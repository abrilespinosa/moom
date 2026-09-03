"""
Cada vista tiene su dirección.

Sin esto la barra de direcciones decía lo mismo en las cinco vistas, y de ahí
salían cuatro cosas a la vez: no se podía guardar una parada en marcadores ni
en la pantalla de inicio, no se podía compartir, recargar volvía al principio,
y el gesto de atrás del móvil sacaba de la aplicación entera porque no había
historial que recorrer.
"""

import pytest

pytestmark = pytest.mark.navegador


def test_abrir_una_parada_escribe_su_direccion(render):
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("cibeles");
        await esperarA(() => resultados().length > 0);
        pulsarResultado();
        await esperarA(() => vistaVisible() === "vista-llegadas");

        responder(location.hash);
    """)

    assert resultado == "#/parada/72"


def test_una_direccion_de_parada_abre_esa_parada(render):
    """
    El camino que importa: alguien pega el enlace o abre su marcador.

    Entra por seleccionarParada() y no pintando a mano, para no saltarse la
    limpieza de marcadores ni las protecciones contra respuestas que llegan
    tarde.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);

        location.hash = "#/parada/est_4_323";
        await esperarA(() => vistaVisible() === "vista-llegadas");

        responder({
          vista: vistaVisible(),
          nombre: document.getElementById("nombre-parada-actual").textContent,
        });
    """)

    assert resultado["vista"] == "vista-llegadas"
    assert "Alsacia" in resultado["nombre"]


def test_volver_devuelve_la_direccion_al_buscador(render):
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("cibeles");
        await esperarA(() => resultados().length > 0);
        pulsarResultado();
        await esperarA(() => vistaVisible() === "vista-llegadas");

        document.getElementById("boton-volver").click();
        await esperarA(() => vistaVisible() === "vista-busqueda");

        responder(location.hash);
    """)

    assert resultado in ("#/", "")


def test_una_parada_que_ya_no_existe_no_rompe_nada(render):
    """
    Un volcado GTFS nuevo puede renumerar una parada, así que un enlace
    guardado hace meses puede apuntar a algo que ya no está. Eso no es culpa
    de quien lo guardó: se abre el buscador y ya, sin error en pantalla.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);

        location.hash = "#/parada/no-existe-esta-parada";
        await esperarA(() => vistaVisible() === "vista-busqueda", 4000);

        responder({
          vista: vistaVisible(),
          aviso: document.getElementById("aviso-conexion").hidden,
        });
    """)

    assert resultado["vista"] == "vista-busqueda"
    assert resultado["aviso"] is True, "no debe salir el aviso de conexión"
