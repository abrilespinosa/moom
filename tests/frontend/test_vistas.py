"""
Las tres vistas del panel y cómo se navega entre ellas.

El panel tiene tres vistas (busqueda, linea, llegadas) de las que solo una es
visible, y el botón "Volver" no lleva siempre al mismo sitio: depende de por
dónde se entró. Es una regla fácil de romper sin darse cuenta al tocar
cualquiera de las tres.
"""

import pytest

pytestmark = pytest.mark.navegador


def test_elegir_una_linea_abre_su_recorrido_en_orden(render):
    resultado = render("""
        await esperarA(() => TODAS_LAS_LINEAS.length > 0);
        escribirEnBuscador("27");
        await esperarA(() => resultados().length > 0);

        pulsarResultado();
        await esperarA(() => vistaVisible() === "vista-linea");
        await esperarA(() => document.querySelectorAll("#lista-recorrido li").length > 0);

        responder({
          vista: vistaVisible(),
          paradas: [...document.querySelectorAll("#lista-recorrido li")]
                     .map((li) => li.textContent.trim()),
        });
    """)

    assert resultado["vista"] == "vista-linea"
    # El orden del recorrido es el dato: una lista de paradas desordenada no
    # sirve para nada, y es justo lo que se pierde si alguien reordena.
    assert "Cibeles" in resultado["paradas"][0]
    assert "Atocha" in resultado["paradas"][1]


def test_volver_desde_una_parada_de_la_linea_regresa_al_recorrido(render):
    """
    Es lo que hace vistaDeOrigen. Sin él, "Volver" mandaba siempre al
    buscador y había que buscar la línea otra vez para seguir mirando su
    recorrido, que es lo que se estaba haciendo.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_LINEAS.length > 0);
        escribirEnBuscador("27");
        await esperarA(() => resultados().length > 0);
        pulsarResultado();

        await esperarA(() => document.querySelectorAll("#lista-recorrido li").length > 0);
        document.querySelector("#lista-recorrido .resultado-principal").click();
        await esperarA(() => vistaVisible() === "vista-llegadas");

        const antesDeVolver = vistaVisible();
        document.getElementById("boton-volver").click();

        responder({ antesDeVolver, despues: vistaVisible() });
    """)

    assert resultado["antesDeVolver"] == "vista-llegadas"
    assert resultado["despues"] == "vista-linea"


def test_volver_desde_una_parada_buscada_regresa_al_buscador(render):
    """El otro lado de la misma regla: entrando por el buscador, se vuelve ahí."""
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("cibeles");
        await esperarA(() => resultados().length > 0);

        pulsarResultado();
        await esperarA(() => vistaVisible() === "vista-llegadas");

        document.getElementById("boton-volver").click();
        responder(vistaVisible());
    """)

    assert resultado == "vista-busqueda"


def test_solo_hay_una_vista_visible_a_la_vez(render):
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("cibeles");
        await esperarA(() => resultados().length > 0);
        pulsarResultado();
        await esperarA(() => vistaVisible() === "vista-llegadas");

        const visibles = ["vista-busqueda", "vista-linea", "vista-llegadas"].filter(
          (id) => getComputedStyle(document.getElementById(id)).display !== "none"
        );

        responder(visibles);
    """)

    assert resultado == ["vista-llegadas"]
