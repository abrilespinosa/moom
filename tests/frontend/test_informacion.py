"""
Planos y tarifas: la vista de consulta.

Lo que se comprueba no es que se pinte una lista, sino las tres cosas que la
hacen honesta: que los enlaces salgan a los canales oficiales, que el peso de
cada plano esté a la vista antes de pulsarlo, y que los precios lleven fecha.
"""

import pytest

pytestmark = pytest.mark.navegador

# Los únicos hosts a los que puede apuntar esto. Coincide con lo declarado en
# frontend/privacidad.html; si aparece otro, el test de terceros también salta.
HOSTS_OFICIALES = ("www.metromadrid.es", "www.crtm.es")


def test_el_boton_esta_siempre_y_abre_la_vista(render):
    """
    Al revés que el de avisos, que solo aparece cuando pasa algo: este es
    consulta, y hace falta justo cuando no te sabes la red.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        const b = document.getElementById("boton-informacion");
        const visibleAntes = b.getBoundingClientRect().height > 0;

        b.click();
        await esperarA(() => vistaVisible() === "vista-informacion");

        responder({
          visibleAntes,
          vista: vistaVisible(),
          titulos: [...document.querySelectorAll(".informacion-titulo")]
                     .map((h) => h.textContent.trim()),
        });
    """)

    assert resultado["visibleAntes"] is True
    assert resultado["vista"] == "vista-informacion"
    assert resultado["titulos"] == ["Planos", "Billetes y tarifas"]


def test_cada_plano_dice_lo_que_pesa_antes_de_abrirlo(render):
    """
    El esquemático son 6,2 MB. En la calle y con datos móviles, saberlo antes
    es la diferencia entre abrirlo y arrepentirse.
    """
    resultado = render("""
        document.getElementById("boton-informacion").click();
        await esperarA(() => vistaVisible() === "vista-informacion");

        responder([...document.querySelectorAll(".ficha-enlace")].map((f) => ({
          titulo: f.querySelector(".ficha-titulo").textContent.trim(),
          peso: f.querySelector(".ficha-peso")
                  ? f.querySelector(".ficha-peso").textContent.trim()
                  : null,
          url: f.querySelector("a").getAttribute("href"),
          destino: f.querySelector("a").getAttribute("target"),
          rel: f.querySelector("a").getAttribute("rel"),
        })));
    """)

    planos = [f for f in resultado if f["url"].endswith(".pdf")]
    assert planos, "sin planos en PDF no se prueba nada"

    for ficha in planos:
        assert ficha["peso"], f"{ficha['titulo']} no dice lo que pesa"
        assert "MB" in ficha["peso"]

    # Y ninguno se sirve desde aquí: son documentos de Metro y del CRTM.
    for ficha in resultado:
        assert ficha["url"].startswith("https://"), ficha["url"]
        assert any(h in ficha["url"] for h in HOSTS_OFICIALES), ficha["url"]
        # target _blank sin noopener le da a la página de destino una
        # referencia a la nuestra por window.opener.
        assert ficha["destino"] == "_blank"
        assert "noopener" in (ficha["rel"] or "")


def test_los_precios_llevan_la_fecha_desde_la_que_valen(render):
    """
    Cambian al menos una vez al año —en 2025 cambiaron dos veces— y desde aquí
    no hay forma de enterarse. Un precio viejo sin fecha es una mentira; con
    la fecha delante sigue informando, que es el principio del proyecto.
    """
    resultado = render("""
        document.getElementById("boton-informacion").click();
        await esperarA(() => vistaVisible() === "vista-informacion");

        const precios = [...document.querySelectorAll(".tarifa-precio")]
                          .map((p) => p.textContent.trim());

        responder({
          vigencia: document.querySelector(".informacion-vigencia").textContent.trim(),
          cuantos: precios.length,
          // Todos tienen que ser una cantidad, no un hueco vacío.
          todosConImporte: precios.every((p) => /\\d/.test(p)),
        });
    """)

    assert "2026" in resultado["vigencia"]
    assert resultado["cuantos"] > 10
    assert resultado["todosConImporte"] is True


def test_volver_regresa_a_donde_se_estaba(render):
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("cibeles");
        await esperarA(() => resultados().length > 0);
        pulsarResultado();
        await esperarA(() => vistaVisible() === "vista-llegadas");

        document.getElementById("boton-informacion").click();
        await esperarA(() => vistaVisible() === "vista-informacion");

        document.getElementById("boton-volver-informacion").click();
        responder(vistaVisible());
    """)

    assert resultado == "vista-llegadas"
