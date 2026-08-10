"""
main.py

Servidor web (API) que expone los datos de EMT Madrid en una URL local,
para que el futuro frontend (mapa en el navegador) pueda consultarlos.

Cómo arrancarlo (desde la raíz del proyecto, en terminal):
    uvicorn backend.main:app --reload

Luego puedes visitar en el navegador, por ejemplo:
    http://127.0.0.1:8000/parada/72
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.emt_client import obtener_llegadas_parada
from backend.gtfs_loader import (
    cargar_todas_las_paradas,
    cargar_colores_lineas_metro,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En desarrollo, permitimos cualquier origen
    allow_methods=["*"],
    allow_headers=["*"],
)

PARADAS = cargar_todas_las_paradas()

# Diccionario id -> parada, para búsquedas rápidas por id en vez de
# recorrer las 13.560 paradas cada vez que el endpoint de Metro necesita
# encontrar el codAnden de una estación.
PARADAS_POR_ID = {parada["id"]: parada for parada in PARADAS}

# Las líneas con su recorrido de paradas, construidas desde el GTFS al
# arrancar (alrededor de un segundo). Si faltan los archivos pesados que no
# van al repositorio, la lista queda vacía y la búsqueda por línea se
# desactiva sola, sin afectar al resto de la aplicación.
LINEAS = cargar_lineas()
LINEAS_POR_ID = {linea["id"]: linea for linea in LINEAS}


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

@app.get("/paradas")
def listar_paradas():
    """
    Devuelve todas las paradas de la red EMT (id, nombre, lat, lon).
    """
    return PARADAS

@app.get("/lineas")
def listar_lineas():
    """
    Devuelve todas las líneas de las tres redes, SIN su recorrido.

    Ejemplo de uso: GET /lineas

    El recorrido se deja fuera a propósito: son casi 30.000 identificadores
    de parada entre las 582 líneas, y el buscador solo necesita el número,
    el nombre y el color para filtrar mientras se escribe. Las paradas se
    piden aparte, ya en /linea/{id}, cuando se elige una concreta.

    El número de línea NO es único entre redes: hay 21 que se repiten, como
    la 1 y la 2, que existen a la vez en EMT y en Metro. Por eso cada línea
    lleva su "fuente", y el "id" la incluye como prefijo.
    """
    return [
        {clave: linea[clave] for clave in linea if clave != "sentidos"}
        for linea in LINEAS
    ]


@app.get("/linea/{cod_linea}")
def recorrido_linea(cod_linea: str):
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
        return {
            "encontrada": False,
            "mensaje": "No se encontró esa línea.",
        }

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
    if stop_id.startswith("par_"):
        # La API del CRTM solo entiende el código sin el prefijo del GTFS:
        # "par_8_06002" -> "8_06002". Misma traducción que en Metro.
        cod_parada = stop_id.replace("par_", "", 1)

        info_parada = obtener_info_estacion(cod_parada)
        llegadas = obtener_tiempos_espera(cod_parada, info_parada["stopType"])

        return {
            "parada": info_parada["name"],
            "codStop": stop_id,
            "llegadas": agrupar_llegadas(llegadas),
        }

    return obtener_llegadas_parada(stop_id)


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

    info_estacion = obtener_info_estacion(cod_anden)
    trenes = obtener_tiempos_espera(cod_anden, info_estacion["stopType"])

    # Nota: aquí no hace falta filtrar líneas que no sean de Metro. A
    # diferencia de codLines (que en Sol incluye Cercanías), los trenes que
    # devuelve GetStopsTimes para un andén de Metro son siempre de Metro;
    # comprobado en Sol y en Alonso Martínez.
    #
    # El "enVivo" de cada grupo saldrá siempre a None en Metro, porque sus
    # trenes no traen codIssue. No pasa nada: los tiempos de Metro ya son en
    # tiempo real, así que el panel no tiene nada que advertir.
    grupos_llegadas = agrupar_llegadas(trenes)

    # En las grandes estaciones de trasbordo, la API devuelve en codLines
    # TODAS las líneas que paran ahí, incluidas las que no son de Metro:
    # Sol, por ejemplo, devuelve además "5__C3___", "5__C4_A__" y
    # "5__C4_B__", que son líneas de Cercanías (el prefijo "5__" es el modo
    # ferroviario; Metro es el "4__").
    #
    # El frontend usa esta lista para pedir los trenes de cada línea a
    # /metro/linea/{codLine}/vehiculos, así que sin filtrar acabaría
    # pidiendo trenes de Cercanías a un endpoint de Metro: hoy devuelven
    # cero vehículos y solo gastan peticiones, pero si algún día trajeran
    # alguno se pintaría en el mapa como si fuera un tren de Metro, con el
    # color azul de respaldo porque no está en routes.txt.
    #
    # Usamos el propio routes.txt de Metro como fuente de verdad de "qué
    # es una línea de Metro", en vez de comprobar el prefijo a mano: así,
    # además, toda línea que devolvemos tiene color garantizado.
    lineas_de_metro = cargar_colores_lineas_metro()
    cod_lines = [
        linea
        for linea in info_estacion["codLines"]["Line"]
        if linea in lineas_de_metro
    ]

    return {
        "estacion": info_estacion["name"],
        "codStop": cod_stop,
        "codLines": cod_lines,
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

    colores_lineas = cargar_colores_lineas_metro()
    color_linea = colores_lineas.get(cod_line, {})

    return {
        "linea": info_linea["description"],
        "codLine": cod_line,
        "color": color_linea.get("color"),
        "colorTexto": color_linea.get("color_texto"),
        "vehiculos": vehiculos_totales,
    }


@app.get("/metro/lineas/colores")
def colores_lineas_metro():
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
    return cargar_colores_lineas_metro()