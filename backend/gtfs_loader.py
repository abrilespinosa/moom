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

    Verificado con datos reales: 290 filas con location_type 0 (andenes)
    y 240 con location_type 1 (estaciones), confirmado con el caso de Sol
    (parent_station "est_90_58" agrupa a sus 3 andenes).
    """
    paradas = []

    # Este archivo concreto viene con BOM (marca invisible al principio del
    # archivo, probablemente añadida por el portal del CRTM al exportarlo).
    # "utf-8-sig" le dice a Python que la detecte y la descarte, para que
    # la primera columna se lea como "stop_id" y no como "\ufeffstop_id".
    with open("backend/data/metro/stops.txt", encoding="utf-8-sig") as archivo:
        lector = csv.DictReader(archivo)

        for fila in lector:
            if fila["location_type"] != "1":
                continue

            parada = {
                "id": fila["stop_id"],
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