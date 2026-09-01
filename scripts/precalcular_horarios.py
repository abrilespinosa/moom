"""
Precalcula los horarios de paso de cada línea, para enseñarlos en el panel.

Por qué existe: es la misma historia que scripts/precalcular_datos.py. Los
horarios viven en stop_times.txt (1,2 M de filas en el CRTM, 1,9 M en EMT) y
esos archivos no van al repositorio. Sin precalcular, un clon limpio y el
despliegue se quedan sin horarios.

    python -m scripts.precalcular_horarios

LO IMPORTANTE, Y NO ES UN DETALLE: las tres redes publican cosas distintas, y
la presentación tiene que respetarlo en vez de fingir que son lo mismo.

- CRTM interurbano: horas de paso REALES. 1,24 M de filas en stop_times y CERO
  en frequencies. Se puede enseñar la tabla de salidas tal cual, como la que
  reparte el propio consorcio.
- EMT y Metro: FRECUENCIAS. Sus salidas reales están en frequencies.txt
  ("de 7:00 a 8:00, uno cada 1920 s"); las filas de stop_times solo sirven
  para saber cuánto se tarda entre paradas. Enseñar "pasa a las 7:03" sería
  inventárselo. Se enseñan intervalos, que es lo que ellos mismos publican.

Y una limitación del origen que hay que declarar, no esconder: 101 de las 340
líneas del CRTM traen un único servicio marcado como "todos los días", así que
para ellas los datos abiertos NO distinguen laborable de sábado ni de domingo.
Se marcan como tales para que el panel pueda decirlo.
"""

import csv
import json
import os
import re
from collections import defaultdict

from backend.gtfs_loader import DIRECTORIO_PRECALCULADO, FUENTES_GTFS

# Nombre legible de cada patrón de días de calendar.txt (L M X J V S D).
NOMBRE_DE_LOS_DIAS = {
    "1111100": "Laborables",
    "1111111": "Todos los días",
    "0000010": "Sábados",
    "0000001": "Domingos y festivos",
    "0000011": "Fines de semana",
    "1111000": "Lunes a jueves",
    "0000100": "Viernes",
    "1111110": "Lunes a sábado",
}

# Orden en el que se enseñan, de más común a menos.
ORDEN_DE_LOS_DIAS = [
    "Laborables",
    "Lunes a jueves",
    "Viernes",
    "Lunes a sábado",
    "Sábados",
    "Fines de semana",
    "Domingos y festivos",
    "Todos los días",
]


def _nombre_de_dias(patron):
    if patron in NOMBRE_DE_LOS_DIAS:
        return NOMBRE_DE_LOS_DIAS[patron]

    # Patrones raros (un servicio que solo circula martes y jueves, por
    # ejemplo): se compone el nombre a partir de las iniciales en vez de
    # descartarlo o de mentir llamándolo "laborables".
    iniciales = "LMXJVSD"
    dias = [iniciales[i] for i, activo in enumerate(patron) if activo == "1"]
    return ", ".join(dias) if dias else "Sin servicio"


def _hora_corta(hora_gtfs):
    """
    '06:00:00' -> '06:00'.

    Se parte por ":" en vez de cortar por posición: el GTFS de EMT escribe las
    horas sin cero delante ("7:00:00"), y suponer una anchura fija reventaba
    justo ahí.

    Las horas pasadas de medianoche (el GTFS usa 25:10 para la 1:10 del día
    siguiente) se normalizan a la del reloj, que es como las lee una persona
    esperando en la parada.
    """
    partes = hora_gtfs.split(":")
    return f"{int(partes[0]) % 24:02d}:{partes[1]}"


def _calendario(carpeta, encoding):
    """service_id -> patrón de días ('1111100')."""
    ruta = f"{carpeta}/calendar.txt"

    if not os.path.exists(ruta):
        return {}

    with open(ruta, encoding=encoding) as archivo:
        return {
            fila["service_id"]: "".join(
                fila[dia]
                for dia in (
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                )
            )
            for fila in csv.DictReader(archivo)
        }


# La hora de salida va incrustada en el trip_id del CRTM
# ("..._1_06:00:00_1_su__1_..."), lo que ahorra recorrer stop_times entero
# solo para saber a qué hora sale cada viaje. Se comprobó contra la tabla
# oficial de la línea 191: las 32 horas distintas coinciden una a una.
_HORA_EN_TRIP_ID = re.compile(r"_(\d{2}:\d{2}:\d{2})_")


def _horarios_reales(carpeta, encoding, calendario):
    """
    Para las fuentes con horas de paso reales (hoy solo el CRTM).

    Devuelve: route_id -> sentido -> patrón de días -> [horas de salida]
    """
    horarios = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

    with open(f"{carpeta}/trips.txt", encoding=encoding) as archivo:
        for fila in csv.DictReader(archivo):
            encontrada = _HORA_EN_TRIP_ID.search(fila["trip_id"])

            if not encontrada:
                continue

            patron = calendario.get(fila["service_id"], "1111111")
            sentido = fila.get("direction_id", "0")

            horarios[fila["route_id"]][sentido][patron].add(
                _hora_corta(encontrada.group(1))
            )

    return horarios


def _horarios_por_frecuencia(carpeta, encoding, calendario):
    """
    Para EMT y Metro, que publican intervalos y no horas.

    Devuelve: route_id -> sentido -> patrón de días -> [franjas]
    """
    # frequencies.txt indexa por trip_id, así que primero hace falta saber de
    # qué línea, sentido y servicio es cada viaje.
    viajes = {}

    with open(f"{carpeta}/trips.txt", encoding=encoding) as archivo:
        for fila in csv.DictReader(archivo):
            viajes[fila["trip_id"]] = (
                fila["route_id"],
                fila.get("direction_id", "0"),
                calendario.get(fila["service_id"], "1111111"),
            )

    ruta = f"{carpeta}/frequencies.txt"

    if not os.path.exists(ruta):
        return {}

    franjas = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

    with open(ruta, encoding=encoding) as archivo:
        for fila in csv.DictReader(archivo):
            if fila["trip_id"] not in viajes:
                continue

            linea, sentido, patron = viajes[fila["trip_id"]]
            desde = _hora_corta(fila["start_time"])
            hasta = _hora_corta(fila["end_time"])
            cada = round(int(fila["headway_secs"]) / 60)

            # Varios viajes comparten la misma franja horaria (uno por cada
            # salida dentro de ella). Se guardan por (desde, hasta) para
            # quedarse con una sola, y con el intervalo más corto: es el que
            # de verdad se percibe esperando en la parada.
            clave = (desde, hasta)
            anterior = franjas[linea][sentido][patron].get(clave)

            if anterior is None or cada < anterior:
                franjas[linea][sentido][patron][clave] = cada

    return franjas


def _ordenar_dias(bloques):
    return sorted(
        bloques,
        key=lambda b: (
            ORDEN_DE_LOS_DIAS.index(b["dias"])
            if b["dias"] in ORDEN_DE_LOS_DIAS
            else len(ORDEN_DE_LOS_DIAS)
        ),
    )


def construir():
    horarios = {}
    resumen = []

    for fuente, carpeta, encoding in FUENTES_GTFS:
        faltan = [
            n
            for n in ("trips.txt", "calendar.txt")
            if not os.path.exists(f"{carpeta}/{n}")
        ]
        if faltan:
            print(f"[horarios] {fuente}: falta {', '.join(faltan)}. Se omite.")
            continue

        calendario = _calendario(carpeta, encoding)
        tiene_frecuencias = os.path.getsize(f"{carpeta}/frequencies.txt") > 100 \
            if os.path.exists(f"{carpeta}/frequencies.txt") else False

        # Los destinos de cada sentido, para titular la columna.
        destinos = {}
        with open(f"{carpeta}/trips.txt", encoding=encoding) as archivo:
            for fila in csv.DictReader(archivo):
                clave = (fila["route_id"], fila.get("direction_id", "0"))
                destinos.setdefault(clave, fila.get("trip_headsign", ""))

        if tiene_frecuencias:
            datos = _horarios_por_frecuencia(carpeta, encoding, calendario)
            tipo = "frecuencias"
        else:
            datos = _horarios_reales(carpeta, encoding, calendario)
            tipo = "horas"

        lineas_de_la_fuente = 0

        for route_id, sentidos in datos.items():
            bloques_por_sentido = []

            for sentido, por_dias in sorted(sentidos.items()):
                bloques = []

                for patron, valor in por_dias.items():
                    if tipo == "horas":
                        bloques.append(
                            {"dias": _nombre_de_dias(patron), "salidas": sorted(valor)}
                        )
                    else:
                        bloques.append(
                            {
                                "dias": _nombre_de_dias(patron),
                                "franjas": [
                                    {"desde": d, "hasta": h, "cada": c}
                                    for (d, h), c in sorted(valor.items())
                                ],
                            }
                        )

                bloques_por_sentido.append(
                    {
                        "destino": destinos.get((route_id, sentido), ""),
                        "dias": _ordenar_dias(bloques),
                    }
                )

            # "Todos los días" como ÚNICO bloque significa que el volcado no
            # distingue tipos de día para esta línea. El panel tiene que poder
            # decirlo en vez de dar a entender que solo hay un horario.
            sin_tipos_de_dia = all(
                len(s["dias"]) == 1 and s["dias"][0]["dias"] == "Todos los días"
                for s in bloques_por_sentido
            )

            horarios[f"{fuente}-{route_id}"] = {
                "tipo": tipo,
                "sinTiposDeDia": sin_tipos_de_dia,
                "sentidos": bloques_por_sentido,
            }
            lineas_de_la_fuente += 1

        resumen.append(f"{fuente}: {lineas_de_la_fuente} líneas ({tipo})")

    return horarios, resumen


if __name__ == "__main__":
    os.makedirs(DIRECTORIO_PRECALCULADO, exist_ok=True)
    horarios, resumen = construir()

    ruta = os.path.join(DIRECTORIO_PRECALCULADO, "horarios.json")
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(horarios, archivo, ensure_ascii=False, separators=(",", ":"))

    print(f"{ruta}: {len(horarios)} líneas, {os.path.getsize(ruta) / 1e6:.2f} MB")
    for linea in resumen:
        print(f"  {linea}")

    sin_tipos = sum(1 for h in horarios.values() if h["sinTiposDeDia"])
    if sin_tipos:
        print(
            f"  Aviso: {sin_tipos} líneas sin tipos de día en el volcado "
            f"(el panel lo dirá; conocidas: 101 del CRTM)."
        )
