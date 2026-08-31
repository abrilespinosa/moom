"""
metro_client.py

Cliente para la API pública del CRTM (Consorcio de Transportes de Madrid):
información de estaciones, tiempos de espera en tiempo real, y posición de
los vehículos de una línea.

A diferencia de la API de EMT, esta API NO requiere autenticación: no hay
token, ni email/password, ni cabeceras especiales. Es de acceso público.

Aunque el archivo se llama metro_client, la API es del CRTM entero y
funciona por MODO de transporte, indicado en el prefijo del código de
parada: "4_" es Metro y "8_" son los autobuses interurbanos. Las mismas
funciones de aquí sirven para los dos, así que no hay un cliente aparte
para el interurbano.

Cuidado con una diferencia importante entre modos, medida contra la API:

- Metro: tiempos de espera y posición de los trenes, ambos en vivo.
- Interurbano: los tiempos SÍ traen corrección en tiempo real (ver
  llegada_en_vivo más abajo), pero las posiciones de GetLineLocation están
  congeladas — se comprobó que 19 autobuses de 5 líneas no se movían ni un
  metro en varios minutos, y que tres de ellos daban coordenadas idénticas
  hasta el quinto decimal 15 minutos después. Por eso el mapa solo pinta
  vehículos de Metro.

Endpoints usados (descubiertos leyendo el código fuente de la librería
citram-python-api y verificados manualmente contra el servidor real):

- GetStops.php?codStop=X        -> info básica de una estación (nombre, stopType, coordenadas)
- GetStopsTimes.php?codStop=X&type=Y&orderBy=Z&stopTimesByIti=W
                                 -> tiempos de espera. IMPORTANTE: el parámetro
                                    stopTimesByIti NO filtra por sentido (se probó
                                    y devuelve siempre ambos sentidos mezclados).
                                    Por eso pedimos una sola vez y separamos
                                    nosotros mismos usando el campo "destination".
- GetLineLocation.php           -> posición (latitud/longitud) de los trenes
                                    circulando en una línea/sentido concreto.
"""

import re
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://www.crtm.es/widgets/api"

# Una única sesión HTTP para todas las llamadas al CRTM, en vez de
# requests.get suelto, que abre una conexión TCP+TLS nueva cada vez.
#
# Ahorra el saludo TLS, unos 80ms por llamada (medido: time_appconnect
# 0,084s). Es una mejora modesta y conviene no atribuirle más: en una
# prueba A/B intercalando ambos métodos contra las mismas estaciones, las
# medianas salieron 0,46s sin sesión y 0,62s con ella, o sea que el ruido
# del propio CRTM se come la diferencia. Lo que de verdad manda son los
# tiempos de respuesta del servidor, que van de 0,1s a 4,5s para la MISMA
# consulta según el momento.
#
# La sesión es de nivel de módulo y la comparten todos los hilos que
# FastAPI usa para atender peticiones. requests.Session es seguro para
# eso en la práctica (urllib3 mantiene un pool de conexiones con su propio
# candado); lo que no admite es compartirse entre procesos.
_sesion = requests.Session()

# Reintentos, pero afinados distinto que en emt_client.py porque el fallo de
# este servidor es otro. Medido con 12 consultas seguidas: 11 salieron y la
# que falló fue un ReadTimeout, o sea su latencia errática de siempre (de
# 0,1s a 6,9s), no un saludo TLS caído como en EMT.
#
# Por eso aquí read=0: una relectura sobre una consulta que ya puede tardar
# 10 segundos duplicaría la espera para recuperar un dato que el frontend va
# a volver a pedir dentro de 20s de todas formas, enseñando mientras tanto
# los últimos tiempos buenos. Los reintentos de conexión sí se quedan:
# fallan al instante y no cuestan nada.
_reintentos = Retry(
    total=2,
    connect=2,
    read=0,
    status=1,
    backoff_factor=0.3,
    status_forcelist=(502, 503, 504),
)
_sesion.mount("https://", HTTPAdapter(max_retries=_reintentos))

# (conectar, leer) en segundos. Sin timeout, requests espera indefinidamente:
# una conexión que el CRTM deje colgada retiene para siempre un hilo del pool
# de FastAPI, y con unas pocas la aplicación entera deja de responder aunque
# el servidor siga vivo. En local no se nota porque el proceso se reinicia
# constantemente.
#
# El límite de lectura es 10s y no menos porque la latencia del CRTM es
# errática de por sí: de 0,1s a 4,5s para la MISMA consulta, con picos
# medidos de 6,9s. Cortar antes convertiría en error lo que solo es un
# servidor lento. El de conexión es corto porque ahí no hay ambigüedad: si
# no llegamos a saludar, no vamos a llegar.
TIMEOUT_SEGUNDOS = (5, 10)

# Dentro de codIssue viene incrustada la hora PROGRAMADA de ese viaje, entre
# guiones bajos: "8__621____4_13:15:00_1_-__20_8__621___" -> "13:15:00".
_HORA_EN_CODISSUE = re.compile(r"_(\d{2}:\d{2}:\d{2})_")


def llegada_en_vivo(llegada):
    """
    Dice si una llegada trae dato en tiempo real o es solo el horario teórico.

    Cómo se distingue (descubierto comparando campos contra la API real):
    el campo "time" es la hora PREVISTA y "codIssue" lleva incrustada la hora
    PROGRAMADA del viaje. Si difieren, alguien ha corregido la previsión con
    información real del autobús; si coinciden al segundo, lo más probable es
    que solo estemos viendo la tabla de horarios.

    Devuelve:
        True   -> hay corrección en vivo
        False  -> la hora prevista coincide con la programada
        None   -> no se puede saber, porque esta llegada no trae codIssue

    Los trenes de Metro caen siempre en None: su codIssue viene vacío. No es
    un problema, porque sus tiempos ya son en tiempo real de por sí; el que
    necesita esta distinción es el interurbano, donde conviven ambas cosas.

    OJO: cuando devuelve False no está garantizado que no haya dato en vivo.
    Un autobús que pase exactamente a su hora daría prevista == programada y
    sería indistinguible. Es decir, sirve para avisar de lo que casi seguro
    es teórico, no para afirmar que algo NO se está siguiendo.
    """
    cod_issue = llegada.get("codIssue") or ""
    encontrada = _HORA_EN_CODISSUE.search(cod_issue)

    if not encontrada:
        return None

    hora_programada = encontrada.group(1)
    hora_prevista = llegada["time"][11:19]  # "2026-08-10T13:15:43+02:00" -> "13:15:43"

    return hora_prevista != hora_programada

# --- Caché en memoria ---
# Mismo patrón que en emt_client.py: variables a nivel de módulo, que viven
# mientras el servidor esté corriendo.
#
# OJO: la posición de los trenes NO se cachea, a propósito. El frontend
# refresca cada 10s y este caché duraba 20s, así que una de cada dos
# peticiones devolvía posiciones repetidas y los trenes se veían dando
# saltos en vez de avanzar. A diferencia de la API de EMT, la del CRTM no
# pide autenticación ni tiene cuota conocida, así que no hay nada que
# proteger: el caché solo estaba empeorando la animación.
#
# Medido en vivo (lunes 11:40, Línea 2): el propio CRTM refresca las
# posiciones cada 20-30s aproximadamente, y suele mover un tren cada vez.
# O sea que el origen ya es lento de por sí: añadirle encima un caché de
# 20s podía duplicar el retraso. Por eso el poller de Metro del frontend
# va a 20s (INTERVALO_REFRESCO_METRO en app.js), acompasado con el ritmo
# real de la fuente: así se evitan peticiones que no traen nada nuevo sin
# reintroducir un caché que añadiría retraso encima.
#
# Los tiempos de espera sí lo conservan: que una hora de llegada se
# actualice 10 segundos más tarde no se percibe, un tren parado sí.
_cache_tiempos_espera = {}

# La info de una estación (nombre, stopType, líneas que pasan por ella) es
# un dato ESTÁTICO: no cambia mientras el servidor está encendido. Por eso
# este caché no tiene caducidad, igual que el de colores de línea en
# gtfs_loader.py. Sin él, cada ciclo del frontend pedía esta misma
# información dos veces (una por el panel de tiempos y otra por los trenes
# del mapa), gastando llamadas al CRTM para recibir siempre lo mismo.
_cache_info_estacion = {}

# Los itinerarios de una línea son igual de estáticos que la información de
# una estación, así que se guardan igual, sin caducidad. Antes se pedían en
# CADA petición de posición de trenes: 0,2s de espera por línea y por
# refresco, cada 20 segundos, para recibir siempre lo mismo.
_cache_info_linea = {}

# Duración de la validez del caché, en segundos.
SEGUNDOS_VALIDEZ_CACHE = 20

# Tope de entradas por caché.
#
# Los tres diccionarios de arriba no se podaban nunca: guardan una entrada por
# id distinto consultado, y dos de ellos (info de estación e info de línea) no
# caducan, así que en un proceso de larga vida crecen sin techo. En el
# despliegue actual apenas importa —en Vercel las instancias se reciclan
# solas—, pero un uvicorn levantado durante días sí lo acumula, y hay 13.542
# paradas que alcanzar.
#
# 500 sobra de largo para el uso real: una sesión mira unas pocas paradas, y
# aun con varias personas a la vez no se acerca. Se desaloja la entrada más
# ANTIGUA, no la menos usada: los diccionarios de Python conservan el orden de
# inserción, así que la primera clave es la que lleva más tiempo dentro.
# Reasignar una clave existente no la mueve al final, o sea que refrescar unos
# tiempos de espera no la rejuvenece. Es una poda tosca a propósito: aquí lo
# que importa es que el diccionario no crezca sin fin, no acertar con la
# política de desalojo.
MAXIMO_ENTRADAS_CACHE = 500


def _guardar_en_cache(cache, clave, valor):
    """
    Guarda una entrada sin dejar que el diccionario crezca sin límite.
    """
    if clave not in cache and len(cache) >= MAXIMO_ENTRADAS_CACHE:
        del cache[next(iter(cache))]

    cache[clave] = valor


def _cache_sigue_siendo_valido(diccionario_cache, clave):
    """
    Comprueba si hay una entrada guardada en el diccionario de caché dado
    y si todavía no ha pasado demasiado tiempo desde que se guardó.
    """
    if clave not in diccionario_cache:
        return False

    _datos, momento_guardado = diccionario_cache[clave]
    segundos_transcurridos = time.time() - momento_guardado

    return segundos_transcurridos < SEGUNDOS_VALIDEZ_CACHE


def obtener_info_estacion(cod_stop):
    """
    Devuelve la información básica de una estación de Metro: nombre,
    coordenadas, stopType (necesario para pedir tiempos de espera después),
    y las líneas que pasan por ella.

    Parámetros:
        cod_stop: código de la estación en formato CRTM, por ejemplo "4_323"
                  (Alsacia). El "4" identifica el modo Metro.

    Devuelve un diccionario con la estructura que da la API directamente,
    por ejemplo:
        {
            "codStop": "4_323",
            "name": "ALSACIA",
            "stopType": 0,
            "coordinates": {"longitude": -3.62351, "latitude": 40.41829},
            "codLines": {"Line": ["4__2___"]},
            ...
        }
    """
    if cod_stop in _cache_info_estacion:
        return _cache_info_estacion[cod_stop]

    url = f"{BASE_URL}/GetStops.php"
    parametros = {"codStop": cod_stop}

    respuesta = _sesion.get(url, params=parametros, timeout=TIMEOUT_SEGUNDOS)
    respuesta.raise_for_status()

    datos = respuesta.json()

    try:
        estacion = datos["stops"]["Stop"]
    except KeyError:
        print("Respuesta inesperada al pedir info de estación, revisa el JSON:")
        print(datos)
        raise

    # Misma rareza que en obtener_tiempos_espera y obtener_posicion_trenes:
    # cuando solo hay UN elemento, la API lo devuelve suelto en vez de dentro
    # de una lista de un elemento. Aquí pasa con las líneas que pasan por la
    # estación: Alsacia (solo Línea 2) devuelve la cadena "4__2___", mientras
    # que Gran Vía (Líneas 1 y 5) devuelve ["4__1___", "4__5___"].
    #
    # Lo normalizamos aquí, en el cliente, para que quien use esta función
    # pueda recorrer codLines siempre igual sin comprobar el tipo. Si no,
    # el frontend hace .map() sobre una cadena y revienta en silencio,
    # dejando sin trenes en el mapa a todas las estaciones de una sola línea
    # (que son la mayoría de las 240).
    lineas = estacion["codLines"]["Line"]
    if not isinstance(lineas, list):
        estacion["codLines"]["Line"] = [lineas]

    _guardar_en_cache(_cache_info_estacion, cod_stop, estacion)

    return estacion


def obtener_info_linea(cod_line):
    """
    Devuelve la información de una línea de Metro: su descripción y, sobre
    todo, sus dos itinerarios (uno por cada sentido de circulación), cada
    uno con su "codItinerary" y su "direction" (1 o 2).

    El resultado se guarda en caché sin caducidad, como el de las
    estaciones: los itinerarios de una línea no cambian mientras el
    servidor está encendido. Sin el caché, cada petición de posición de
    trenes empezaba por esta llamada (0,2s medidos) para recibir siempre
    exactamente lo mismo — y esa petición se repite por cada línea de la
    estación cada 20 segundos.

    Parámetros:
        cod_line: código de la línea, por ejemplo "4__2___" (Línea 2)

    Devuelve un diccionario con la estructura:
        {
            "codLine": "4__2___",
            "description": "Las Rosas-Cuatro Caminos",
            "itinerary": {
                "Itinerary": [
                    {"codItinerary": "4__2____1__IT_1", "direction": 1, "name": "LAS ROSAS-CUATRO CAMINOS", ...},
                    {"codItinerary": "4__2____2__IT_1", "direction": 2, "name": "CUATRO CAMINOS-LAS ROSAS", ...}
                ]
            },
            ...
        }
    """
    if cod_line in _cache_info_linea:
        return _cache_info_linea[cod_line]

    url = f"{BASE_URL}/GetLinesInformation.php"
    parametros = {"activeItinerary": 1, "codLine": cod_line}

    respuesta = _sesion.get(url, params=parametros, timeout=TIMEOUT_SEGUNDOS)
    respuesta.raise_for_status()

    datos = respuesta.json()

    try:
        info = datos["lines"]["LineInformation"]
    except KeyError:
        print("Respuesta inesperada al pedir info de línea, revisa el JSON:")
        print(datos)
        raise

    # La misma rareza que en las otras tres funciones de este archivo: cuando
    # solo hay UN elemento, la API lo devuelve suelto en vez de dentro de una
    # lista de un elemento.
    #
    # Hoy no se dispara: comprobadas las 13 líneas de Metro en vivo, todas
    # devuelven sus dos itinerarios, el Ramal incluido. Se normaliza igual
    # porque quien lo consume hace "for itinerario in itinerarios": con un
    # diccionario suelto iteraría sobre sus CLAVES, que son cadenas, y
    # reventaría con un TypeError difícil de leer al hacer itinerario["stops"].
    itinerarios = info["itinerary"]["Itinerary"]
    if not isinstance(itinerarios, list):
        info["itinerary"]["Itinerary"] = [itinerarios]

    _guardar_en_cache(_cache_info_linea, cod_line, info)

    return info


# La API exige el parámetro "type", pero NO afecta a la respuesta.
# Comprobado contra el servidor real en Alsacia, Sol y una parada
# interurbana: pidiendo type 0, 1, 5 y 9 devuelve exactamente las mismas
# llegadas (mismo destino y misma hora). Además, el "stopType" real de
# todas las paradas consultadas es 0.
#
# Importa porque antes había que llamar a GetStops PRIMERO solo para
# averiguar el stopType y poder pedir los tiempos después: dos llamadas
# en serie, cada una de entre 0,1s y 4,5s. Con un valor fijo, quien las
# necesite puede lanzarlas a la vez.
TIPO_PARADA_POR_DEFECTO = 0


def obtener_tiempos_espera(cod_stop, stop_type=TIPO_PARADA_POR_DEFECTO):
    """
    Consulta los próximos trenes que van a pasar por una estación, en
    ambos sentidos a la vez.

    Parámetros:
        cod_stop: código de la estación, por ejemplo "4_323" (Alsacia)
        stop_type: el "stopType" de esa parada. Se puede omitir: la API lo
                   exige pero ignora su valor (ver TIPO_PARADA_POR_DEFECTO).

    Devuelve la lista cruda de trenes tal como la da la API, cada uno con
    su "destination" (texto del destino, ej. "LAS ROSAS"), "direction"
    (1 o 2) y "time" (hora estimada de llegada). Agrupar por destino se
    hace en el backend (main.py), no aquí: este cliente solo habla con
    la API externa.
    """
    if _cache_sigue_siendo_valido(_cache_tiempos_espera, cod_stop):
        datos, _momento_guardado = _cache_tiempos_espera[cod_stop]
        return datos

    url = f"{BASE_URL}/GetStopsTimes.php"
    parametros = {
        "codStop": cod_stop,
        "type": stop_type,
        "orderBy": 2,
        # stopTimesByIti es obligatorio para la API, pero no afecta al
        # resultado (se probó pasando los dos itinerarios posibles y la
        # respuesta fue idéntica). Pasamos el cod_stop como relleno,
        # siguiendo el mismo valor que usa el ejemplo de la librería original.
        "stopTimesByIti": cod_stop,
    }

    respuesta = _sesion.get(url, params=parametros, timeout=TIMEOUT_SEGUNDOS)
    respuesta.raise_for_status()

    datos = respuesta.json()

    try:
        trenes = datos["stopTimes"]["times"].get("Time", [])
    except KeyError:
        print("Respuesta inesperada al pedir tiempos de espera, revisa el JSON:")
        print(datos)
        raise

    # La API a veces devuelve un solo resultado como diccionario suelto
    # en vez de una lista de un elemento. Lo normalizamos siempre a lista
    # para que el resto del código no tenga que comprobar el tipo.
    if isinstance(trenes, dict):
        trenes = [trenes]

    _guardar_en_cache(_cache_tiempos_espera, cod_stop, (trenes, time.time()))

    return trenes


def obtener_posicion_trenes(mode_cod, cod_itinerary, cod_line, cod_stop, direction):
    """
    Consulta la posición geográfica actual de los trenes circulando en
    una línea y sentido concretos.

    Parámetros:
        mode_cod: id del modo de transporte (4 para Metro)
        cod_itinerary: código del itinerario, ej. "4__2____2__IT_1"
        cod_line: código de la línea, ej. "4__2___"
        cod_stop: cualquier estación de esa línea (la API lo pide como
                  formalidad, el resultado es el mismo sea cual sea)
        direction: sentido del itinerario (1 o 2)

    Devuelve una lista de vehículos, cada uno con su "codVehicle" y sus
    "coordinates" (longitude, latitude).

    Sin caché a propósito: ver la nota en la sección de cachés al principio
    de este archivo.
    """
    url = f"{BASE_URL}/GetLineLocation.php"
    parametros = {
        "mode": mode_cod,
        "codItinerary": cod_itinerary,
        "codLine": cod_line,
        "codStop": cod_stop,
        "direction": direction,
    }

    respuesta = _sesion.get(url, params=parametros, timeout=TIMEOUT_SEGUNDOS)
    respuesta.raise_for_status()

    datos = respuesta.json()

    try:
        vehiculos = datos["vehiclesLocation"].get("VehicleLocation", [])
    except KeyError:
        print("Respuesta inesperada al pedir posición de trenes, revisa el JSON:")
        print(datos)
        raise

    if isinstance(vehiculos, dict):
        vehiculos = [vehiculos]

    return vehiculos


if __name__ == "__main__":
    COD_STOP_ALSACIA = "4_323"

    info = obtener_info_estacion(COD_STOP_ALSACIA)
    print("Estación:", info["name"], "| stopType:", info["stopType"])

    tiempos = obtener_tiempos_espera(COD_STOP_ALSACIA, info["stopType"])
    print(f"\n{len(tiempos)} trenes próximos:")
    for tren in tiempos:
        print(" ->", tren["destination"], "| hora:", tren["time"])