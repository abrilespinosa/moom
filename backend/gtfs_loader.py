import csv

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
       usamos el primero de la lista como aproximación razonable para
       el MVP: pedir tiempos de todas las líneas a la vez es una mejora
       futura, no bloqueante para que el panel funcione ahora.
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

    return paradas


def cargar_todas_las_paradas():
    return cargar_paradas_emt() + cargar_paradas_crtm() + cargar_paradas_metro()

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