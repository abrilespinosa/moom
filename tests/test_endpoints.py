"""
Tests de los endpoints que responden sin salir a la red.

Solo se prueban rutas que contestan desde memoria o que cortan antes de
llamar a EMT o al CRTM. Así los tests no fallan porque una API externa esté
caída, que es exactamente el tipo de fallo que no debe romper una suite.
"""

from fastapi.testclient import TestClient

from backend.main import app

cliente = TestClient(app)


def test_una_parada_que_no_existe_da_404():
    """
    Además de ser la respuesta honesta, esta comprobación cierra una vía de
    abuso: el id se interpola en la ruta de la URL de EMT, y esa petición
    lleva nuestro token. Un valor con "../" dentro cambiaba la petición que
    sale del servidor.
    """
    respuesta = cliente.get("/parada/no-existe-esta-parada")

    assert respuesta.status_code == 404


def test_los_intentos_de_inyeccion_se_rechazan_antes_de_llamar_a_emt():
    """
    Ninguno de estos llega a la red: si alguno pasara, el test tardaría
    segundos y podría fallar por causas ajenas.
    """
    for id_malicioso in (
        "../../../mobilitylabs/user/login",
        "72%3Ffoo=bar",  # el "?" codificado, que sí viaja dentro de la ruta
        "72/../../otra",
        "9" * 500,
    ):
        respuesta = cliente.get(f"/parada/{id_malicioso}")
        assert respuesta.status_code == 404, id_malicioso


def test_listar_lineas_no_incluye_el_recorrido():
    """
    Son casi 30.000 ids de parada entre todas las líneas, y el buscador solo
    necesita número, nombre y color. El recorrido se pide aparte.
    """
    lineas = cliente.get("/lineas").json()

    assert lineas
    assert all("sentidos" not in linea for linea in lineas)
    assert {"id", "numero", "nombre", "fuente"} <= set(lineas[0])


def test_una_linea_conocida_trae_su_recorrido_con_nombres():
    respuesta = cliente.get("/linea/EMT-027").json()

    assert respuesta["encontrada"] is True
    assert respuesta["sentidos"]

    primera = respuesta["sentidos"][0]["paradas"][0]
    assert primera["id"]
    assert primera["nombre"]


def test_una_linea_inexistente_se_responde_sin_romper():
    """
    Se contesta con encontrada: False en vez de un 404 porque el frontend
    distingue por ese campo, y un error de red significa otra cosa distinta.
    """
    assert cliente.get("/linea/NO-EXISTE").json()["encontrada"] is False


def test_una_estacion_de_metro_desconocida_no_llama_a_la_api():
    """Corta antes de salir a la red y devuelve una lista de líneas vacía."""
    respuesta = cliente.get("/metro/parada/est_9_999/lineas").json()

    assert respuesta["codLines"] == []


def test_listar_paradas_devuelve_las_tres_redes():
    paradas = cliente.get("/paradas").json()

    assert len({parada["fuente"] for parada in paradas}) == 3
