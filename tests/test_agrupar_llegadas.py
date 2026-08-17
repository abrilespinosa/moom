"""
Tests de agrupar_llegadas(), que convierte la lista plana de llegadas del
CRTM en las tarjetas que pinta el panel.

Es lógica pura: recibe un diccionario y devuelve otro, sin tocar la red.
"""

from backend.main import agrupar_llegadas


def llegada(cod_line, destino, hora, corto=None, cod_issue=""):
    """
    Fabrica una llegada con la forma que devuelve GetStopsTimes.php.

    Se construye a mano en vez de guardar una respuesta real porque así se
    ve, en cada test, qué campo es el que se está poniendo a prueba.
    """
    return {
        "line": {"codLine": cod_line, "shortDescription": corto or cod_line},
        "destination": destino,
        "time": hora,
        "codIssue": cod_issue,
    }


def test_agrupa_por_linea_y_destino_no_solo_por_destino():
    """
    Dos líneas distintas con el MISMO destino tienen que dar dos grupos.

    Es la razón de ser de la función: en una estación de trasbordo, agrupar
    solo por destino mezclaría trenes de líneas diferentes en una tarjeta, y
    el distintivo de color de esa tarjeta pertenece a una línea concreta.
    """
    grupos = agrupar_llegadas(
        [
            llegada("4__1___", "PINAR DE CHAMARTÍN", "2026-08-17T10:00:00+02:00"),
            llegada("4__2___", "PINAR DE CHAMARTÍN", "2026-08-17T10:01:00+02:00"),
        ]
    )

    assert len(grupos) == 2
    assert {g["codLine"] for g in grupos} == {"4__1___", "4__2___"}


def test_los_dos_sentidos_de_una_linea_son_grupos_distintos():
    """
    La API no filtra por sentido: devuelve los dos mezclados y la separación
    se hace aquí, por el campo destination.
    """
    grupos = agrupar_llegadas(
        [
            llegada("4__2___", "LAS ROSAS", "2026-08-17T10:00:00+02:00"),
            llegada("4__2___", "CUATRO CAMINOS", "2026-08-17T10:02:00+02:00"),
        ]
    )

    assert {g["destino"] for g in grupos} == {"LAS ROSAS", "CUATRO CAMINOS"}


def test_acumula_los_tiempos_del_mismo_grupo_en_orden():
    """
    Los tiempos de un mismo grupo se apilan respetando el orden de llegada,
    que es el que trae la API (se pide con orderBy=2). El panel enseña el
    primero en grande y el resto como "siguiente".
    """
    grupos = agrupar_llegadas(
        [
            llegada("4__2___", "LAS ROSAS", "2026-08-17T10:00:00+02:00"),
            llegada("4__2___", "LAS ROSAS", "2026-08-17T10:06:00+02:00"),
            llegada("4__2___", "LAS ROSAS", "2026-08-17T10:12:00+02:00"),
        ]
    )

    assert len(grupos) == 1
    assert grupos[0]["tiempos"] == [
        "2026-08-17T10:00:00+02:00",
        "2026-08-17T10:06:00+02:00",
        "2026-08-17T10:12:00+02:00",
    ]


def test_en_vivo_se_toma_de_la_primera_llegada_del_grupo():
    """
    El indicador de "en vivo" describe la llegada que se muestra en grande,
    o sea la más próxima. Aquí la primera trae corrección en vivo (la hora
    prevista no coincide con la programada del codIssue) y la segunda no;
    debe mandar la primera.
    """
    grupos = agrupar_llegadas(
        [
            llegada(
                "8__621___",
                "MADRID",
                "2026-08-17T13:17:00+02:00",
                cod_issue="8__621____4_13:15:00_1_",
            ),
            llegada(
                "8__621___",
                "MADRID",
                "2026-08-17T13:45:00+02:00",
                cod_issue="8__621____4_13:45:00_1_",
            ),
        ]
    )

    assert grupos[0]["enVivo"] is True


def test_sin_llegadas_devuelve_lista_vacia():
    """Una parada sin servicio a esta hora es normal, no un error."""
    assert agrupar_llegadas([]) == []
