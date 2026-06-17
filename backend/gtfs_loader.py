import csv

def cargar_paradas():
    paradas = []

    with open("backend/data/stops.txt", encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)

        for fila in lector:
            parada = {
                "id": fila["stop_id"],
                "nombre": fila["stop_name"],
                "lat": float(fila["stop_lat"]),
                "lon": float(fila["stop_lon"]),
            }
            paradas.append(parada)

    return paradas

if __name__ == "__main__":
    paradas = cargar_paradas()
    print(f"Total de paradas: {len(paradas)}")
    print(paradas[0])