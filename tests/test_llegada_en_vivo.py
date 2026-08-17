"""
Tests de llegada_en_vivo(), que distingue una llegada con seguimiento real
de una que solo sale de la tabla de horarios.

El truco, descubierto comparando campos contra la API: "time" es la hora
prevista y "codIssue" lleva incrustada la programada. Si difieren, alguien
ha corregido la previsión con información del vehículo.
"""

from backend.metro_client import llegada_en_vivo


def test_metro_devuelve_none_porque_no_trae_codissue():
    """
    En Metro el campo viene vacío, así que no hay con qué comparar. Devolver
    None y no False es importante: False significaría "he comprobado que es
    horario teórico", y aquí lo cierto es que no se puede saber.
    """
    assert llegada_en_vivo({"time": "2026-08-17T10:00:00+02:00", "codIssue": ""}) is None


def test_sin_el_campo_tampoco_falla():
    """La API omite codIssue en algunas respuestas; no debe reventar."""
    assert llegada_en_vivo({"time": "2026-08-17T10:00:00+02:00"}) is None


def test_hora_distinta_de_la_programada_es_dato_en_vivo():
    """
    Prevista 13:17:43 contra programada 13:15:00: alguien ha corregido la
    previsión, así que hay seguimiento real.
    """
    assert (
        llegada_en_vivo(
            {
                "time": "2026-08-17T13:17:43+02:00",
                "codIssue": "8__621____4_13:15:00_1_2026",
            }
        )
        is True
    )


def test_hora_igual_a_la_programada_no_se_considera_en_vivo():
    """
    Coinciden al segundo, así que lo más probable es que estemos viendo la
    tabla de horarios.

    OJO con lo que este False significa: un autobús puntual al segundo daría
    exactamente esto y sí tendría seguimiento. Es una cota inferior, sirve
    para avisar de lo que casi seguro es teórico, no para negar lo contrario.
    """
    assert (
        llegada_en_vivo(
            {
                "time": "2026-08-17T13:15:00+02:00",
                "codIssue": "8__621____4_13:15:00_1_2026",
            }
        )
        is False
    )


def test_un_codissue_sin_hora_dentro_devuelve_none():
    """Si el formato cambia y ya no lleva hora, no se puede afirmar nada."""
    assert llegada_en_vivo({"time": "2026-08-17T13:15:00+02:00", "codIssue": "8__621"}) is None
