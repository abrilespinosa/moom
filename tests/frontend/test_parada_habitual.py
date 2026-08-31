"""
Los atajos de quien usa la aplicación a diario entre las mismas paradas.

Todo esto solo se nota en la SEGUNDA visita, así que es exactamente el tipo de
comportamiento que se rompe sin que nadie se entere.
"""

import pytest

pytestmark = pytest.mark.navegador


def test_la_parada_consultada_se_guarda_como_reciente(render):
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("cibeles");
        await esperarA(() => resultados().length > 0);
        pulsarResultado();
        await esperarA(() => vistaVisible() === "vista-llegadas");

        responder(JSON.parse(localStorage.getItem("moom:recientes")));
    """)

    assert resultado == ["72"]


def test_la_mas_reciente_va_primera_y_no_se_duplica(render):
    """
    Volver a una parada que ya estaba en la lista la sube arriba en vez de
    añadirla otra vez. Sin esto, ir y volver de la misma parada llenaría las
    tres posiciones con el mismo sitio.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);

        recordarParadaReciente("72");
        recordarParadaReciente("270");
        recordarParadaReciente("72");

        responder(JSON.parse(localStorage.getItem("moom:recientes")));
    """)

    assert resultado == ["72", "270"]


def test_solo_se_guardan_tres(render):
    """Cuatro paradas distintas: la más antigua se cae."""
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);

        ["72", "270", "par_8_06002", "est_4_323"].forEach(recordarParadaReciente);

        responder(JSON.parse(localStorage.getItem("moom:recientes")));
    """)

    assert resultado == ["est_4_323", "par_8_06002", "270"]
    assert len(resultado) == 3


def test_al_volver_se_ofrecen_las_recientes(render):
    """
    Con el buscador vacío tienen que aparecer, sin escribir nada. Es el atajo
    entero: tres gestos menos en cada visita.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        localStorage.setItem("moom:recientes", JSON.stringify(["72", "270"]));
        actualizarResultadosBusqueda();
        await esperarA(() => resultados().length > 0);

        responder([...document.querySelectorAll("#lista-resultados li")]
                    .map((li) => li.textContent.trim()));
    """)

    assert any("Recientes" in t for t in resultado), resultado
    assert any("Cibeles" in t for t in resultado), resultado
    assert any("Atocha" in t for t in resultado), resultado


def test_una_reciente_que_ya_no_existe_se_omite(render):
    """Mismo caso que los favoritos: los ids caducan con cada volcado GTFS."""
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        localStorage.setItem(
          "moom:recientes",
          JSON.stringify(["72", "parada-que-ya-no-existe"])
        );
        actualizarResultadosBusqueda();
        await esperarA(() => resultados().length > 0);

        responder([...document.querySelectorAll("#lista-resultados li")]
                    .map((li) => li.textContent.trim()));
    """)

    assert any("Cibeles" in t for t in resultado), resultado
    assert not any("ya-no-existe" in t for t in resultado), resultado


def test_la_clave_antigua_se_limpia(render):
    """
    Antes se guardaba una sola parada en "moom:ultima-parada". Se borra al
    escribir la nueva para no dejar basura en el navegador de quien la tuviera.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        localStorage.setItem("moom:ultima-parada", "270");
        recordarParadaReciente("72");

        responder({
          antigua: localStorage.getItem("moom:ultima-parada"),
          nueva: JSON.parse(localStorage.getItem("moom:recientes")),
        });
    """)

    assert resultado["antigua"] is None
    assert resultado["nueva"] == ["72"]


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
