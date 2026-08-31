"""
Qué pasa cuando el backend falla, y los favoritos.

Los dos son casos que no se ven abriendo la página un momento: uno solo
aparece cuando algo va mal, y el otro solo después de haber usado la
aplicación antes.
"""

import pytest

pytestmark = pytest.mark.navegador


def test_un_fallo_del_backend_se_avisa_en_el_panel(render):
    """
    El backend de mentira solo conoce la parada 72. Al pedir la 270 responde
    404, y ahí está lo importante: fetch NO lanza excepción ante un 4xx o 5xx,
    solo si la petición no llega a completarse. Sin la comprobación de
    pedirJson(), ese 404 seguía su camino y se leía como una respuesta vacía
    legítima ("no hay autobuses ahora mismo"), que es lo contrario de lo que
    ha pasado.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("atocha");
        await esperarA(() => resultados().length > 0);

        resultados()[0].click();

        const aviso = document.getElementById("aviso-conexion");
        await esperarA(() => !aviso.hidden);

        responder({ visible: !aviso.hidden, texto: aviso.textContent.trim() });
    """)

    assert resultado["visible"], "el aviso de conexión debería aparecer"
    assert resultado["texto"], "el aviso no puede salir vacío"


def test_sin_fallos_el_aviso_no_aparece(render):
    """
    La otra mitad: un aviso que estuviera siempre visible no avisaría de nada.
    La parada 72 sí la conoce el backend de mentira.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("cibeles");
        await esperarA(() => resultados().length > 0);

        resultados()[0].click();
        await esperarA(() => vistaVisible() === "vista-llegadas");
        await esperarA(() => document.querySelectorAll("#lista-llegadas li").length > 0);

        responder({
          avisoOculto: document.getElementById("aviso-conexion").hidden,
          llegadas: document.querySelectorAll("#lista-llegadas li").length,
        });
    """)

    assert resultado["avisoOculto"] is True
    assert resultado["llegadas"] > 0


def test_una_parada_marcada_como_favorita_se_guarda_y_se_relee(render):
    """
    Se guardan SOLO ids, porque los nombres y las coordenadas cambian con cada
    volcado GTFS. Este test fija las dos mitades: que la estrella escribe en
    localStorage, y que con el buscador vacío eso se vuelve a pintar.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("cibeles");
        await esperarA(() => resultados().length > 0);

        resultados()[0].querySelector(".boton-favorito").click();

        // Con el buscador vacío, la lista pasa a enseñar los favoritos.
        escribirEnBuscador("");
        await esperarA(() => resultados().length > 0);

        responder({
          guardado: JSON.parse(localStorage.getItem("moom:favoritos")),
          enPantalla: [...document.querySelectorAll("#lista-resultados li")]
                        .map((li) => li.textContent.trim()),
        });
    """)

    assert resultado["guardado"]["paradas"] == ["72"], resultado["guardado"]
    assert any("Favoritos" in texto for texto in resultado["enPantalla"])
    assert any("Cibeles" in texto for texto in resultado["enPantalla"])


def test_un_favorito_que_ya_no_existe_se_omite_sin_romper_nada(render):
    """
    Los ids que desaparecen de un volcado a otro no se borran de localStorage
    a propósito (podrían volver), así que hay que saber ignorarlos al pintar.
    Sin esto, un id viejo dejaba la lista de favoritos entera sin dibujar.
    """
    resultado = render("""
        // Primero las paradas: los favoritos se resuelven contra
        // PARADAS_POR_ID, y si todavía está vacío se descartan los dos ids y
        // el test no probaría nada.
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);

        localStorage.setItem(
          "moom:favoritos",
          JSON.stringify({ paradas: ["72", "parada-que-ya-no-existe"], lineas: [] })
        );
        cargarFavoritos();
        actualizarResultadosBusqueda();
        await esperarA(() => resultados().length > 0);

        responder([...document.querySelectorAll("#lista-resultados li")]
                    .map((li) => li.textContent.trim()));
    """)

    assert any("Cibeles" in texto for texto in resultado), resultado
    assert not any("ya-no-existe" in texto for texto in resultado), resultado
