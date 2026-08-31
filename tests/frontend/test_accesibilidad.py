"""Que la aplicación se pueda usar sin ratón. Era el P0 de la auditoría."""
import pytest
pytestmark = pytest.mark.navegador


def test_se_puede_abrir_una_parada_solo_con_teclado(render):
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("cibeles");
        await esperarA(() => resultados().length > 0);

        // Lo que hace una persona sin ratón: tabular hasta el resultado y
        // pulsar Enter. Aquí se enfoca directamente y se comprueba que el
        // elemento enfocable EXISTE y responde a la activación.
        const boton = resultados()[0].querySelector(".resultado-principal");
        boton.focus();
        const enfocado = document.activeElement === boton;
        boton.click();
        await esperarA(() => vistaVisible() === "vista-llegadas");

        responder({
          esBoton: boton.tagName,
          recibeFoco: enfocado,
          etiqueta: boton.getAttribute("aria-label"),
          vista: vistaVisible(),
        });
    """)

    assert resultado["esBoton"] == "BUTTON"
    assert resultado["recibeFoco"] is True
    assert "Cibeles" in resultado["etiqueta"]
    assert resultado["vista"] == "vista-llegadas"


def test_el_buscador_tiene_nombre_accesible(render):
    resultado = render("""
        const campo = document.getElementById("input-buscar");
        const etiqueta = document.querySelector('label[for="input-buscar"]');
        responder({
          hayEtiqueta: !!etiqueta,
          texto: etiqueta ? etiqueta.textContent.trim() : null,
          visible: etiqueta ? etiqueta.getBoundingClientRect().width : null,
        });
    """)
    assert resultado["hayEtiqueta"] is True
    assert "Buscar" in resultado["texto"]
    assert resultado["visible"] <= 2, "debe estar oculta visualmente, no en pantalla"


def test_hay_foco_visible_y_landmarks(render):
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        responder({
          main: document.querySelectorAll("main").length,
          header: document.querySelectorAll("header").length,
          reglaDeFoco: [...document.styleSheets]
            .flatMap((h) => { try { return [...h.cssRules]; } catch { return []; } })
            .some((r) => r.selectorText && r.selectorText.includes(":focus-visible")),
        });
    """)
    assert resultado["main"] == 1
    assert resultado["header"] == 1
    assert resultado["reglaDeFoco"] is True
