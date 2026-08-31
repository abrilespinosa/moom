import pytest

pytestmark = pytest.mark.navegador


def test_la_pagina_arranca_y_pinta_las_paradas(render):
    """Prueba de humo: si esto falla, app.js ha reventado al cargar."""
    resultado = render("""
        await esperarA(() => document.querySelectorAll("#lista-resultados li").length > 0);
        responder({ titulo: document.title, vista: vistaVisible() });
    """)

    assert "Moom" in resultado["titulo"]
    assert resultado["vista"] == "vista-busqueda"
