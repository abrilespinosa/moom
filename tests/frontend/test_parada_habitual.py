"""
Los atajos de quien usa la aplicación a diario en la misma parada.

Todo esto solo se nota en la SEGUNDA visita, así que es exactamente el tipo de
comportamiento que se rompe sin que nadie se entere.
"""

import pytest

pytestmark = pytest.mark.navegador


def test_la_ultima_parada_consultada_se_recuerda(render):
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("cibeles");
        await esperarA(() => resultados().length > 0);
        pulsarResultado();
        await esperarA(() => vistaVisible() === "vista-llegadas");

        responder(localStorage.getItem("moom:ultima-parada"));
    """)

    assert resultado == "72"


def test_al_volver_se_ofrece_la_ultima_parada(render):
    """
    Con el buscador vacío tiene que aparecer, sin escribir nada. Es el atajo
    entero: tres gestos menos en cada visita.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        localStorage.setItem("moom:ultima-parada", "72");
        actualizarResultadosBusqueda();
        await esperarA(() => resultados().length > 0);

        responder([...document.querySelectorAll("#lista-resultados li")]
                    .map((li) => li.textContent.trim()));
    """)

    assert any("última que miraste" in t for t in resultado), resultado
    assert any("Cibeles" in t for t in resultado), resultado


def test_una_ultima_parada_que_ya_no_existe_no_rompe_la_lista(render):
    """Mismo caso que los favoritos: los ids caducan con cada volcado GTFS."""
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        localStorage.setItem("moom:ultima-parada", "parada-que-ya-no-existe");
        actualizarResultadosBusqueda();
        await esperarA(() => document.querySelectorAll("#lista-resultados li").length > 0);

        responder([...document.querySelectorAll("#lista-resultados li")]
                    .map((li) => li.textContent.trim()));
    """)

    assert not any("última que miraste" in t for t in resultado), resultado


def test_el_reloj_se_para_con_la_pestana_oculta(render):
    """
    Con el móvil en el bolsillo no hay nada que refrescar. Antes seguía
    pidiendo llegadas cada 10s indefinidamente: batería y cuota de EMT
    gastadas en respuestas que nadie ve.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        const alArrancar = relojDeRefrescos !== null;

        // Se simula que la pestaña se oculta.
        Object.defineProperty(document, "hidden", { value: true, configurable: true });
        document.dispatchEvent(new Event("visibilitychange"));
        const conPestanaOculta = relojDeRefrescos !== null;

        Object.defineProperty(document, "hidden", { value: false, configurable: true });
        document.dispatchEvent(new Event("visibilitychange"));
        const alVolver = relojDeRefrescos !== null;

        responder({ alArrancar, conPestanaOculta, alVolver });
    """)

    assert resultado["alArrancar"] is True
    assert resultado["conPestanaOculta"] is False, "el reloj debía pararse"
    assert resultado["alVolver"] is True, "y volver a arrancar al mirar otra vez"
