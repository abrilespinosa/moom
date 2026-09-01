"""
Los avisos de servicio de la EMT.

Lo que más importa aquí no es que se pinten, es QUÉ se cuenta: la API devuelve
un arrastre de semanas —el día que se construyó esto, 20 de 21 ya habían
pasado— así que un contador de "21 avisos" sería ruido puro.
"""

import pytest

pytestmark = pytest.mark.navegador


def test_el_boton_solo_cuenta_los_avisos_en_curso(render):
    resultado = render("""
        await esperarA(() => !document.getElementById("boton-incidencias").hidden);
        const b = document.getElementById("boton-incidencias");
        responder({ oculto: b.hidden, texto: b.textContent.trim() });
    """)

    assert resultado["oculto"] is False
    # Hay tres avisos de mentira, pero solo UNO está en curso.
    assert "1 aviso" in resultado["texto"]
    assert "3" not in resultado["texto"]


def test_al_pulsarlo_se_ven_los_tres_estados(render):
    resultado = render("""
        await esperarA(() => !document.getElementById("boton-incidencias").hidden);
        document.getElementById("boton-incidencias").click();
        await esperarA(() => vistaVisible() === "vista-incidencias");

        responder({
          vista: vistaVisible(),
          titulo: document.getElementById("titulo-incidencias").textContent.trim(),
          estados: [...document.querySelectorAll(".incidencia-estado")]
                     .map((e) => e.textContent.trim()),
        });
    """)

    assert resultado["vista"] == "vista-incidencias"
    assert "1 aviso en curso" in resultado["titulo"]
    # Los terminados se enseñan igual: saber que ya acabó también informa.
    assert resultado["estados"] == ["En curso", "Programada", "Ya terminada"]


def test_volver_regresa_a_donde_se_estaba(render):
    """
    Mismo criterio que el botón Volver de las llegadas: si entraste mirando una
    parada, no te devuelve al buscador y te hace buscarla otra vez.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("cibeles");
        await esperarA(() => resultados().length > 0);
        pulsarResultado();
        await esperarA(() => vistaVisible() === "vista-llegadas");

        await esperarA(() => !document.getElementById("boton-incidencias").hidden);
        document.getElementById("boton-incidencias").click();
        await esperarA(() => vistaVisible() === "vista-incidencias");

        document.getElementById("boton-volver-incidencias").click();
        responder(vistaVisible());
    """)

    assert resultado == "vista-llegadas"


def test_sin_avisos_en_curso_el_boton_no_se_ve(render):
    """
    Que app.js le ponga hidden no basta: la regla de style.css selecciona por
    id y eso pesa más que el [hidden] del navegador, así que display: flex
    ganaba y el botón salía igual.

    Llegó a producción tal cual: una caja naranja vacía que llevaba a una
    lista de avisos ya terminados, que es justo lo que el diseño quería
    evitar. El test anterior no podía verlo porque leía b.hidden —la
    propiedad que se acababa de escribir— en vez de mirar si se dibujaba.

    Por eso aquí se mide el elemento, no se le pregunta.
    """
    resultado = render(
        """
        const b = document.getElementById("boton-incidencias");
        b.hidden = true;
        responder({
          alto: b.getBoundingClientRect().height,
          display: getComputedStyle(b).display,
        });
        """
    )

    assert resultado["display"] == "none"
    assert resultado["alto"] == 0
