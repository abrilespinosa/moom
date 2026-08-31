"""
El buscador: qué sale y en qué orden.

Es la parte del frontend con más decisiones tomadas a mano, y por tanto la
que más se puede romper sin que nadie se entere: el orden de los resultados
no salta a la vista al abrir la página.
"""

import pytest

pytestmark = pytest.mark.navegador


def test_buscar_un_numero_pone_primero_la_linea_exacta(render):
    """
    Quien escribe "27" quiere la línea 27, no la 270. Las dos empiezan igual,
    así que sin el desempate explícito de buscarLineas() el orden lo decidiría
    el archivo GTFS, que no tiene por qué poner antes la corta.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_LINEAS.length > 0);
        escribirEnBuscador("27");
        await esperarA(() => resultados().length > 0);
        responder(resultados().map((li) => li.textContent.trim()));
    """)

    assert "Plaza Castilla" in resultado[0], resultado
    assert any("Canillejas" in texto for texto in resultado), (
        "la 270 debería seguir apareciendo, solo que después"
    )


def test_las_lineas_van_antes_que_las_paradas(render):
    """
    Buscando un número, lo que se busca casi siempre es una línea. Las paradas
    que llevan ese número dentro del código van después.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_LINEAS.length > 0);
        escribirEnBuscador("27");
        await esperarA(() => resultados().length > 0);
        responder(resultados().map((li) => li.className));
    """)

    clases_de_linea = [i for i, c in enumerate(resultado) if "resultado-linea" in c]
    clases_de_parada = [i for i, c in enumerate(resultado) if "resultado-linea" not in c]

    if clases_de_parada:
        assert max(clases_de_linea) < min(clases_de_parada), resultado


def test_el_filtro_de_modo_recorta_los_resultados(render):
    """
    Cambiar de filtro rehace la búsqueda. Con Metro activo no puede colarse
    una línea de EMT, aunque su número coincida.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_LINEAS.length > 0);

        document.querySelector('.filtro-boton[data-filtro="METRO"]').click();
        escribirEnBuscador("2");
        await esperarA(() => resultados().length > 0);

        responder({
          filtro: filtroActivo,
          textos: resultados().map((li) => li.textContent.trim()),
        });
    """)

    assert resultado["filtro"] == "METRO"
    assert resultado["textos"], "con el filtro de Metro debería quedar algo"
    assert all("Bus" not in texto for texto in resultado["textos"]), resultado["textos"]


def test_una_parada_ensena_el_codigo_de_la_marquesina(render):
    """
    codigoDeParada() quita el prefijo del volcado: par_8_06002 -> 06002. El
    prefijo le sirve al backend para elegir API, pero en la marquesina está
    escrito el código corto, que es el que la persona puede comparar.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("america");
        await esperarA(() => resultados().length > 0);
        responder(resultados()[0].textContent.trim());
    """)

    assert "06002" in resultado
    assert "par_8_" not in resultado
