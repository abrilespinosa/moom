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

def cargar_todas_las_paradas():
    return cargar_paradas_emt() + cargar_paradas_crtm()

if __name__ == "__main__":
    paradas_emt = cargar_paradas_emt()
    paradas_crtm = cargar_paradas_crtm()
 
    print(f"Paradas EMT: {len(paradas_emt)}")
    print(paradas_emt[0])
 
    print(f"Paradas CRTM: {len(paradas_crtm)}")
    print(paradas_crtm[0])