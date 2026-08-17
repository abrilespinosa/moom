"""
Precalcula lo necesario para calcular rutas con horas de verdad.

Por qué cabe: el GTFS trae 122.030 viajes, pero la mayoría repite el mismo
recorrido con los mismos tiempos entre paradas y solo cambia la hora de
salida. Agrupándolos por ese patrón quedan 12.561, y de cada uno basta con
guardar sus paradas, los segundos que tarda en llegar a cada una desde la
primera, y la lista de horas a las que sale. Son 8,7 MB, o 1,6 comprimidos:
del mismo orden que el resto del precálculo, así que no hace falta ninguna
base de datos.

Genera backend/data/precalculado/rutas.json con tres partes:

  servicios  service_id -> qué días circula y entre qué fechas. Una salida
             de las 8:00 no vale si su servicio es "solo sábados".
  patrones   los 12.561 recorridos con sus tiempos y sus horas de salida.
  enlaces    pares de paradas a menos de 400 m, con la distancia. Es lo que
             permite trasbordar entre dos líneas que no comparten parada
             pero se tocan a la vuelta de la esquina.

Uso (desde la raíz, como todo lo que importa gtfs_loader):

    python -m scripts.precalcular_rutas

Hay que volver a ejecutarlo con cada volcado GTFS nuevo, igual que
precalcular_datos.py.
"""

import csv
import json
import math
import os
from collections import defaultdict

from backend.gtfs_loader import (
    DIRECTORIO_PRECALCULADO,
    FUENTES_GTFS,
    _estacion_de_cada_anden,
    cargar_todas_las_paradas,
)

# Radio para considerar que se puede ir andando de una parada a otra. 400 m
# son unos 6 minutos con el rodeo que aplica el frontend: más que eso deja
# de parecer un trasbordo y empieza a parecer otro viaje.
RADIO_ENLACE_METROS = 400

DIAS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _segundos(hora):
    """
    "14:05:00" -> 50700.

    El GTFS permite horas por encima de 24 para los viajes que cruzan la
    medianoche ("25:10:00" es la 1:10 del día siguiente), y esta cuenta las
    mantiene crecientes, que es justo lo que necesita el planificador para
    comparar horarios sin casos especiales.
    """
    h, m, s = hora.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def _cargar_servicios(carpeta, encoding, prefijo):
    """
    Qué días circula cada servicio, como máscara de 7 bits (lunes = bit 0).

    calendar_dates.txt añade y quita fechas sueltas —festivos, sobre todo—
    y se guarda aparte para poder corregir el día concreto que se consulte.
    """
    servicios = {}

    with open(f"{carpeta}/calendar.txt", encoding=encoding) as archivo:
        for fila in csv.DictReader(archivo):
            mascara = 0
            for i, dia in enumerate(DIAS):
                if fila[dia] == "1":
                    mascara |= 1 << i

            servicios[f"{prefijo}:{fila['service_id']}"] = {
                "d": mascara,
                "desde": fila["start_date"],
                "hasta": fila["end_date"],
                "mas": [],
                "menos": [],
            }

    excepciones = f"{carpeta}/calendar_dates.txt"
    if os.path.exists(excepciones):
        with open(excepciones, encoding=encoding) as archivo:
            for fila in csv.DictReader(archivo):
                clave = f"{prefijo}:{fila['service_id']}"
                if clave not in servicios:
                    continue
                # 1 = ese día sí circula; 2 = ese día no.
                destino = "mas" if fila["exception_type"] == "1" else "menos"
                servicios[clave][destino].append(fila["date"])

    return servicios


def _patrones_de_la_fuente(fuente, carpeta, encoding):
    """
    Agrupa los viajes de una fuente por recorrido y tiempos relativos.

    Dos viajes de la línea 27 que paran en lo mismo y tardan lo mismo entre
    paradas son el mismo patrón aunque salgan a horas distintas: se guarda
    una vez y se le cuelgan las dos salidas.
    """
    trip_meta = {}
    with open(f"{carpeta}/trips.txt", encoding=encoding) as archivo:
        for fila in csv.DictReader(archivo):
            trip_meta[fila["trip_id"]] = (fila["route_id"], fila["service_id"])

    # Ventanas de frecuencia, que son las que de verdad dicen cuándo pasa un
    # vehículo en EMT y en Metro.
    #
    # Estas dos redes no publican horario sino intervalos: "de 7:00 a 9:00,
    # uno cada 630 segundos". Sus filas de stop_times traen UNA hora nominal
    # por viaje, que solo sirve para saber cuánto se tarda entre paradas, no
    # a qué hora sale nada. Tomarla como salida real dejaba a Metro con 120
    # pasos en todo el día, y el planificador mandaba en autobús a sitios a
    # los que se va en metro en veinte minutos.
    #
    # El interurbano es al revés: no tiene ni una fila aquí y sus horas de
    # stop_times sí son las buenas.
    frecuencias = defaultdict(list)
    archivo_frecuencias = f"{carpeta}/frequencies.txt"
    if os.path.exists(archivo_frecuencias):
        with open(archivo_frecuencias, encoding=encoding) as archivo:
            for fila in csv.DictReader(archivo):
                paso = int(fila["headway_secs"])
                if paso > 0:
                    frecuencias[fila["trip_id"]].append(
                        (
                            _segundos(fila["start_time"]),
                            _segundos(fila["end_time"]),
                            paso,
                        )
                    )

    viajes = defaultdict(list)
    with open(f"{carpeta}/stop_times.txt", encoding=encoding) as archivo:
        lector = csv.reader(archivo)
        cabecera = next(lector)
        i_trip, i_salida, i_parada, i_orden = (
            cabecera.index(c)
            for c in ("trip_id", "departure_time", "stop_id", "stop_sequence")
        )
        # csv.reader y no DictReader: son 3,1 M de filas y construir un
        # diccionario por fila cuesta más que todo lo demás junto.
        for fila in lector:
            viajes[fila[i_trip]].append(
                (int(fila[i_orden]), fila[i_parada], fila[i_salida])
            )

    # Los recorridos de Metro vienen en andenes; el resto de la aplicación
    # trabaja en estaciones, así que hay que traducirlos o ningún id casará
    # con los de /paradas.
    traduccion = _estacion_de_cada_anden(carpeta, encoding) if fuente == "METRO" else {}

    agrupados = defaultdict(lambda: {"salidas": set(), "ventanas": set()})
    for trip, filas in viajes.items():
        if trip not in trip_meta:
            continue

        filas.sort()
        ruta, servicio = trip_meta[trip]
        base = _segundos(filas[0][2])

        paradas = tuple(traduccion.get(p, p) for _, p, _ in filas)
        tiempos = tuple(_segundos(t) - base for _, _, t in filas)

        grupo = agrupados[(ruta, paradas, tiempos)]

        if trip in frecuencias:
            for inicio, fin, paso in frecuencias[trip]:
                grupo["ventanas"].add((inicio, fin, paso, f"{fuente}:{servicio}"))
        else:
            grupo["salidas"].add((base, f"{fuente}:{servicio}"))

    patrones = []
    for (ruta, paradas, tiempos), grupo in agrupados.items():
        patrones.append(
            {
                "l": f"{fuente}-{ruta}",
                "p": list(paradas),
                "t": list(tiempos),
                # Salidas sueltas, ordenadas por hora: el planificador las
                # busca por bisección. Solo las usa el interurbano.
                "s": sorted(grupo["salidas"]),
                # Ventanas [desde, hasta, cada cuánto, servicio]. Las de EMT
                # y Metro; de aquí se calcula el próximo paso sin guardar
                # una fila por vehículo.
                "f": sorted(grupo["ventanas"]),
            }
        )

    return patrones


def _enlaces_a_pie(paradas):
    """
    Pares de paradas a menos de RADIO_ENLACE_METROS, con su distancia.

    Se resuelve con una rejilla: se mete cada parada en una celda del tamaño
    del radio y solo se comparan las de celdas contiguas. Comparar las
    13.542 contra todas serían 183 millones de parejas; así son 67.500
    enlaces en una décima de segundo.
    """
    lado = RADIO_ENLACE_METROS / 111320  # grados que mide un lado de celda

    rejilla = defaultdict(list)
    for parada in paradas:
        rejilla[(int(parada["lat"] / lado), int(parada["lon"] / lado))].append(parada)

    def metros(a, b):
        radio_tierra = 6371000
        rad = math.radians
        dlat = rad(b["lat"] - a["lat"])
        dlon = rad(b["lon"] - a["lon"])
        x = (
            math.sin(dlat / 2) ** 2
            + math.cos(rad(a["lat"])) * math.cos(rad(b["lat"])) * math.sin(dlon / 2) ** 2
        )
        return radio_tierra * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x))

    enlaces = defaultdict(list)
    for parada in paradas:
        celda = (int(parada["lat"] / lado), int(parada["lon"] / lado))

        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for vecina in rejilla.get((celda[0] + dx, celda[1] + dy), []):
                    if vecina["id"] == parada["id"]:
                        continue

                    distancia = metros(parada, vecina)
                    if distancia <= RADIO_ENLACE_METROS:
                        enlaces[parada["id"]].append([vecina["id"], round(distancia)])

    # En orden de cercanía: el planificador prueba primero los trasbordos
    # más cortos, que son los que dan mejores rutas.
    for lista in enlaces.values():
        lista.sort(key=lambda x: x[1])

    return enlaces


if __name__ == "__main__":
    os.makedirs(DIRECTORIO_PRECALCULADO, exist_ok=True)

    servicios = {}
    patrones = []

    for fuente, carpeta, encoding in FUENTES_GTFS:
        faltan = [
            nombre
            for nombre in ("trips.txt", "stop_times.txt", "calendar.txt")
            if not os.path.exists(f"{carpeta}/{nombre}")
        ]
        if faltan:
            print(f"[rutas] {fuente}: falta {', '.join(faltan)}. Se omite.")
            continue

        servicios.update(_cargar_servicios(carpeta, encoding, fuente))
        propios = _patrones_de_la_fuente(fuente, carpeta, encoding)
        patrones.extend(propios)
        print(f"  {fuente}: {len(propios)} patrones")

    datos = {
        "servicios": servicios,
        "patrones": patrones,
        "enlaces": _enlaces_a_pie(cargar_todas_las_paradas()),
    }

    ruta = os.path.join(DIRECTORIO_PRECALCULADO, "rutas.json")
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, separators=(",", ":"))

    print(
        f"{ruta}: {len(patrones)} patrones, {len(servicios)} servicios, "
        f"{sum(len(v) for v in datos['enlaces'].values())} enlaces a pie, "
        f"{os.path.getsize(ruta) / 1e6:.1f} MB"
    )
