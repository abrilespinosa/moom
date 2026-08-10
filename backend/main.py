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
from backend.gtfs_loader import cargar_todas_las_paradas, cargar_colores_lineas_metro
from backend.metro_client import (
    obtener_info_estacion,
    obtener_info_linea,
    obtener_tiempos_espera,
    obtener_posicion_trenes,
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

@app.get("/paradas")
def listar_paradas():
    """
    Devuelve todas las paradas de la red EMT (id, nombre, lat, lon).
    """
    return PARADAS

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

    Ejemplo de uso: GET /parada/72

    Nota CRTM: las paradas interurbanas (id con formato "par_8_XXXXX")
    no tienen API pública de tiempo real conocida (investigado a fondo,
    ver notas del proyecto). Para esos IDs devolvemos un mensaje claro
    en vez de intentar consultar la API de EMT, que no las reconoce y
    devolvería un error.
    """
    if stop_id.startswith("par_"):
        return {
            "tiempo_real_disponible": False,
            "mensaje": "Tiempo real no disponible para esta parada (CRTM).",
        }

    return obtener_llegadas_parada(stop_id)


@app.get("/metro/parada/{cod_stop}")
def tiempos_estacion_metro(cod_stop: str):
    """
    Devuelve los próximos trenes en una estación de Metro, agrupados por
    destino (igual que el panel de la app oficial: un bloque por sentido).

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

    # Agrupamos los trenes en un diccionario cuya clave es el destino
    # (ej. "LAS ROSAS") y cuyo valor es la lista de horas de los trenes
    # que van hacia ese destino, ya ordenados (la API los devuelve en
    # orden porque pedimos orderBy=2).
    trenes_por_destino = {}
    for tren in trenes:
        destino = tren["destination"]
        trenes_por_destino.setdefault(destino, []).append(tren["time"])

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
        "destinos": trenes_por_destino,
    }


@app.get("/metro/linea/{cod_line}/vehiculos")
def vehiculos_linea_metro(cod_line: str):
    """
    Devuelve la posición actual de los trenes circulando en una línea,
    en ambos sentidos.

    Ejemplo de uso: GET /metro/linea/4__2___/vehiculos  (Línea 2)

    Primero pedimos la info de la línea para sacar sus dos itinerarios
    (uno por sentido), y para cada uno llamamos a obtener_posicion_trenes.
    Necesitamos una estación cualquiera de cada itinerario para rellenar
    el parámetro "cod_stop" que la API exige; usamos la primera de la
    lista que ya viene incluida en la respuesta de info de línea.
    """
    info_linea = obtener_info_linea(cod_line)
    itinerarios = info_linea["itinerary"]["Itinerary"]

    vehiculos_totales = []
    for itinerario in itinerarios:
        paradas_itinerario = itinerario["stops"].get("StopInformation", [])
        if isinstance(paradas_itinerario, dict):
            paradas_itinerario = [paradas_itinerario]

        if not paradas_itinerario:
            # Si un itinerario no trae ninguna parada en su respuesta,
            # no podemos rellenar el parámetro cod_stop que pide la API,
            # así que saltamos este sentido en vez de fallar todo el endpoint.
            continue

        primera_parada = paradas_itinerario[0]["codStop"]

        vehiculos = obtener_posicion_trenes(
            mode_cod=info_linea["codMode"],
            cod_itinerary=itinerario["codItinerary"],
            cod_line=cod_line,
            cod_stop=primera_parada,
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