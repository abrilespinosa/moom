"""
Tests de lineas_de_metro_de(), que quita de codLines las líneas que no son
de Metro.

Importa en las estaciones de trasbordo: Sol devuelve también líneas de
Cercanías, y sin filtrar el frontend acabaría pidiendo trenes de Cercanías
al endpoint de Metro.
"""

from backend.main import lineas_de_metro_de


def estacion(*lineas):
    """Monta la parte de la respuesta de GetStops.php que usa la función."""
    return {"codLines": {"Line": list(lineas)}}


def test_descarta_las_lineas_de_cercanias_de_sol():
    """
    El caso real que motivó la función: Sol devuelve sus tres líneas de
    Metro más tres de Cercanías (prefijo "5__", el modo ferroviario).
    """
    resultado = lineas_de_metro_de(
        estacion("4__1___", "4__2___", "4__3___", "5__C3___", "5__C4_A__", "5__C4_B__")
    )

    assert resultado == ["4__1___", "4__2___", "4__3___"]


def test_una_estacion_normal_conserva_todas_sus_lineas():
    assert lineas_de_metro_de(estacion("4__2___")) == ["4__2___"]


def test_se_filtra_contra_routes_txt_no_por_el_prefijo():
    """
    Un código inventado con el prefijo correcto de Metro debe caer igual,
    porque la fuente de verdad es routes.txt y no la forma del código. Así,
    toda línea que sale de aquí tiene color garantizado.
    """
    assert lineas_de_metro_de(estacion("4__99___")) == []


def test_sin_lineas_devuelve_lista_vacia():
    assert lineas_de_metro_de(estacion()) == []
