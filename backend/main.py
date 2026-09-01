"""
main.py

Servidor web (API) que expone los datos de EMT Madrid en una URL local,
para que el futuro frontend (mapa en el navegador) pueda consultarlos.

Cómo arrancarlo (desde la raíz del proyecto, en terminal):
    uvicorn backend.main:app --reload

Luego puedes visitar en el navegador, por ejemplo:
    http://127.0.0.1:8000/parada/72
"""

from concurrent.futures import ThreadPoolExecutor

import requests
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.emt_client import obtener_llegadas_parada
from backend.gtfs_loader import (
    cargar_accesibilidad,
    cargar_todas_las_paradas,
    cargar_colores_lineas_metro,
    cargar_horarios,
    cargar_lineas,
)
from backend.metro_client import (
    obtener_info_estacion,
    obtener_info_linea,
    obtener_tiempos_espera,
    obtener_posicion_trenes,
    llegada_en_vivo,
)

# Esta variable "app" es el corazón de FastAPI: representa nuestro servidor.
# Uvicorn (el programa que lo ejecuta) busca específicamente una variable
# llamada "app" en este archivo.
app = FastAPI(title="Moom API")

# CORS solo para desarrollo. En el despliegue el frontend y la API comparten
# dominio (la API cuelga de /api, ver vercel.json), así que el navegador ni
# llega a hacer la comprobación: producción no necesita ninguna de estas
# reglas. Quedan acotadas a los dos orígenes locales con los que se trabaja
# —el servidor estático del frontend y uvicorn— en vez del "*" de antes,
# que dejaba a cualquier página leer esta API desde el navegador.
#
# Solo GET: no hay un solo endpoint que escriba nada.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)

PARADAS = cargar_todas_las_paradas()

# La accesibilidad se mezcla aquí, al arrancar, en vez de meterla en
# paradas.json: la generan dos scripts distintos, y así regenerar el callejero
# tras un volcado GTFS nuevo no borra la lista de accesibilidad, que se
# mantiene a mano y no viene de ningún GTFS.
#
# Solo la llevan las estaciones de Metro que están en la lista oficial. Las
# demás no llevan el campo, que es distinto de llevarlo a "no": de la mayoría
# no se sabe, y decir "no accesible" sin saberlo sería tan dañino como decir
# "accesible" sin saberlo.
_ACCESIBILIDAD = cargar_accesibilidad()

# Se comprueba la fuente y no solo el id: hay 9 intercambiadores (Moncloa,
# Plaza de Castilla, Príncipe Pío...) que aparecen DOS veces en el callejero
# con el MISMO id, una vez desde el volcado del CRTM y otra desde el de Metro,
# en idénticas coordenadas. Sin este filtro, la copia de autobús también salía
# marcada como accesible, y la lista es de Metro.
for _parada in PARADAS:
    if _parada["fuente"] != "METRO":
        continue

    _grado = _ACCESIBILIDAD.get(_parada["id"])
    if _grado is not None:
        _parada["accesibilidad"] = _grado

# Diccionario id -> parada, para búsquedas rápidas por id en vez de
# recorrer las 13.542 paradas cada vez que el endpoint de Metro necesita
# encontrar el codAnden de una estación.
PARADAS_POR_ID = {parada["id"]: parada for parada in PARADAS}

# Las líneas con su recorrido de paradas, construidas desde el GTFS al
# arrancar (alrededor de un segundo). Si faltan los archivos pesados que no
# van al repositorio, la lista queda vacía y la búsqueda por línea se
# desactiva sola, sin afectar al resto de la aplicación.
LINEAS = cargar_lineas()
LINEAS_POR_ID = {linea["id"]: linea for linea in LINEAS}

# Los horarios de paso, indexados por el mismo id de línea. Se cargan una vez
# aquí, como todo lo demás del volcado.
HORARIOS = cargar_horarios()


@app.exception_handler(requests.RequestException)
def fallo_de_api_externa(peticion: Request, excepcion: requests.RequestException):
    """
    Convierte cualquier fallo de red contra EMT o el CRTM en un 503 con
    mensaje, en vez del 500 pelado que salía antes.

    Un único manejador para todos los endpoints porque el fallo es siempre
    el mismo: ninguna de estas rutas hace nada más que hablar con una API
    externa. requests.RequestException es la clase madre de todo lo que
    pueden lanzar los dos clientes — el Timeout que ahora sí puede saltar,
    la conexión rechazada, y el HTTPError de raise_for_status cuando la API
    responde con un 4xx o 5xx propio.

    503 y no 500 porque describe lo que de verdad pasa: no está roto
    nuestro código, está caída (o lenta) una API de la que dependemos.
    El frontend lo distingue por el código, sin leer el cuerpo.

    Las excepciones que ocurren dentro de en_paralelo() llegan igual aquí:
    .result() las vuelve a lanzar en el hilo del endpoint.
    """
    # flush=True porque cuando la salida no es una terminal (un servidor
    # desplegado, o uvicorn redirigido a un fichero) Python la almacena en
    # un búfer: sin esto, el aviso se pierde justo en el caso en el que
    # hace falta, que es depurar un fallo en producción. Comprobado.
    print(
        f"[api externa] {peticion.url.path}: {type(excepcion).__name__}: {excepcion}",
        flush=True,
    )

    return JSONResponse(
        status_code=503,
        content={
            "error": "api_externa_no_disponible",
            "mensaje": (
                "El servicio de datos en tiempo real no responde ahora mismo. "
                "Inténtalo de nuevo en unos segundos."
            ),
        },
    )


def en_paralelo(*funciones):
    """
    Ejecuta varias funciones a la vez y devuelve sus resultados en orden.

    Sirve para las peticiones que necesitan dos datos del CRTM que no
    dependen entre sí (la información de la estación y sus tiempos de
    espera). Encadenadas, la espera es la suma de las dos; lanzadas a la
    vez, la de la más lenta. Con un servidor que tarda entre 0,1s y 4,5s
    en la misma consulta, esa diferencia se nota en el panel.

    Los endpoints de FastAPI que las llaman son funciones normales (def y
    no async def), así que ya se ejecutan en un hilo del pool de FastAPI;
    estos dos hilos de más solo viven lo que dura la petición.

    Si alguna función lanza una excepción, .result() la vuelve a lanzar
    aquí, igual que si se hubiera llamado directamente.
    """
    with ThreadPoolExecutor(max_workers=len(funciones)) as ejecutor:
        futuros = [ejecutor.submit(funcion) for funcion in funciones]
        return [futuro.result() for futuro in futuros]


def agrupar_llegadas(llegadas):
    """
    Agrupa las llegadas que devuelve la API del CRTM por LÍNEA + destino, que
    es como las presenta el panel: una tarjeta por línea y sentido.

    Lo usan tanto Metro como el interurbano, porque la API devuelve la misma
    estructura para los dos modos.

    Agrupar solo por destino no bastaría: en una estación de trasbordo el
    destino no dice de qué línea es cada vehículo, y esa es justo la
    información que necesita el distintivo de color de cada tarjeta.

    Cada grupo lleva un "enVivo" que dice si su llegada más próxima (la que
    se muestra en grande) trae dato en tiempo real, es horario teórico, o no
    se puede saber. Se toma de la PRIMERA llegada del grupo porque la API ya
    las devuelve ordenadas por hora (pedimos orderBy=2), así que la primera
    que llega aquí es la más cercana.
    """
    grupos = {}

    for llegada in llegadas:
        cod_line = llegada["line"]["codLine"]
        destino = llegada["destination"]
        clave = (cod_line, destino)

        if clave not in grupos:
            grupos[clave] = {
                "codLine": cod_line,
                "linea": llegada["line"]["shortDescription"],
                "destino": destino,
                "tiempos": [],
                "enVivo": llegada_en_vivo(llegada),
            }

        grupos[clave]["tiempos"].append(llegada["time"])

    return list(grupos.values())

# Cuánto puede guardarse una respuesta que no cambia mientras el servidor
# viva. Son los datos del volcado GTFS: paradas, líneas y colores. No se
# parecen en nada a los tiempos de llegada, que caducan en segundos.
#
# Dos plazos porque son dos cachés distintas: max-age es la del navegador y
# s-maxage la del CDN de Vercel. Al navegador se le da una hora —si
# regeneras el GTFS, quien tenga la página abierta lo verá pronto— y al CDN
# un día, porque Vercel vacía su caché en cada despliegue y ahí no hay
# riesgo de servir datos viejos.
#
# Lo que se gana no es tanto el ancho de banda como las visitas repetidas:
# hoy cada carga ejecuta la función y baja 247 KB (x-vercel-cache: MISS);
# con esto, la segunda visita no descarga nada.
CACHE_DATOS_ESTATICOS = "public, max-age=3600, s-maxage=86400"


@app.get("/paradas")
def listar_paradas(respuesta: Response):
    """
    Devuelve todas las paradas de las tres redes (id, nombre, lat, lon).
    """
    respuesta.headers["Cache-Control"] = CACHE_DATOS_ESTATICOS
    return PARADAS

# Cuántas paradas devuelve /paradas/cerca si no se pide otra cosa. Cuarenta
# cubre de sobra lo que hay alrededor de una parada en Madrid, y pesa unos
# pocos KB frente a los 254 de la lista completa.
PARADAS_CERCANAS_POR_DEFECTO = 40
MAXIMO_PARADAS_CERCANAS = 200


def _distancia_aproximada(lat1, lon1, lat2, lon2):
    """
    Distancia al cuadrado en un plano, sin raíz ni trigonometría.

    Aquí NO hace falta la distancia real: solo hay que ORDENAR, y la raíz
    cuadrada es monótona, así que ordenar por el cuadrado da el mismo orden y
    se ahorra 13.542 raíces por petición.

    El coseno de la latitud corrige que un grado de longitud en Madrid mide
    unos 0,76 de lo que mide uno de latitud; sin él, "lo más cercano" saldría
    estirado en sentido este-oeste. Se toma como constante porque la ciudad
    entera cabe en medio grado y la variación es despreciable.
    """
    ESTRECHAMIENTO_EN_MADRID = 0.76

    dlat = lat1 - lat2
    dlon = (lon1 - lon2) * ESTRECHAMIENTO_EN_MADRID

    return dlat * dlat + dlon * dlon


@app.get("/paradas/cerca")
def paradas_cerca(respuesta: Response, lat: float, lon: float, limite: int = PARADAS_CERCANAS_POR_DEFECTO):
    """
    Las paradas más próximas a un punto, ordenadas de más cerca a más lejos.

    Ejemplo de uso: GET /paradas/cerca?lat=40.4168&lon=-3.7038

    Existe por quien abre esto de pie en una parada. /paradas devuelve las
    13.542 de las tres redes, que son 254 KB comprimidos, y hasta que no
    llegan no hay ni buscador ni marcadores. Con buena cobertura no se nota;
    con la de una marquesina bajo un edificio, es la diferencia entre útil e
    inservible.

    Esto pesa unos pocos KB y permite empezar a usar la aplicación mientras la
    lista completa sigue viajando por detrás.

    NO sustituye a /paradas: el buscador necesita el callejero entero para
    encontrar una parada del otro lado de la ciudad.
    """
    # Acotado por arriba: sin esto, un limite=999999 recorre y serializa la
    # lista entera, que es justo lo que este endpoint viene a evitar.
    limite = max(1, min(limite, MAXIMO_PARADAS_CERCANAS))

    cercanas = sorted(
        PARADAS,
        key=lambda parada: _distancia_aproximada(lat, lon, parada["lat"], parada["lon"]),
    )[:limite]

    # Misma caché que el resto del volcado GTFS: son datos estáticos. Cambia
    # con las coordenadas, pero la URL las lleva, así que cada punto tiene su
    # propia entrada de caché.
    respuesta.headers["Cache-Control"] = CACHE_DATOS_ESTATICOS

    return cercanas


@app.get("/lineas")
def listar_lineas(respuesta: Response):
    """
    Devuelve todas las líneas de las tres redes, SIN su recorrido.

    Ejemplo de uso: GET /lineas

    El recorrido se deja fuera a propósito: son casi 30.000 identificadores
    de parada entre las 603 líneas, y el buscador solo necesita el número,
    el nombre y el color para filtrar mientras se escribe. Las paradas se
    piden aparte, ya en /linea/{id}, cuando se elige una concreta.

    El número de línea NO es único entre redes: hay 21 que se repiten, como
    la 1 y la 2, que existen a la vez en EMT y en Metro. Por eso cada línea
    lleva su "fuente", y el "id" la incluye como prefijo.
    """
    respuesta.headers["Cache-Control"] = CACHE_DATOS_ESTATICOS

    return [
        {clave: linea[clave] for clave in linea if clave != "sentidos"}
        for linea in LINEAS
    ]


@app.get("/linea/{cod_linea}")
def recorrido_linea(cod_linea: str, respuesta: Response):
    """
    Devuelve una línea con sus paradas en orden, un bloque por sentido.

    Ejemplo de uso: GET /linea/EMT-027

    Las paradas salen con id y nombre. El nombre se resuelve aquí, contra
    las paradas que ya tenemos cargadas, para que el frontend pueda pintar
    la lista sin cruzar nada por su cuenta; el id le sirve luego para
    seleccionar esa parada y ver sus llegadas.
    """
    linea = LINEAS_POR_ID.get(cod_linea)

    if linea is None:
        # Sin cabecera de caché a propósito: no tiene sentido guardar durante
        # un día que una línea no existe. Si aparece en el próximo volcado,
        # la respuesta buena tiene que llegar ya.
        return {
            "encontrada": False,
            "mensaje": "No se encontró esa línea.",
        }

    # Es un dato del volcado GTFS, igual de estático que /paradas o /lineas, y
    # se pedía sin cachear: cada vez que alguien abría el recorrido de una
    # línea se ejecutaba la función y se volvía a bajar la respuesta entera,
    # con los nombres de parada ya resueltos.
    respuesta.headers["Cache-Control"] = CACHE_DATOS_ESTATICOS

    sentidos = [
        {
            "destino": sentido["destino"],
            "paradas": [
                {
                    "id": id_parada,
                    # Si una parada del recorrido ya no está en stops.txt
                    # (los volcados de líneas y de paradas no siempre van a
                    # la par), la listamos igual en vez de romper el orden.
                    "nombre": PARADAS_POR_ID.get(id_parada, {}).get(
                        "nombre", "Parada desconocida"
                    ),
                }
                for id_parada in sentido["paradas"]
            ],
        }
        for sentido in linea["sentidos"]
    ]

    return {
        "encontrada": True,
        **{clave: linea[clave] for clave in linea if clave != "sentidos"},
        "sentidos": sentidos,
    }


# El CRTM publica en su web la tabla de horarios de cada línea como imagen,
# una por sentido, con el diagrama del recorrido y las notas al pie. Es la
# misma hoja que reparten en papel, y es mejor que cualquier tabla que podamos
# construir nosotros: trae los tipos de día incluso en las 101 líneas cuyo GTFS
# no los distingue.
#
# El patrón, deducido de la página de la línea 191 y comprobado en 60 líneas de
# las dos redes (100% de acierto, ambos sentidos):
#
#     https://www.crtm.es/datos_lineas/horarios/{MODO}{NUMERO}H{1|2}.png
#
# El modo va delante del número: 8 para el interurbano y 6 para la EMT. Metro
# NO tiene imágenes (404 en todas las probadas), lo cual es coherente: publica
# frecuencias, no horas de paso.
URL_HORARIOS_CRTM = "https://www.crtm.es/datos_lineas/horarios"

# OJO, las dos redes no se construyen igual, y es un error fácil:
#
# - El route_id del CRTM YA LLEVA el modo delante ("8__191___" -> "8191"), así
#   que solo hay que quitarle los guiones bajos. Añadirle el 8 otra vez daba
#   "88191" y un 404.
# - El de EMT es solo el número ("103"), así que ahí sí hay que anteponer su
#   modo, que es el 6.
MODO_QUE_HAY_QUE_ANTEPONER = {"CRTM": "", "EMT": "6"}


def _imagenes_de_horario(cod_linea):
    """
    Las dos imágenes oficiales de una línea, o None si esa red no las publica.

    No se comprueba que existan: sería una petición a la web del CRTM por cada
    apertura de línea, y el frontend ya se entera solo si una imagen no carga.
    """
    fuente, _, route_id = cod_linea.partition("-")

    if fuente not in MODO_QUE_HAY_QUE_ANTEPONER:
        return None

    codigo = MODO_QUE_HAY_QUE_ANTEPONER[fuente] + route_id.replace("_", "")

    return [
        {"sentido": "Ida", "url": f"{URL_HORARIOS_CRTM}/{codigo}H1.png"},
        {"sentido": "Vuelta", "url": f"{URL_HORARIOS_CRTM}/{codigo}H2.png"},
    ]


@app.get("/linea/{cod_linea}/horarios")
def horarios_linea(cod_linea: str, respuesta: Response):
    """
    Los horarios de paso de una línea, por sentido y tipo de día.

    Ejemplo de uso: GET /linea/CRTM-8__191___/horarios

    Va aparte de /linea/{id} a propósito: el recorrido se pide siempre al abrir
    una línea, y los horarios solo si se despliegan. Son datos distintos, de
    tamaño distinto, y no tiene sentido pagar los dos cuando se quiere uno.

    El campo "tipo" dice qué se está devolviendo, y NO es un detalle de
    implementación que el frontend pueda ignorar:

    - "horas": salidas reales, como las publica el CRTM para el interurbano.
    - "frecuencias": franjas con su intervalo ("de 6:00 a 9:00, cada 5 min"),
      que es lo único que publican EMT y Metro. Enseñarlo como si fueran horas
      de paso sería inventarse una precisión que el origen no tiene.

    Y "sinTiposDeDia" avisa de que el volcado no distingue laborable de sábado
    ni de domingo para esa línea. Son 101 de las 340 del CRTM, así que no es un
    caso raro: el panel tiene que decirlo en vez de dar a entender que solo hay
    un horario.
    """
    if cod_linea not in LINEAS_POR_ID:
        raise HTTPException(status_code=404, detail="Línea desconocida")

    horarios = HORARIOS.get(cod_linea)

    if horarios is None:
        # La línea existe pero no tiene horarios en el volcado. Es el mismo
        # caso que las 21 sin recorrido: se responde con honestidad en vez de
        # con un 404, que daría a entender que la línea no existe.
        return {"disponible": False, "sentidos": []}

    respuesta.headers["Cache-Control"] = CACHE_DATOS_ESTATICOS

    return {
        "disponible": True,
        # Las imágenes oficiales van primero cuando existen: traen el diagrama
        # del recorrido, las notas al pie y los tipos de día incluso en las
        # líneas cuyo GTFS no los distingue. La tabla de abajo se queda como
        # alternativa: pesa unos KB frente a 300-800 de la imagen, y un lector
        # de pantalla no puede leer un PNG.
        "imagenes": _imagenes_de_horario(cod_linea),
        **horarios,
    }


@app.get("/")
def inicio():
    """
    Ruta raíz, solo para confirmar que el servidor está vivo.
    Visitar http://127.0.0.1:8000/ debería mostrar este mensaje.
    """
    return {"mensaje": "Moom API funcionando. Prueba /parada/{numero_de_parada}"}


@app.get("/parada/{stop_id}")
def llegadas_parada(stop_id: str):
    """
    Devuelve los autobuses que se acercan a la parada indicada.

    Ejemplo de uso: GET /parada/72              (parada urbana de EMT)
                    GET /parada/par_8_06002     (interurbana del CRTM)

    Las dos fuentes se sirven aquí porque para el frontend ambas son "una
    parada de autobús", pero cada una viene de una API distinta:

    - EMT: su propia API autenticada. Devolvemos su JSON tal cual, con las
      llegadas colgando de data[0].Arrive.
    - CRTM (ids "par_8_XXXXX"): la misma API pública que usamos para Metro.
      Devolvemos las llegadas ya agrupadas en "llegadas", igual que
      /metro/parada, para que el panel pueda pintarlas con el mismo código.

    Durante mucho tiempo aquí se respondía que el interurbano no tenía
    tiempo real. Resultó que sí lo tiene: la API del CRTM funciona por modo
    de transporte y el "8" del id es precisamente el del interurbano, solo
    que nunca se había probado contra ella. Ver llegada_en_vivo() en
    metro_client.py para el matiz de qué llegadas son en vivo y cuáles son
    horario teórico.
    """
    # Solo se aceptan ids que existan en el GTFS cargado. Además de dar un
    # 404 honesto en vez de un error de la API remota, esto cierra una vía
    # de abuso: el id se interpola en la RUTA de la URL de EMT (ver
    # obtener_llegadas_parada), así que un valor con "?" o con "../" dentro
    # cambiaba la petición que sale de aquí, y esa petición lleva nuestro
    # token. El host es fijo, o sea que nunca se pudo saltar a otro
    # dominio, pero sí alcanzar otras rutas de la propia API de EMT.
    #
    # En producción esto lo frenaba el edge de Vercel, que rechaza las
    # barras codificadas antes de llegar aquí; en local con uvicorn no hay
    # nada que lo pare, así que la comprobación tiene que estar en el
    # código. Es la misma validación que ya hacían los endpoints de Metro.
    if stop_id not in PARADAS_POR_ID:
        raise HTTPException(status_code=404, detail="Parada desconocida")

    if stop_id.startswith("par_"):
        # La API del CRTM solo entiende el código sin el prefijo del GTFS:
        # "par_8_06002" -> "8_06002". Misma traducción que en Metro.
        cod_parada = stop_id.replace("par_", "", 1)

        # Las dos llamadas a la vez: los tiempos ya no esperan a que la
        # información de la parada llegue para saber su stopType, porque
        # la API ignora ese parámetro (ver TIPO_PARADA_POR_DEFECTO).
        info_parada, llegadas = en_paralelo(
            lambda: obtener_info_estacion(cod_parada),
            lambda: obtener_tiempos_espera(cod_parada),
        )

        return {
            "parada": info_parada["name"],
            "codStop": stop_id,
            "llegadas": agrupar_llegadas(llegadas),
        }

    return obtener_llegadas_parada(stop_id)


def lineas_de_metro_de(info_estacion):
    """
    Filtra el codLines de una estación dejando solo líneas de Metro.

    En las grandes estaciones de trasbordo, la API devuelve en codLines
    TODAS las líneas que paran ahí, incluidas las que no son de Metro:
    Sol, por ejemplo, devuelve además "5__C3___", "5__C4_A__" y
    "5__C4_B__", que son líneas de Cercanías (el prefijo "5__" es el modo
    ferroviario; Metro es el "4__").

    El frontend usa esta lista para pedir los trenes de cada línea a
    /metro/linea/{codLine}/vehiculos, así que sin filtrar acabaría
    pidiendo trenes de Cercanías a un endpoint de Metro: hoy devuelven
    cero vehículos y solo gastan peticiones, pero si algún día trajeran
    alguno se pintaría en el mapa como si fuera un tren de Metro, con el
    color azul de respaldo porque no está en routes.txt.

    Usamos el propio routes.txt de Metro como fuente de verdad de "qué
    es una línea de Metro", en vez de comprobar el prefijo a mano: así,
    además, toda línea que devolvemos tiene color garantizado.
    """
    lineas_de_metro = cargar_colores_lineas_metro()

    return [
        linea
        for linea in info_estacion["codLines"]["Line"]
        if linea in lineas_de_metro
    ]


@app.get("/metro/parada/{cod_stop}/lineas")
def lineas_estacion_metro(cod_stop: str):
    """
    Devuelve solo las líneas de Metro que pasan por una estación.

    Ejemplo de uso: GET /metro/parada/est_4_323/lineas

    Es la mitad barata de /metro/parada: una sola llamada al CRTM
    (GetStops, 0,15s medidos y con caché permanente), sin los tiempos de
    espera, que son los que tardan entre medio segundo y cinco.

    Existe por el mapa. Para pintar los trenes hay que saber primero qué
    líneas pasan por la estación, y eso se pedía a /metro/parada, que de
    paso traía unas llegadas que el mapa no usa y que el panel ya estaba
    pidiendo por su cuenta. Resultado: los trenes tardaban en aparecer lo
    que tardase la llamada más lenta del CRTM, sin ninguna necesidad.
    """
    estacion = PARADAS_POR_ID.get(cod_stop)
    if estacion is None or estacion.get("codAnden") is None:
        return {"codStop": cod_stop, "codLines": []}

    info_estacion = obtener_info_estacion(estacion["codAnden"])

    return {
        "codStop": cod_stop,
        "codLines": lineas_de_metro_de(info_estacion),
    }


@app.get("/metro/parada/{cod_stop}")
def tiempos_estacion_metro(cod_stop: str):
    """
    Devuelve los próximos trenes en una estación de Metro, agrupados por
    línea y destino (igual que el panel de la app oficial: un bloque por
    línea y sentido, con el distintivo de la línea a la izquierda).

    Ejemplo de uso: GET /metro/parada/est_4_323  (Alsacia, Línea 2)

    IMPORTANTE: cod_stop aquí es el id de la ESTACIÓN (ej. "est_4_323"),
    el mismo que usamos para pintar el punto en el mapa. La API del CRTM
    no reconoce este id directamente (devuelve vacío) — solo reconoce
    el id de ANDÉN (ej. "4_323"), que guardamos en gtfs_loader.py como
    el campo "codAnden" de cada estación. Por eso el primer paso aquí es
    resolver cod_stop -> codAnden antes de llamar a metro_client.

    Después, igual que antes:
    1. obtener_info_estacion(codAnden) -> necesitamos su "stopType"
    2. obtener_tiempos_espera -> nos da los trenes de AMBOS sentidos mezclados

    El agrupado por destino se hace aquí, no en metro_client.py, porque es
    una decisión de "cómo presentamos los datos a nuestro frontend", no de
    "cómo hablamos con la API externa".
    """
    estacion = PARADAS_POR_ID.get(cod_stop)
    if estacion is None or estacion.get("codAnden") is None:
        return {
            "tiempo_real_disponible": False,
            "mensaje": "No se encontró un andén válido para esta estación de Metro.",
        }

    cod_anden = estacion["codAnden"]

    # Las dos a la vez, no una detrás de otra. Antes había que esperar a
    # GetStops para conocer el stopType y solo entonces pedir los tiempos;
    # comprobado contra la API, ese parámetro no cambia la respuesta, así
    # que la espera del panel pasa de ser la SUMA de las dos llamadas a la
    # de la más lenta.
    info_estacion, trenes = en_paralelo(
        lambda: obtener_info_estacion(cod_anden),
        lambda: obtener_tiempos_espera(cod_anden),
    )

    # Nota: aquí no hace falta filtrar líneas que no sean de Metro. A
    # diferencia de codLines (que en Sol incluye Cercanías), los trenes que
    # devuelve GetStopsTimes para un andén de Metro son siempre de Metro;
    # comprobado en Sol y en Alonso Martínez.
    #
    # El "enVivo" de cada grupo saldrá siempre a None en Metro, porque sus
    # trenes no traen codIssue. No pasa nada: los tiempos de Metro ya son en
    # tiempo real, así que el panel no tiene nada que advertir.
    grupos_llegadas = agrupar_llegadas(trenes)

    return {
        "estacion": info_estacion["name"],
        "codStop": cod_stop,
        # El filtrado de líneas que no son de Metro vive en
        # lineas_de_metro_de(), que comparte con /metro/parada/{id}/lineas.
        "codLines": lineas_de_metro_de(info_estacion),
        "llegadas": grupos_llegadas,
    }


@app.get("/metro/linea/{cod_line}/vehiculos")
def vehiculos_linea_metro(cod_line: str, cod_stop: str | None = None):
    """
    Devuelve la posición actual de los trenes circulando en una línea,
    en ambos sentidos.

    Ejemplo de uso: GET /metro/linea/4__2___/vehiculos?cod_stop=est_4_323

    IMPORTANTE (verificado contra la API real): GetLineLocation.php NO
    devuelve todos los trenes de la línea. Devuelve los ~2 trenes más
    cercanos a la estación que se le pasa en "codStop". Antes aquí se
    usaba siempre paradas_itinerario[0], la PRIMERA parada del itinerario,
    es decir la cabecera de la línea — por eso el mapa mostraba siempre
    los mismos 4 trenes clavados en los dos extremos, sin moverse nunca.

    Por eso aceptamos "cod_stop": la estación que el usuario está mirando
    ahora mismo. Así los trenes que se pintan en el mapa son los que de
    verdad se acercan a esa estación, y coinciden con los tiempos que se
    ven en el panel de llegadas.

    El parámetro es opcional: si no llega, se mantiene el comportamiento
    anterior (primera parada del itinerario), para que la ruta siga
    funcionando si se llama a mano desde el navegador o con curl.
    """
    # Solo líneas de Metro que existan. Sin esta comprobación, un código
    # cualquiera llegaba hasta el CRTM, que responde {"lines": {}}, y
    # obtener_info_linea lanzaba un KeyError. Ese KeyError NO es un
    # RequestException, así que se saltaba el manejador que convierte los
    # fallos de API externa en 503 y salía un 500 pelado, que además miente:
    # no está roto el servidor, es que la línea pedida no existe.
    #
    # Es la misma validación que /parada/{stop_id} hace con las paradas, y
    # usa la misma fuente de verdad que lineas_de_metro_de(): los colores de
    # Metro, que salen de su routes.txt.
    colores_lineas = cargar_colores_lineas_metro()

    if cod_line not in colores_lineas:
        raise HTTPException(status_code=404, detail="Línea de Metro desconocida")

    # El frontend maneja ids de ESTACIÓN ("est_4_323"), pero la API del
    # CRTM solo entiende ids de ANDÉN ("4_323"). Hacemos aquí la misma
    # traducción que en /metro/parada/{cod_stop}, en vez de obligar al
    # frontend a conocer los codAnden.
    cod_anden_pedido = None
    if cod_stop is not None:
        estacion = PARADAS_POR_ID.get(cod_stop)
        if estacion is not None:
            cod_anden_pedido = estacion.get("codAnden")

    info_linea = obtener_info_linea(cod_line)
    itinerarios = info_linea["itinerary"]["Itinerary"]

    vehiculos_totales = []
    for itinerario in itinerarios:
        paradas_itinerario = itinerario["stops"].get("StopInformation", [])
        if isinstance(paradas_itinerario, dict):
            paradas_itinerario = [paradas_itinerario]

        if not paradas_itinerario and cod_anden_pedido is None:
            # Si un itinerario no trae ninguna parada en su respuesta y
            # tampoco nos han pedido una estación concreta, no podemos
            # rellenar el parámetro cod_stop que pide la API, así que
            # saltamos este sentido en vez de fallar todo el endpoint.
            continue

        # La estación que mira el usuario manda; la cabecera del itinerario
        # queda solo como respaldo para cuando no se pasa cod_stop.
        parada_de_referencia = (
            cod_anden_pedido
            if cod_anden_pedido is not None
            else paradas_itinerario[0]["codStop"]
        )

        vehiculos = obtener_posicion_trenes(
            mode_cod=info_linea["codMode"],
            cod_itinerary=itinerario["codItinerary"],
            cod_line=cod_line,
            cod_stop=parada_de_referencia,
            direction=itinerario["direction"],
        )
        vehiculos_totales.extend(vehiculos)

    # Ya está garantizado que existe: se comprobó al entrar, antes de gastar
    # ninguna llamada al CRTM.
    color_linea = colores_lineas[cod_line]

    return {
        "linea": info_linea["description"],
        "codLine": cod_line,
        "color": color_linea["color"],
        "colorTexto": color_linea["color_texto"],
        "vehiculos": vehiculos_totales,
    }


@app.get("/metro/lineas/colores")
def colores_lineas_metro(respuesta: Response):
    """
    Devuelve el número y los colores oficiales de todas las líneas de Metro,
    indexados por su código de línea.

    Ejemplo de uso: GET /metro/lineas/colores

        {
            "4__1___": {"numero": "1", "color": "2DBEF0", "color_texto": "FFFFFF"},
            "4__2___": {"numero": "2", "color": "ED1C24", "color_texto": "FFFFFF"},
            ...
        }

    Son 13 líneas y sus colores no cambian nunca, así que el frontend pide
    esto UNA sola vez al arrancar y lo guarda. Así puede pintar el distintivo
    de cualquier línea (por ejemplo los chips de la cabecera de estación) sin
    una petición por línea, y sin tener que duplicar la tabla de colores en
    el código del navegador.

    Los colores vienen en hexadecimal SIN el "#" inicial, tal como los trae
    routes.txt; quien los use tendrá que añadirlo.
    """
    respuesta.headers["Cache-Control"] = CACHE_DATOS_ESTATICOS

    return cargar_colores_lineas_metro()