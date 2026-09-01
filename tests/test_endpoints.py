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
    Sin tope, un limite enorme recorre y serializa las 13.533, que es
    exactamente lo que este endpoint viene a evitar.
    """
    cercanas = cliente.get("/paradas/cerca?lat=40.4&lon=-3.7&limite=99999").json()

    assert len(cercanas) == 200


def test_las_paradas_cercanas_pesan_una_fracción_de_la_lista_completa():
    cerca = len(cliente.get("/paradas/cerca?lat=40.4168&lon=-3.7038").content)
    todas = len(cliente.get("/paradas").content)

    assert cerca < todas / 50, f"cerca={cerca} todas={todas}"


def test_los_horarios_del_interurbano_son_horas_reales():
    """
    El CRTM publica horas de paso: 1,24 M de filas en stop_times y CERO en
    frequencies. Comprobado contra la tabla oficial de la línea 191, cuyas 32
    horas distintas coinciden una a una con las del volcado.
    """
    datos = cliente.get("/linea/CRTM-8__191___/horarios").json()

    assert datos["disponible"] is True
    assert datos["tipo"] == "horas"

    salidas = datos["sentidos"][0]["dias"][0]["salidas"]
    assert "06:00" in salidas and "06:40" in salidas and "06:55" in salidas
    # Los nocturnos de la tabla oficial, normalizados a hora de reloj.
    assert "00:30" in salidas and "02:30" in salidas


def test_los_horarios_de_la_emt_son_frecuencias():
    """
    EMT no publica horas de paso, publica intervalos. Enseñar "pasa a las
    7:03" sería inventarse una precisión que el origen no tiene.
    """
    datos = cliente.get("/linea/EMT-027/horarios").json()

    assert datos["tipo"] == "frecuencias"

    franjas = datos["sentidos"][0]["dias"][0]["franjas"]
    assert franjas
    assert all({"desde", "hasta", "cada"} <= set(f) for f in franjas)
    assert all(f["cada"] > 0 for f in franjas)


def test_se_avisa_cuando_el_volcado_no_distingue_tipos_de_dia():
    """
    101 de las 340 líneas del CRTM traen un único servicio de "todos los días".
    El panel tiene que poder decirlo en vez de dar a entender que solo hay un
    horario; la 191 es una de ellas y la 421 no.
    """
    sin_tipos = cliente.get("/linea/CRTM-8__191___/horarios").json()
    con_tipos = cliente.get("/linea/CRTM-8__421___/horarios").json()

    assert sin_tipos["sinTiposDeDia"] is True
    assert con_tipos["sinTiposDeDia"] is False

    dias = [b["dias"] for b in con_tipos["sentidos"][0]["dias"]]
    assert "Laborables" in dias and "Sábados" in dias


def test_los_horarios_de_una_linea_desconocida_dan_404():
    assert cliente.get("/linea/NO-EXISTE/horarios").status_code == 404


def test_las_hojas_oficiales_se_construyen_bien_para_cada_red():
    """
    El CRTM publica la tabla de horarios de cada línea como imagen, una por
    sentido: /datos_lineas/horarios/{MODO}{NUMERO}H{1|2}.png

    Las dos redes NO se construyen igual, y es el error fácil: el route_id del
    CRTM ya lleva su modo delante ("8__191___" -> "8191"), mientras que el de
    EMT es solo el número y hay que anteponerle el 6. Anteponerlo también al
    del CRTM daba "88191" y un 404.
    """
    interurbano = cliente.get("/linea/CRTM-8__191___/horarios").json()["imagenes"]
    urbano = cliente.get("/linea/EMT-103/horarios").json()["imagenes"]

    assert [i["sentido"] for i in interurbano] == ["Ida", "Vuelta"]
    assert interurbano[0]["url"].endswith("/8191H1.png")
    assert interurbano[1]["url"].endswith("/8191H2.png")

    assert urbano[0]["url"].endswith("/6103H1.png")
    assert urbano[1]["url"].endswith("/6103H2.png")


def test_metro_no_tiene_hojas_oficiales():
    """
    Comprobado contra la web del CRTM: Metro devuelve 404 en todas. Es
    coherente, porque publica frecuencias y no horas de paso, así que ahí se
    enseña la tabla construida desde el GTFS.
    """
    datos = cliente.get("/linea/METRO-4__2___/horarios").json()

    assert datos["imagenes"] is None
    assert datos["tipo"] == "frecuencias"


def test_las_llegadas_no_arrastran_las_incidencias():
    """
    EMT las manda dentro de la misma respuesta, y son el 87% de su peso: 19 KB
    de 22. El poller pide esto CADA 10 SEGUNDOS, así que dejarlas ahí sería
    servir dos docenas de avisos de toda la red —la mayoría de semanas
    pasadas— a alguien que solo quiere saber cuándo pasa su autobús, con datos
    móviles y en la calle.
    """
    datos = cliente.get("/parada/72").json()

    assert "Incident" not in datos["data"][0]
    assert len(cliente.get("/parada/72").content) < 8000


def test_quitarlas_de_las_llegadas_no_se_las_quita_a_incidencias():
    """
    Las dos rutas leen de la MISMA caché de emt_client, así que quitar el bloque
    del original se las vaciaba a quien sí las quiere. Pasó al escribirlo, y el
    síntoma era desconcertante: /incidencias devolvía cero justo después de
    consultar una parada.
    """
    cliente.get("/parada/72")
    primera = cliente.get("/incidencias").json()

    cliente.get("/parada/72")
    segunda = cliente.get("/incidencias").json()

    assert primera["incidencias"], "sin avisos no se prueba nada"
    assert len(segunda["incidencias"]) == len(primera["incidencias"])


def test_cada_incidencia_dice_si_sigue_o_ya_terminó():
    """
    Es lo único que hace útil la lista: la API devuelve un arrastre de semanas.
    """
    datos = cliente.get("/incidencias").json()

    validos = {"en_curso", "programada", "terminada", "desconocida"}
    assert all(i["estado"] in validos for i in datos["incidencias"])

    # Y el contador solo cuenta lo que está pasando ahora.
    assert datos["enCurso"] == sum(
        1 for i in datos["incidencias"] if i["estado"] == "en_curso"
    )
