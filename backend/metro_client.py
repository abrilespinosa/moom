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

BASE_URL = "https://www.crtm.es/widgets/api"

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

# Duración de la validez del caché, en segundos.
SEGUNDOS_VALIDEZ_CACHE = 20


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

    respuesta = requests.get(url, params=parametros)
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

    _cache_info_estacion[cod_stop] = estacion

    return estacion


def obtener_info_linea(cod_line):
    """
    Devuelve la información de una línea de Metro: su descripción y, sobre
    todo, sus dos itinerarios (uno por cada sentido de circulación), cada
    uno con su "codItinerary" y su "direction" (1 o 2).

    Esta función no usa caché propio: la información de una línea (sus
    itinerarios) no cambia de un minuto a otro, así que no hace falta
    refrescarla con la misma frecuencia que los tiempos de espera o la
    posición de los trenes. Se llama solo cuando se necesita resolver
    los itinerarios de una línea, normalmente antes de pedir su posición.

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
    url = f"{BASE_URL}/GetLinesInformation.php"
    parametros = {"activeItinerary": 1, "codLine": cod_line}

    respuesta = requests.get(url, params=parametros)
    respuesta.raise_for_status()

    datos = respuesta.json()

    try:
        return datos["lines"]["LineInformation"]
    except KeyError:
        print("Respuesta inesperada al pedir info de línea, revisa el JSON:")
        print(datos)
        raise


def obtener_tiempos_espera(cod_stop, stop_type):
    """
    Consulta los próximos trenes que van a pasar por una estación, en
    ambos sentidos a la vez.

    Parámetros:
        cod_stop: código de la estación, por ejemplo "4_323" (Alsacia)
        stop_type: el valor "stopType" que devuelve obtener_info_estacion
                   para esa misma estación. La API lo exige aunque no
                   sepamos bien qué significa cada valor.

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

    respuesta = requests.get(url, params=parametros)
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

    _cache_tiempos_espera[cod_stop] = (trenes, time.time())

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

    respuesta = requests.get(url, params=parametros)
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