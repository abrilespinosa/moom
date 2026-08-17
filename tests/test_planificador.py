"""
Tests del cálculo de rutas.

Se apoyan en rutas.json, que va en el repositorio, así que no hace falta el
GTFS pesado ni salir a la red.
"""

from datetime import date

import pytest

from backend import planificador
from backend.gtfs_loader import cargar_todas_las_paradas

PARADAS = cargar_todas_las_paradas()

# Un lunes laborable dentro del calendario del volcado actual.
LUNES = date(2026, 8, 17)

SOL = {"lat": 40.41695, "lon": -3.70346}
CHAMARTIN = {"lat": 40.47230, "lon": -3.68250}


def patron(salidas=(), ventanas=()):
    """Un patrón mínimo, solo con lo que mira _primera_salida."""
    return {"s": sorted(salidas), "f": sorted(ventanas)}


def test_encuentra_el_siguiente_paso_dentro_de_una_ventana_de_frecuencia():
    """
    EMT y Metro publican intervalos, no horarios. Con un paso cada 600s
    desde las 7:00, quien llega a las 7:05 se sube al de las 7:10.
    """
    p = patron(ventanas=[(7 * 3600, 9 * 3600, 600, "S")])

    assert planificador._primera_salida(p, 7 * 3600 + 300, {"S"}) == 7 * 3600 + 600


def test_antes_de_que_abra_la_ventana_se_coge_el_primero():
    p = patron(ventanas=[(7 * 3600, 9 * 3600, 600, "S")])

    assert planificador._primera_salida(p, 6 * 3600, {"S"}) == 7 * 3600


def test_despues_de_cerrar_la_ventana_no_hay_paso():
    p = patron(ventanas=[(7 * 3600, 9 * 3600, 600, "S")])

    assert planificador._primera_salida(p, 10 * 3600, {"S"}) is None


def test_un_servicio_que_hoy_no_circula_se_ignora():
    """
    Es lo que distingue un sábado de un laborable. Sin esta comprobación, el
    planificador propondría autobuses que hoy no salen.
    """
    p = patron(ventanas=[(7 * 3600, 9 * 3600, 600, "SABADO")])

    assert planificador._primera_salida(p, 7 * 3600, {"LABORABLE"}) is None


def test_entre_una_salida_suelta_y_una_ventana_gana_la_mas_temprana():
    """
    Una línea puede tener las dos formas si cambia de régimen a lo largo del
    día, y hay que quedarse con lo que pase antes.
    """
    p = patron(
        salidas=[(8 * 3600, "S")],
        ventanas=[(7 * 3600, 9 * 3600, 600, "S")],
    )

    assert planificador._primera_salida(p, 7 * 3600 + 1, {"S"}) == 7 * 3600 + 600


@pytest.mark.skipif(not planificador.hay_datos(), reason="falta rutas.json")
def test_de_sol_a_chamartin_sale_una_ruta_razonable():
    """
    Sin fijar líneas concretas, que cambian con cada volcado: lo que se
    comprueba es que la ruta existe, que va en metro y que tarda un rato
    verosímil. En transporte público ese trayecto son unos veinte minutos;
    si saliera una hora, algo estaría mal.
    """
    ruta = planificador.planificar(PARADAS, SOL, CHAMARTIN, 10 * 3600, LUNES)

    assert ruta is not None
    assert 10 * 60 <= ruta["duracion"] <= 45 * 60
    assert any(tramo["modo"] == "linea" for tramo in ruta["tramos"])


@pytest.mark.skipif(not planificador.hay_datos(), reason="falta rutas.json")
def test_los_tramos_van_encadenados_en_el_tiempo():
    """
    Cada tramo tiene que empezar después de que acabe el anterior. Si no, la
    ruta sería imposible aunque el total cuadrase.
    """
    ruta = planificador.planificar(PARADAS, SOL, CHAMARTIN, 10 * 3600, LUNES)
    en_linea = [t for t in ruta["tramos"] if t["modo"] == "linea"]

    for anterior, siguiente in zip(en_linea, en_linea[1:]):
        assert siguiente["sale"] >= anterior["llega"]


@pytest.mark.skipif(not planificador.hay_datos(), reason="falta rutas.json")
def test_no_quedan_paseos_partidos_ni_de_dos_metros():
    """
    La reconstrucción saca un tramo por cada salto entre paradas cercanas.
    Sin fundirlos, una caminata sale troceada en tres, y los saltos de
    veinte metros son ruido de coordenadas más que un paseo.
    """
    ruta = planificador.planificar(PARADAS, SOL, CHAMARTIN, 10 * 3600, LUNES)
    modos = [t["modo"] for t in ruta["tramos"]]

    assert "andando andando" not in " ".join(modos)
    for tramo in ruta["tramos"]:
        if tramo["modo"] == "andando":
            assert tramo["metros"] >= 20


@pytest.mark.skipif(not planificador.hay_datos(), reason="falta rutas.json")
def test_avisa_de_que_el_calendario_de_metro_esta_caducado():
    """
    El volcado de Metro del repositorio declara servicio hasta el
    27-05-2026. Se sigue usando su horario, porque descartar la red entera
    daría rutas absurdas, pero la respuesta tiene que decirlo.

    Cuando se descargue un GTFS de Metro al día, este test empezará a fallar
    y habrá que quitarlo: será la señal de que ya no hace falta el apaño.
    """
    ruta = planificador.planificar(PARADAS, SOL, CHAMARTIN, 10 * 3600, LUNES)

    assert "METRO" in ruta["calendariosCaducados"]
