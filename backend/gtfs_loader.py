import csv
import json
import os

# Los datos ya precalculados por scripts/precalcular_datos.py.
#
# La ruta se construye desde __file__ y NO relativa al directorio de trabajo,
# a diferencia del resto de rutas de este archivo. El motivo es el despliegue:
# en un entorno serverless el directorio de trabajo no está garantizado, así
# que "backend/data/..." solo funciona por la convención de arrancar siempre
# desde la raíz, que aquí no se puede sostener. Las rutas del GTFS crudo se
# quedan como estaban porque solo se leen en local, al regenerar el JSON.
DIRECTORIO_PRECALCULADO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "precalculado"
)


def _leer_precalculado(nombre):
    """
    Devuelve el contenido del JSON precalculado, o None si no está.

    Que falte no es un error: en local, con el GTFS completo descargado, se
    puede trabajar sin haberlo generado nunca. Quien lo necesita de verdad es
    el despliegue, donde los archivos pesados del GTFS no existen.
    """
    ruta = os.path.join(DIRECTORIO_PRECALCULADO, nombre)

    if not os.path.exists(ruta):
        return None

    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)

def cargar_paradas_emt():
    paradas = []
 
    with open("backend/data/emt/stops.txt", encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)
 
        for fila in lector:
            parada = {
                "id": fila["stop_id"],
                "nombre": fila["stop_name"],
                "lat": float(fila["stop_lat"]),
                "lon": float(fila["stop_lon"]),
                "fuente": "EMT",
            }
            paradas.append(parada)
 
    return paradas
 
 
def cargar_paradas_crtm():
    paradas = []
 
    with open("backend/data/crtm/stops.txt", encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)
 
        for fila in lector:
            parada = {
                "id": fila["stop_id"],
                "nombre": fila["stop_name"],
                "lat": float(fila["stop_lat"]),
                "lon": float(fila["stop_lon"]),
                "fuente": "CRTM",
            }
            paradas.append(parada)
 
    return paradas


def cargar_paradas_metro():
    """
    Carga las estaciones de Metro desde el GTFS del CRTM.

    A diferencia de stops.txt de EMT/CRTM-bus, el GTFS de Metro tiene una
    jerarquía de dos niveles (definida por la propia especificación GTFS,
    campo "location_type"):

    - location_type "0": un andén individual, uno por cada línea que pasa
      por la estación (ej. Sol tiene 3 filas con location_type 0, una por
      cada línea 1/2/3 que para ahí).
    - location_type "1": la estación en sí, que agrupa a sus andenes. Es
      la fila que nos interesa para pintar "una estación = un punto en
      el mapa", en vez de tener 3 marcadores superpuestos en Sol.

    PROBLEMA DESCUBIERTO AL PROBAR CONTRA LA API EN VIVO: el "id" de la
    estación (location_type 1, ej. "est_4_13") NO es un código que la
    API del CRTM reconozca para pedir tiempos de espera (GetStops.php
    le devuelve {"stops": {}}, vacío). La API solo entiende códigos de
    ANDÉN (location_type 0, ej. "par_4_13"). Por eso cada estación
    necesita guardar también su "codAnden": el id de andén que se usará
    al llamar a la API, distinto de "id" (que sigue siendo el de la
    estación, usado para pintar el punto en el mapa).

    Cómo resolvemos "codAnden", verificado con datos reales:
    1. Para el 94.6% de las estaciones (227 de 240): basta con cambiar
       el prefijo "est_" por "par_" en el propio id (ej. "est_4_13" ->
       "par_4_13"); el resto del código coincide siempre.
    2. Para los 13 grandes intercambiadores (prefijo "est_90_...", ej.
       Sol, Chamartín, Atocha): esa transformación simple no funciona,
       porque su numeración no coincide con la de sus andenes. Para
       estos usamos el campo GTFS "parent_station" de los propios
       andenes, que sí los vincula correctamente. Si una estación así
       tiene varios andenes (ej. Sol tiene 3, uno por línea 1/2/3),
       nos quedamos con el primero, y eso NO pierde información:
       comprobado contra la API, GetStopsTimes es consciente de la
       ESTACIÓN y no del andén, así que preguntando por cualquier andén
       de Sol devuelve las llegadas de sus tres líneas. Guardar un solo
       codAnden por estación es suficiente.
    """
    paradas = []

    # Este archivo concreto viene con BOM (marca invisible al principio del
    # archivo, probablemente añadida por el portal del CRTM al exportarlo).
    # "utf-8-sig" le dice a Python que la detecte y la descarte, para que
    # la primera columna se lea como "stop_id" y no como "\ufeffstop_id".
    with open("backend/data/metro/stops.txt", encoding="utf-8-sig") as archivo:
        filas = list(csv.DictReader(archivo))

    # Primera pasada: construimos un mapa parent_station -> [andenes],
    # solo con los andenes que sí declaran su estación padre. Lo usamos
    # como fallback para los 13 intercambiadores que no siguen el
    # patrón simple de numeración.
    andenes_por_estacion_padre = {}
    for fila in filas:
        if fila["location_type"] == "0" and fila["parent_station"]:
            andenes_por_estacion_padre.setdefault(
                fila["parent_station"], []
            ).append(fila["stop_id"])

    # Para poder comprobar si la transformación simple "est_ -> par_"
    # corresponde a un andén que realmente existe en el archivo.
    ids_existentes = {fila["stop_id"] for fila in filas}

    for fila in filas:
        if fila["location_type"] != "1":
            continue

        cod_estacion = fila["stop_id"]

        # Estrategia 1: cambiar el prefijo y comprobar que ese andén existe.
        candidato_simple = cod_estacion.replace("est_", "par_", 1)

        if candidato_simple in ids_existentes:
            cod_anden = candidato_simple
        else:
            # Estrategia 2 (fallback): buscar por parent_station, y
            # quedarnos con el primer andén de la lista si hay varios.
            andenes = andenes_por_estacion_padre.get(cod_estacion)
            cod_anden = andenes[0] if andenes else None

        # IMPORTANTE: verificado contra la API real (GetStops.php), el
        # CRTM solo reconoce el formato "modo_número" sin prefijo, por
        # ejemplo "4_323". Los ids del GTFS vienen con un prefijo
        # ("par_4_323", "est_4_323") que es interno del propio fichero
        # GTFS y que la API no entiende, así que lo quitamos aquí antes
        # de guardarlo, en vez de dejar que cada llamada a la API falle.
        if cod_anden is not None:
            cod_anden = cod_anden.replace("par_", "", 1).replace("est_", "", 1)
        parada = {
            "id": cod_estacion,
            "codAnden": cod_anden,
            "nombre": fila["stop_name"],
            "lat": float(fila["stop_lat"]),
            "lon": float(fila["stop_lon"]),
            "fuente": "METRO",
        }
        paradas.append(parada)

    # Tercera estrategia: andenes HUÉRFANOS, sin fila de estación.
    #
    # Dos andenes del volcado del CRTM no tienen estación asociada por
    # ninguno de los dos caminos anteriores: Noviciado (par_4_38) y Acacias
    # (par_4_92). No existe "est_4_38" ni "est_4_92", y tampoco declaran
    # parent_station. Es un hueco del propio GTFS, no de esta función.
    #
    # Sin esto, esas dos estaciones desaparecían del mapa y del recorrido de
    # sus líneas, pese a ser estaciones normales y corrientes en servicio: se
    # comprobó contra la API del CRTM que reconoce sus códigos (4_38 y 4_92)
    # y devuelve llegadas. Así que las reconstruimos a partir de su propio
    # andén, que ya trae nombre y coordenadas, y les damos el id sintético
    # que les correspondería. Ambos están libres, no pisan a ninguna otra.
    for fila in filas:
        if fila["location_type"] != "0":
            continue

        anden = fila["stop_id"]
        candidato = anden.replace("par_", "est_", 1)
        tiene_estacion = candidato in ids_existentes or fila["parent_station"]

        if not tiene_estacion:
            paradas.append(
                {
                    "id": candidato,
                    "codAnden": anden.replace("par_", "", 1),
                    "nombre": fila["stop_name"],
                    "lat": float(fila["stop_lat"]),
                    "lon": float(fila["stop_lon"]),
                    "fuente": "METRO",
                }
            )

    return paradas


# Decimales que se conservan de cada coordenada. Cinco dan algo menos de un
# metro de precisión en Madrid, de sobra para clavar una marquesina.
#
# Los GTFS traen 13 decimales de mediana, que es precisión de nanómetro y
# solo sirve para engordar la respuesta: son 13.542 paradas con dos
# coordenadas cada una, y recortarlas quita el 25% del peso que viaja por la
# red (330 KB -> 247 KB ya comprimido).
DECIMALES_COORDENADAS = 5


def _paradas_desde_gtfs():
    paradas = cargar_paradas_emt() + cargar_paradas_crtm() + cargar_paradas_metro()

    for parada in paradas:
        parada["lat"] = round(parada["lat"], DECIMALES_COORDENADAS)
        parada["lon"] = round(parada["lon"], DECIMALES_COORDENADAS)

    return paradas


def cargar_todas_las_paradas():
    """
    Las paradas de las tres redes, del JSON precalculado si lo hay.

    Leerlas del GTFS crudo cuesta bastante más que leer el JSON, pero la
    razón de preferir el precalculado no es la velocidad: es que en un
    despliegue los stops.txt podrían no estar, y que así producción y local
    sirven exactamente los mismos datos.
    """
    return _leer_precalculado("paradas.json") or _paradas_desde_gtfs()


def cargar_horarios():
    """
    Los horarios de paso por línea, del JSON precalculado.

    Devuelve {} si no está: los horarios son un añadido, no algo sin lo que la
    aplicación deje de funcionar, así que el endpoint responde "no disponible"
    en vez de impedir que arranque el servidor.

    Lo genera scripts/precalcular_horarios.py, que es donde está explicado por
    qué el CRTM da horas y EMT y Metro dan frecuencias.
    """
    return _leer_precalculado("horarios.json") or {}


# Caché en memoria: igual que las paradas, los colores de las líneas no
# cambian durante la ejecución del servidor, así que los cargamos una
# sola vez la primera vez que se pidan y reutilizamos el resultado.
_cache_colores_lineas_metro = None


def cargar_colores_lineas_metro():
    """
    Carga, desde el GTFS de Metro, el color oficial de cada línea.

    routes.txt trae una fila por línea, con su código (route_id, el mismo
    formato "4__2___" que usa la API en vivo como codLine), su número
    visible (route_short_name) y sus colores en hexadecimal SIN el "#"
    inicial (route_color para el fondo, route_text_color para el texto
    que va encima, pensado para que se siga leyendo bien sobre ese fondo
    - por ejemplo la Línea 3 es amarilla con texto negro, no blanco).

    Devuelve un diccionario indexado por route_id, por ejemplo:
        {
            "4__2___": {"numero": "2", "color": "ED1C24", "color_texto": "FFFFFF"},
            ...
        }
    para que el backend pueda hacer una simple consulta por codLine, sin
    tener que leer el archivo otra vez ni recorrer una lista cada vez.
    """
    global _cache_colores_lineas_metro

    if _cache_colores_lineas_metro is not None:
        return _cache_colores_lineas_metro

    # Igual que las paradas y las líneas, esto también se precalcula: son
    # datos estáticos y leerlos de routes.txt obligaría a llevar el GTFS de
    # Metro al despliegue solo por este archivo. Se descubrió desplegando:
    # sin esta rama, /metro/lineas/colores y todo lo que pasa por
    # lineas_de_metro_de() reventaban con FileNotFoundError en producción.
    precalculado = _leer_precalculado("colores_metro.json")

    _cache_colores_lineas_metro = (
        precalculado if precalculado is not None else _colores_metro_desde_gtfs()
    )

    return _cache_colores_lineas_metro


def _colores_metro_desde_gtfs():
    colores = {}

    with open("backend/data/metro/routes.txt", encoding="utf-8-sig") as archivo:
        lector = csv.DictReader(archivo)

        for fila in lector:
            colores[fila["route_id"]] = {
                "numero": fila["route_short_name"],
                "color": fila["route_color"],
                "color_texto": fila["route_text_color"],
            }

    return colores

# Las tres fuentes, con la codificación que necesita el GTFS de cada una.
# Solo el de Metro trae BOM (ver cargar_paradas_metro).
FUENTES_GTFS = [
    ("EMT", "backend/data/emt", "utf-8"),
    ("CRTM", "backend/data/crtm", "utf-8"),
    ("METRO", "backend/data/metro", "utf-8-sig"),
]


def _recorridos_de_la_fuente(carpeta, encoding):
    """
    Devuelve, para una fuente, el recorrido de cada línea y sentido:
        { route_id: [ {"sentido": "0", "destino": "...", "paradas": [ids...]} ] }

    El GTFS no guarda "las paradas de la línea 27" en ningún sitio. Guarda
    decenas de miles de VIAJES (cada salida concreta de cada día), y cada
    viaje tiene su lista de paradas en stop_times.txt. Para dibujar el
    recorrido nos vale con UN viaje por línea y sentido, así que de los
    72.511 viajes de la EMT solo nos interesan unos 460.

    Ese filtrado es lo que hace esto viable: stop_times.txt tiene 1,9
    millones de filas y pesa 80 MB, pero al quedarnos solo con los viajes
    representativos una única pasada basta y tarda medio segundo.
    """
    # Primera pasada: un viaje representativo por (línea, sentido).
    representantes = {}  # (route_id, direction_id) -> trip_id
    destinos = {}  # trip_id -> letrero del viaje ("Plaza Castilla")

    with open(f"{carpeta}/trips.txt", encoding=encoding) as archivo:
        for fila in csv.DictReader(archivo):
            clave = (fila["route_id"], fila.get("direction_id", "0"))
            if clave not in representantes:
                representantes[clave] = fila["trip_id"]
                destinos[fila["trip_id"]] = fila.get("trip_headsign", "")

    viajes_que_interesan = set(representantes.values())

    # Segunda pasada: recogemos las paradas de esos viajes.
    #
    # Usamos csv.reader y no DictReader a propósito: DictReader construye un
    # diccionario por fila, y con casi dos millones de filas esa diferencia
    # se nota. Aquí solo necesitamos tres columnas, que localizamos una vez
    # por su nombre en la cabecera.
    secuencias = {}  # trip_id -> [(orden, stop_id)]

    with open(f"{carpeta}/stop_times.txt", encoding=encoding) as archivo:
        lector = csv.reader(archivo)
        cabecera = next(lector)
        i_viaje = cabecera.index("trip_id")
        i_parada = cabecera.index("stop_id")
        i_orden = cabecera.index("stop_sequence")

        for fila in lector:
            if fila[i_viaje] in viajes_que_interesan:
                secuencias.setdefault(fila[i_viaje], []).append(
                    (int(fila[i_orden]), fila[i_parada])
                )

    recorridos = {}
    for (route_id, sentido), viaje in representantes.items():
        # stop_sequence no tiene por qué venir ordenado en el archivo, así
        # que ordenamos por él antes de quedarnos con los ids.
        paradas = [parada for _, parada in sorted(secuencias.get(viaje, []))]

        if paradas:
            recorridos.setdefault(route_id, []).append(
                {
                    "sentido": sentido,
                    "destino": destinos.get(viaje, ""),
                    "paradas": paradas,
                }
            )

    return recorridos


def _estacion_de_cada_anden(carpeta, encoding):
    """
    Devuelve { id_de_andén -> id_de_estación } para el GTFS de Metro.

    Hace falta porque los recorridos de Metro vienen en andenes y todo lo
    demás en la aplicación (el mapa, /paradas, los paneles) trabaja con
    estaciones. Sin esta traducción, las paradas de una línea de Metro no
    se podrían casar con ningún punto del mapa.

    Es el camino inverso al de cargar_paradas_metro, y usa las tres mismas
    estrategias: el prefijo "par_" -> "est_" para la gran mayoría, el campo
    parent_station para los grandes intercambiadores (cuya numeración no
    coincide con la de sus andenes), y el id sintético para los dos andenes
    huérfanos que no tienen ni lo uno ni lo otro.
    """
    with open(f"{carpeta}/stops.txt", encoding=encoding) as archivo:
        filas = list(csv.DictReader(archivo))

    estaciones = {f["stop_id"] for f in filas if f["location_type"] == "1"}
    mapa = {}

    for fila in filas:
        if fila["location_type"] != "0":
            continue

        anden = fila["stop_id"]
        candidato = anden.replace("par_", "est_", 1)

        if candidato in estaciones:
            mapa[anden] = candidato
        elif fila["parent_station"]:
            mapa[anden] = fila["parent_station"]
        else:
            # Andén huérfano: no hay fila de estación en el GTFS. Apuntamos
            # al id sintético que cargar_paradas_metro le fabrica a partir
            # de este mismo andén, para que el recorrido de su línea lo
            # incluya igual que el mapa.
            mapa[anden] = candidato

    return mapa


def _andenes_a_estaciones(recorridos, mapa):
    """
    Reescribe los recorridos de Metro para que hablen de estaciones.

    Además quita repeticiones seguidas: si dos andenes consecutivos de un
    itinerario pertenecen a la misma estación, en el mapa es un único punto
    y listarlo dos veces sería confuso.

    Noviciado y Acacias, cuyos andenes no tienen fila de estación en el
    volcado del CRTM, SÍ salen aquí: el mapa que recibe esta función les
    asigna el id sintético que cargar_paradas_metro les fabrica, así que
    aparecen en el recorrido de su línea igual que en el mapa.

    Queda el aviso por consola para los andenes que ni siquiera están en
    stops.txt (los recorridos salen de stop_times.txt, y los dos volcados no
    siempre van a la par). Esos sí se descartan, porque no hay de dónde
    sacar sus coordenadas.
    """
    huerfanos = set()

    for sentidos in recorridos.values():
        for sentido in sentidos:
            estaciones = []
            for anden in sentido["paradas"]:
                estacion = mapa.get(anden)
                if estacion is None:
                    huerfanos.add(anden)
                    continue
                # Solo saltamos la repetición si es consecutiva: una línea
                # circular puede pasar dos veces por la misma estación de
                # forma legítima, y eso hay que conservarlo.
                if not estaciones or estaciones[-1] != estacion:
                    estaciones.append(estacion)
            sentido["paradas"] = estaciones

    if huerfanos:
        print(
            f"[lineas] METRO: {len(huerfanos)} andenes sin estación en el GTFS, "
            f"se omiten de los recorridos: {', '.join(sorted(huerfanos))}"
        )

    return recorridos


def cargar_lineas():
    """
    Las líneas con su recorrido, del JSON precalculado si lo hay.

    Es el caso que de verdad justifica el precálculo: construir esto lee
    trips.txt y stop_times.txt (1,9 M de filas, 188 MB), que no van al
    repositorio. Sin el JSON, un clon limpio o un despliegue se quedan sin
    búsqueda por línea. Ver scripts/precalcular_datos.py.
    """
    return _leer_precalculado("lineas.json") or _lineas_desde_gtfs()


def _lineas_desde_gtfs():
    """
    Carga todas las líneas de las tres redes con su recorrido de paradas.

    Devuelve una lista de diccionarios:
        {
            "id": "EMT-027",          # único entre fuentes, sirve de ruta URL
            "numero": "27",           # el que ve el viajero
            "nombre": "Plaza Castilla - Embajadores",
            "fuente": "EMT",
            "color": "0178BC",
            "colorTexto": "FFFFFF",
            "sentidos": [ {"destino": ..., "paradas": [ids...]}, ... ]
        }

    Las líneas sin ningún viaje en el volcado se incluyen igual, con
    "sentidos" vacío. Son 21 y antes se descartaban, dando por hecho que
    eran servicios estacionales o especiales que ahora no circulan.

    Eso explica como mucho una parte: la F, la G y la U de la EMT son las
    líneas universitarias, y la SE721 es el servicio especial del estadio.
    Pero también falta la LÍNEA 3 DE METRO y una docena de interurbanas
    normales de la zona de Colmenar Viejo, que circulan a diario. Y el
    calendario de este volcado no distingue temporadas: solo tiene tres
    servicios (laborable, sábado y festivo) del 24-07-2026 al 31-12-2026,
    o sea que ni siquiera hay un periodo estacional en el que apoyarse.
    Sea cual sea el motivo, en trips.txt no hay ni una fila suya.

    Descartarlas las hacía desaparecer del buscador, que es peor que
    enseñarlas sin recorrido: sus paradas sí están en el mapa y sus tiempos
    en vivo funcionan, así que lo único que falta es la lista ordenada de
    paradas. Quien las abre ve un aviso en lugar del recorrido.

    Si faltan los archivos pesados de una fuente (trips.txt y stop_times.txt
    no están en el repositorio por su tamaño), esa fuente se salta con un
    aviso en vez de impedir que arranque el servidor: el resto de la
    aplicación funciona igual sin la búsqueda por línea.
    """
    lineas = []

    for fuente, carpeta, encoding in FUENTES_GTFS:
        faltan = [
            nombre
            for nombre in ("trips.txt", "stop_times.txt")
            if not os.path.exists(f"{carpeta}/{nombre}")
        ]
        if faltan:
            print(
                f"[lineas] {fuente}: falta {', '.join(faltan)} en {carpeta}. "
                f"Se omite esta fuente. Normalmente esto no debería verse: "
                f"las líneas salen de backend/data/precalculado/lineas.json, "
                f"que sí va al repositorio. Si necesitas regenerarlo, "
                f"descarga el GTFS completo a mano de los portales de datos "
                f"abiertos de EMT y del CRTM y ejecuta "
                f"'python -m scripts.precalcular_datos'."
            )
            continue

        recorridos = _recorridos_de_la_fuente(carpeta, encoding)

        # Los recorridos de Metro vienen en andenes; el resto de la
        # aplicación trabaja con estaciones.
        if fuente == "METRO":
            recorridos = _andenes_a_estaciones(
                recorridos, _estacion_de_cada_anden(carpeta, encoding)
            )

        with open(f"{carpeta}/routes.txt", encoding=encoding) as archivo:
            for fila in csv.DictReader(archivo):
                lineas.append(
                    {
                        "id": f"{fuente}-{fila['route_id']}",
                        "numero": fila["route_short_name"],
                        "nombre": fila["route_long_name"],
                        "fuente": fuente,
                        "color": fila.get("route_color") or None,
                        "colorTexto": fila.get("route_text_color") or None,
                        "sentidos": recorridos.get(fila["route_id"], []),
                    }
                )

    return lineas


if __name__ == "__main__":
    paradas_emt = cargar_paradas_emt()
    paradas_crtm = cargar_paradas_crtm()
    paradas_metro = cargar_paradas_metro()
 
    print(f"Paradas EMT: {len(paradas_emt)}")
    print(paradas_emt[0])
 
    print(f"Paradas CRTM: {len(paradas_crtm)}")
    print(paradas_crtm[0])

    print(f"Estaciones Metro: {len(paradas_metro)}")
    print(paradas_metro[0])