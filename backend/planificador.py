"""
Cálculo de rutas: de un punto a otro, con horas reales.

El algoritmo es RAPTOR simplificado. Va por rondas, y cada ronda equivale a
un trasbordo más: la ronda 0 son los viajes directos, la 1 los de un cambio,
y así. En cada ronda se mira, para cada parada a la que ya se sabe llegar y
a qué hora, qué líneas pasan por ella, se coge la primera que salga después
de esa hora y se apuntan las llegadas a todas las paradas siguientes.

Se eligió esto y no un Dijkstra sobre un grafo porque el coste de un tramo
aquí no es un número fijo: depende de a qué hora llegues, porque hay que
esperar al siguiente vehículo. RAPTOR está pensado para justo eso y además
da de forma natural el criterio que interesa, llegar lo antes posible.

Los datos salen de backend/data/precalculado/rutas.json, que genera
scripts/precalcular_rutas.py.
"""

import bisect
import json
import os
from collections import defaultdict
from datetime import date, timedelta

from backend.gtfs_loader import DIRECTORIO_PRECALCULADO

# Cuánto se anda, en metros por hora, y el rodeo sobre la línea recta. Los
# mismos que usa el frontend para la distancia a las paradas: si no
# coincidieran, la app diría dos cosas distintas sobre el mismo paseo.
VELOCIDAD_ANDANDO = 4500
RODEO_CALLEJERO = 1.25

# Lo más lejos que se acepta caminar al principio y al final del viaje.
RADIO_BUSQUEDA_METROS = 800

# Margen para bajarse de un vehículo y subirse al siguiente en la misma
# parada. Sin él, el planificador encadenaría un metro que llega a las 10:00
# con otro que sale a las 10:00, que sobre el papel funciona y en el andén
# no.
MARGEN_TRASBORDO_SEGUNDOS = 60

# Cuántos trasbordos se exploran. Tres tramos cubren de sobra la región; más
# rondas cuestan tiempo y devuelven rutas que nadie haría.
MAXIMO_RONDAS = 3


def _cargar():
    ruta = os.path.join(DIRECTORIO_PRECALCULADO, "rutas.json")

    if not os.path.exists(ruta):
        return None

    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


DATOS = _cargar()

# Índice parada -> [(patrón, posición en su recorrido)]. Se construye una vez
# al importar: recorrer los 12.561 patrones en cada consulta costaría más que
# todo el cálculo.
PATRONES_POR_PARADA = defaultdict(list)

if DATOS:
    for indice, patron in enumerate(DATOS["patrones"]):
        for posicion, parada in enumerate(patron["p"]):
            PATRONES_POR_PARADA[parada].append((indice, posicion))


def hay_datos():
    """
    Si falta rutas.json, el planificador se desactiva y el resto de la
    aplicación sigue funcionando, igual que pasa con la búsqueda por línea
    cuando no están los GTFS pesados.
    """
    return DATOS is not None


def segundos_andando(metros):
    return metros * RODEO_CALLEJERO / VELOCIDAD_ANDANDO * 3600


def _servicios_activos(dia):
    """
    Qué servicios circulan una fecha concreta, y de qué redes ha caducado el
    calendario.

    Manda calendar_dates sobre calendar: un festivo que cae en martes está
    en "menos" del servicio laborable y en "mas" del festivo, y si se mirara
    solo el día de la semana saldrían autobuses que no existen.

    Lo de las caducadas hace falta porque pasa de verdad. El volcado de
    Metro que hay en el repositorio declara servicio hasta el 27-05-2026, y
    a partir de ahí ningún servicio suyo casa con la fecha: siguiendo el
    calendario a rajatabla, el metro deja de existir y el planificador manda
    a Chamartín en autobús. Descartar una red entera en silencio por tener
    el volcado viejo es peor que usar su horario y decirlo, así que para esa
    red se ignora el rango de fechas y se mira solo el día de la semana. Lo
    correcto de verdad es descargar un GTFS nuevo.
    """
    texto = dia.strftime("%Y%m%d")
    bit = 1 << dia.weekday()

    activos = set()
    por_fuente = defaultdict(list)

    for nombre, servicio in DATOS["servicios"].items():
        por_fuente[nombre.split(":", 1)[0]].append((nombre, servicio))

        if texto in servicio["menos"]:
            continue

        if texto in servicio["mas"]:
            activos.add(nombre)
            continue

        if servicio["desde"] <= texto <= servicio["hasta"] and servicio["d"] & bit:
            activos.add(nombre)

    caducadas = []
    for fuente, servicios in por_fuente.items():
        if any(nombre in activos for nombre, _ in servicios):
            continue

        caducadas.append(fuente)
        for nombre, servicio in servicios:
            if servicio["d"] & bit and texto not in servicio["menos"]:
                activos.add(nombre)

    return activos, sorted(caducadas)


def _primera_salida(patron, desde_segundos, activos):
    """
    Hora a la que pasa el primer vehículo útil de este patrón.

    Hay que mirar en dos sitios porque las tres redes no publican su horario
    igual. El interurbano da horas concretas y van en "s"; EMT y Metro dan
    intervalos ("de 7:00 a 9:00, uno cada 630 segundos") y van en "f". Una
    misma línea puede tener de los dos si cambia de régimen a lo largo del
    día, así que se calculan ambos y gana el más temprano.
    """
    mejor = None

    # Salidas sueltas: bisección hasta la primera lo bastante tardía, y
    # desde ahí saltando los servicios que hoy no circulan.
    salidas = patron["s"]
    # Con key= se compara solo la hora. Sin ella habría que construir un
    # elemento del mismo tipo que los de la lista para comparar, y eso ata
    # esta función a que las salidas sean listas (como llegan del JSON) y no
    # tuplas: un detalle invisible que rompe en cuanto alguien las construye
    # a mano.
    i = bisect.bisect_left(salidas, desde_segundos, key=lambda salida: salida[0])
    for hora, servicio in salidas[i:]:
        if servicio in activos:
            mejor = hora
            break

    # Ventanas de frecuencia: el siguiente paso es el primer múltiplo del
    # intervalo que caiga dentro de la ventana y no antes de la hora pedida.
    for inicio, fin, paso, servicio in patron["f"]:
        if servicio not in activos or fin < desde_segundos:
            continue

        if desde_segundos <= inicio:
            candidato = inicio
        else:
            saltos = -(-(desde_segundos - inicio) // paso)  # división hacia arriba
            candidato = inicio + saltos * paso

        if candidato <= fin and (mejor is None or candidato < mejor):
            mejor = candidato

    return mejor


def _paradas_cercanas(paradas, punto, radio=RADIO_BUSQUEDA_METROS):
    """Paradas andando desde un punto, con los segundos que cuesta llegar."""
    import math

    radio_tierra = 6371000
    rad = math.radians
    cercanas = {}

    for parada in paradas:
        dlat = rad(parada["lat"] - punto["lat"])
        dlon = rad(parada["lon"] - punto["lon"])
        x = (
            math.sin(dlat / 2) ** 2
            + math.cos(rad(punto["lat"]))
            * math.cos(rad(parada["lat"]))
            * math.sin(dlon / 2) ** 2
        )
        metros = radio_tierra * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x))

        if metros <= radio:
            cercanas[parada["id"]] = (metros, segundos_andando(metros))

    return cercanas


def planificar(paradas, origen, destino, salida_segundos, dia=None):
    """
    Devuelve la mejor ruta entre dos puntos, o None si no encuentra ninguna.

    "Mejor" es llegar lo antes posible. Entre dos que llegan a la vez gana
    la de menos trasbordos, porque cambiar de vehículo cansa aunque el reloj
    no lo note.
    """
    if not hay_datos():
        return None

    dia = dia or date.today()
    activos, calendarios_caducados = _servicios_activos(dia)

    origen_cercanas = _paradas_cercanas(paradas, origen)
    destino_cercanas = _paradas_cercanas(paradas, destino)

    if not origen_cercanas or not destino_cercanas:
        return None

    # Para cada parada: a qué hora se sabe llegar y cómo se llegó.
    mejor = {}
    for id_parada, (metros, segundos) in origen_cercanas.items():
        mejor[id_parada] = {
            "hora": salida_segundos + segundos,
            "trasbordos": 0,
            "desde": None,
            "tramo": {"modo": "andando", "metros": round(metros)},
        }

    marcadas = set(origen_cercanas)

    for ronda in range(MAXIMO_RONDAS):
        mejoradas = set()

        # Un patrón puede alcanzarse desde varias paradas marcadas; interesa
        # subirse en la más temprana, así que se agrupan antes de recorrer.
        candidatos = {}
        for id_parada in marcadas:
            for indice, posicion in PATRONES_POR_PARADA.get(id_parada, ()):
                actual = candidatos.get(indice)
                if actual is None or mejor[id_parada]["hora"] < mejor[actual[1]]["hora"]:
                    candidatos[indice] = (posicion, id_parada)

        for indice, (posicion, id_subida) in candidatos.items():
            patron = DATOS["patrones"][indice]
            llegada_a_la_parada = mejor[id_subida]["hora"]

            # Hora a la que el vehículo tiene que pasar por la parada de
            # subida: la de llegada del viajero, más el margen si venía de
            # otro vehículo (si venía andando, ya está contado).
            margen = MARGEN_TRASBORDO_SEGUNDOS if ronda > 0 else 0
            desde = llegada_a_la_parada + margen - patron["t"][posicion]

            salida = _primera_salida(patron, desde, activos)
            if salida is None:
                continue

            for siguiente in range(posicion + 1, len(patron["p"])):
                id_destino = patron["p"][siguiente]
                hora = salida + patron["t"][siguiente]

                anterior = mejor.get(id_destino)
                if anterior is None or hora < anterior["hora"]:
                    mejor[id_destino] = {
                        "hora": hora,
                        "trasbordos": ronda,
                        "desde": id_subida,
                        "tramo": {
                            "modo": "linea",
                            "linea": patron["l"],
                            "subida": id_subida,
                            "bajada": id_destino,
                            "sale": salida + patron["t"][posicion],
                            "llega": hora,
                            "paradas": siguiente - posicion,
                        },
                    }
                    mejoradas.add(id_destino)

        # Trasbordos a pie: desde lo que se acaba de mejorar, alcanzar
        # paradas cercanas que sirvan otras líneas.
        for id_parada in list(mejoradas):
            for id_vecina, metros in DATOS["enlaces"].get(id_parada, ()):
                hora = mejor[id_parada]["hora"] + segundos_andando(metros)
                anterior = mejor.get(id_vecina)

                if anterior is None or hora < anterior["hora"]:
                    mejor[id_vecina] = {
                        "hora": hora,
                        "trasbordos": mejor[id_parada]["trasbordos"],
                        "desde": id_parada,
                        "tramo": {"modo": "andando", "metros": metros},
                    }
                    mejoradas.add(id_vecina)

        if not mejoradas:
            break

        marcadas = mejoradas

    # Del conjunto de paradas cercanas al destino, la que permite llegar
    # antes contando el paseo final.
    final = None
    for id_parada, (metros, segundos) in destino_cercanas.items():
        if id_parada not in mejor:
            continue

        llegada = mejor[id_parada]["hora"] + segundos
        if final is None or llegada < final[0]:
            final = (llegada, id_parada, metros)

    if final is None:
        return None

    llegada, id_ultima, metros_finales = final

    # Se reconstruye hacia atrás siguiendo de dónde vino cada parada.
    tramos = []
    actual = id_ultima
    visitadas = set()
    while actual is not None and actual not in visitadas:
        visitadas.add(actual)
        paso = mejor[actual]
        if paso["tramo"]["modo"] == "linea" or paso["desde"] is not None:
            tramos.append(paso["tramo"])
        actual = paso["desde"]

    tramos.reverse()
    tramos.append({"modo": "andando", "metros": round(metros_finales)})

    # Los paseos encadenados se funden en uno. La reconstrucción los saca
    # partidos porque cada salto de enlace es su propio paso, y en pantalla
    # "andar 59 m, andar 393 m, andar 18 m" se lee como tres cosas cuando en
    # la calle es una sola caminata.
    fundidos = []
    for tramo in tramos:
        if (
            tramo["modo"] == "andando"
            and fundidos
            and fundidos[-1]["modo"] == "andando"
        ):
            fundidos[-1]["metros"] += tramo["metros"]
        else:
            fundidos.append(dict(tramo))

    # Un paseo de menos de 20 m es ruido de coordenadas, no un tramo.
    tramos = [t for t in fundidos if t["modo"] != "andando" or t["metros"] >= 20]

    return {
        "sale": salida_segundos,
        "llega": llegada,
        "duracion": llegada - salida_segundos,
        "trasbordos": sum(1 for t in tramos if t["modo"] == "linea") - 1,
        "tramos": tramos,
        # Redes cuyo volcado GTFS ya no cubre la fecha consultada. El
        # frontend tiene que decirlo: sus horas son del último calendario
        # publicado, no de hoy.
        "calendariosCaducados": calendarios_caducados,
    }
