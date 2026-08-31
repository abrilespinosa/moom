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


def test_los_datos_del_gtfs_se_pueden_cachear():
    """
    Paradas, líneas y colores solo cambian al regenerar el volcado, así que
    piden caché larga: sin ella cada visita vuelve a bajarlos.

    Lo que NO debe llevar esta cabecera es ningún endpoint de tiempos en
    vivo: serviría llegadas de hace una hora como si fueran de ahora. Por eso
    la lista de aquí es explícita y no un recorrido de todas las rutas.
    """
    for ruta in ("/paradas", "/lineas", "/linea/EMT-027", "/metro/lineas/colores"):
        cabecera = cliente.get(ruta).headers.get("cache-control", "")
        assert "max-age=3600" in cabecera, ruta


def test_una_linea_que_no_existe_no_se_cachea():
    """
    Guardar durante un día que una línea no existe es justo lo que no
    interesa: si aparece en el próximo volcado, la respuesta buena tiene que
    llegar ya.
    """
    cabecera = cliente.get("/linea/NO-EXISTE").headers.get("cache-control", "")

    assert cabecera == ""


def test_una_linea_de_metro_desconocida_da_404_sin_llamar_a_la_api():
    """
    Antes esto era un 500. El código llegaba hasta el CRTM, que responde
    {"lines": {}}, y saltaba un KeyError que NO es RequestException: se
    escapaba del manejador que convierte los fallos de API externa en 503.

    Si este test empieza a tardar, es que la validación ha dejado de cortar
    antes de salir a la red.
    """
    respuesta = cliente.get("/metro/linea/linea-que-no-existe/vehiculos")

    assert respuesta.status_code == 404


def test_las_coordenadas_no_arrastran_precision_inutil():
    """
    Los GTFS traen 13 decimales, que son nanómetros. Redondearlas a 5 (algo
    menos de un metro) quita el 25% del peso de la respuesta.
    """
    paradas = cliente.get("/paradas").json()

    for parada in paradas:
        assert len(str(parada["lat"]).split(".")[-1]) <= 5, parada
        assert len(str(parada["lon"]).split(".")[-1]) <= 5, parada


def test_las_paradas_cercanas_llegan_ordenadas_y_son_pocas():
    """
    El atajo para quien abre esto de pie en una parada: /paradas son 254 KB y
    hasta que no llegan no hay ni buscador ni marcadores.

    Las coordenadas son las de Sol, así que la primera tiene que ser de allí.
    """
    respuesta = cliente.get("/paradas/cerca?lat=40.4168&lon=-3.7038")
    cercanas = respuesta.json()

    assert respuesta.status_code == 200
    assert len(cercanas) == 40
    assert "Sol" in cercanas[0]["nombre"] or "Sol" in cercanas[0]["id"]

    # Y de verdad ordenadas: cada una, más lejos que la anterior.
    from backend.main import _distancia_aproximada

    distancias = [
        _distancia_aproximada(40.4168, -3.7038, p["lat"], p["lon"]) for p in cercanas
    ]
    assert distancias == sorted(distancias)


def test_las_paradas_cercanas_tienen_tope():
    """
    Sin tope, un limite enorme recorre y serializa las 13.542, que es
    exactamente lo que este endpoint viene a evitar.
    """
    cercanas = cliente.get("/paradas/cerca?lat=40.4&lon=-3.7&limite=99999").json()

    assert len(cercanas) == 200


def test_las_paradas_cercanas_pesan_una_fracción_de_la_lista_completa():
    cerca = len(cliente.get("/paradas/cerca?lat=40.4168&lon=-3.7038").content)
    todas = len(cliente.get("/paradas").content)

    assert cerca < todas / 50, f"cerca={cerca} todas={todas}"
