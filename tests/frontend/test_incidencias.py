"""
Los avisos de servicio de la EMT.

Lo que más importa aquí no es que se pinten, es QUÉ se cuenta: la API devuelve
un arrastre de semanas —el día que se construyó esto, 20 de 21 ya habían
pasado— así que un contador de "21 avisos" sería ruido puro.
"""

import pytest

pytestmark = pytest.mark.navegador


def test_el_boton_no_cuenta_los_avisos_ya_terminados(render):
    """
    Cuenta lo que está pasando y lo que va a pasar; lo terminado, no.

    Empezó contando solo los EN CURSO, y el primer día en producción eso dejó
    inalcanzable una manifestación programada que afectaba a 21 líneas: sin
    botón no había forma de abrir la lista donde estaba.
    """
    resultado = render("""
        await esperarA(() => !document.getElementById("boton-incidencias").hidden);
        const b = document.getElementById("boton-incidencias");
        responder({ oculto: b.hidden, texto: b.textContent.trim() });
    """)

    assert resultado["oculto"] is False
    # De los tres avisos de mentira, uno está en curso y otro programado.
    assert "2 avisos" in resultado["texto"]
    # El tercero ya terminó y no se cuenta.
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
    assert resultado["titulo"] == "1 aviso en curso · 1 programado"
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


def test_volver_la_primera_vez_no_deja_una_ficha_vacia(render):
    """
    Reportado en uso real: pulsar Avisos y luego Volver, RECIÉN CARGADA la
    página, dejaba una ficha de llegadas vacía. La segunda vez ya funcionaba.

    La causa era que vistaVisibleAhora() leía elemento.style.display, o sea el
    atributo EN LÍNEA, que está vacío hasta que mostrarVista() lo escribe por
    primera vez. Las vistas arrancan ocultas desde style.css, así que
    "" !== "none" daba verdadero y contestaba "llegadas" sin que hubiera
    ninguna parada abierta.

    Por eso el test NO navega antes: en cuanto se abre cualquier vista, el
    fallo desaparece. Ir directo desde la carga es la única forma de verlo.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        await esperarA(() => !document.getElementById("boton-incidencias").hidden);

        // Sin pasar por ninguna otra vista, que es cuando fallaba.
        document.getElementById("boton-incidencias").click();
        await esperarA(() => vistaVisible() === "vista-incidencias");

        document.getElementById("boton-volver-incidencias").click();
        responder(vistaVisible());
    """)

    assert resultado == "vista-busqueda"
