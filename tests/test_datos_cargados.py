"""
Tests sobre los datos que la aplicación carga al arrancar.

No comprueban lógica sino invariantes de los datos, que es donde duelen los
fallos de esta aplicación: un volcado GTFS nuevo puede romperlos en silencio
y no se nota hasta que una estación desaparece del mapa.

Se apoyan en el JSON precalculado, que sí viaja en el repositorio, para que
pasen también en un clon limpio sin el GTFS pesado.
"""

from collections import Counter

from backend.gtfs_loader import cargar_lineas, cargar_todas_las_paradas

PARADAS = cargar_todas_las_paradas()
LINEAS = cargar_lineas()


def test_hay_paradas_de_las_tres_redes():
    fuentes = {parada["fuente"] for parada in PARADAS}
    assert fuentes == {"EMT", "CRTM", "METRO"}


def test_los_ids_repetidos_describen_el_mismo_sitio():
    """
    Hay 9 ids que salen dos veces, una en el GTFS del CRTM y otra en el de
    Metro: son los grandes intercambiadores (Méndez Álvaro, Moncloa, Plaza
    de Castilla, Aeropuerto...), que efectivamente pertenecen a las dos
    redes. main.py monta un diccionario id -> parada, así que una tapa a la
    otra; gana Metro, por ser la última que se concatena.

    Que se tapen no rompe nada MIENTRAS describan el mismo punto, y por eso
    lo que se comprueba aquí es justo eso. Si un volcado futuro les diera
    coordenadas distintas, la que ganase pintaría el marcador en otro sitio
    y nadie se enteraría: este test es el que lo cazaría.
    """
    por_id = {}
    for parada in PARADAS:
        por_id.setdefault(parada["id"], []).append(parada)

    for id_parada, versiones in por_id.items():
        distintas = {(p["nombre"], p["lat"], p["lon"]) for p in versiones}
        assert len(distintas) == 1, f"{id_parada} aparece con datos distintos"


def test_la_version_que_prevalece_de_un_intercambiador_sirve_para_metro():
    """
    De los ids repetidos gana el de Metro, que es el que trae codAnden. Si
    el orden de concatenación cambiara y ganase el del CRTM, esas nueve
    estaciones se quedarían sin tiempos en vivo.
    """
    # El mismo diccionario que monta main.py: la última gana.
    por_id = {parada["id"]: parada for parada in PARADAS}
    repetidos = [
        id_parada
        for id_parada, veces in Counter(p["id"] for p in PARADAS).items()
        if veces > 1
    ]

    for id_parada in repetidos:
        assert por_id[id_parada].get("codAnden"), id_parada


def test_toda_estacion_de_metro_tiene_codanden():
    """
    Sin codAnden, la API del CRTM devuelve {"stops": {}} y esa estación se
    queda sin tiempos. Las tres estrategias de traducción existen justamente
    para que esto no pase con ninguna.
    """
    sin_anden = [
        parada
        for parada in PARADAS
        if parada["fuente"] == "METRO" and not parada.get("codAnden")
    ]

    assert sin_anden == []


def test_los_andenes_huerfanos_siguen_teniendo_estacion():
    """
    Noviciado y Acacias no tienen fila de estación ni parent_station en el
    volcado del CRTM, así que se les fabrica una sintética. Sin eso
    desaparecen del mapa y del recorrido de su línea, pese a que la API sí
    responde a sus códigos.
    """
    ids = {parada["id"] for parada in PARADAS}

    assert "est_4_38" in ids  # Noviciado
    assert "est_4_92" in ids  # Acacias


def test_toda_parada_tiene_coordenadas_utilizables():
    """Una parada sin coordenadas válidas no se puede pintar en el mapa."""
    for parada in PARADAS:
        assert isinstance(parada["lat"], float)
        assert isinstance(parada["lon"], float)
        # Madrid y su comunidad, con margen de sobra.
        assert 39.5 < parada["lat"] < 41.5, parada
        assert -5.0 < parada["lon"] < -2.5, parada


def test_los_ids_de_linea_llevan_su_fuente_como_prefijo():
    """
    El número de línea no es único entre redes (la 1 y la 2 existen a la vez
    en EMT y en Metro), así que el id tiene que desambiguar.
    """
    for linea in LINEAS:
        assert linea["id"].startswith(f"{linea['fuente']}-"), linea["id"]


def test_las_lineas_sin_recorrido_se_publican_igual():
    """
    Hay líneas en routes.txt que no aparecen en trips.txt y se quedan sin
    paradas. Se devuelven igual, con sentidos vacío: descartarlas las hacía
    desaparecer del buscador, y sus tiempos en vivo sí funcionan.
    """
    sin_recorrido = [linea for linea in LINEAS if not linea["sentidos"]]

    assert sin_recorrido, "se esperaba al menos una línea sin recorrido"
    # La Línea 3 de Metro es la más llamativa de la lista.
    assert any(linea["fuente"] == "METRO" for linea in sin_recorrido)


def test_las_paradas_de_un_recorrido_existen_como_paradas():
    """
    El frontend recibe el recorrido como lista de ids y busca cada uno en su
    propio índice de paradas. Un id que no exista se pintaría sin nombre.
    """
    ids = {parada["id"] for parada in PARADAS}

    for linea in LINEAS:
        for sentido in linea["sentidos"]:
            for id_parada in sentido["paradas"]:
                assert id_parada in ids, f"{linea['id']} apunta a {id_parada}"
