"""
Que al salir de una estación de Metro no queden trenes en el mapa.

El fallo, reportado en uso real: se entra en una estación, se pulsa Volver, y
los trenes se quedaban dibujados para siempre.

La causa era una carrera. Los pollers comprobaban la estación solo AL ENTRAR
en la función, pero luego esperaban al CRTM entre 0,1 y 4,5 segundos. Si en ese
hueco se pulsaba Volver, la limpieza ocurría ANTES que la respuesta, y la
respuesta volvía a pintar los trenes. Como el siguiente ciclo salía por el
return inicial, ya nadie los limpiaba nunca.
"""

import pytest

pytestmark = pytest.mark.navegador


def test_al_volver_no_quedan_trenes_en_el_mapa(render):
    """
    OJO: este test describe el comportamiento esperado, pero NO es el que
    caza el fallo. Con el backend de mentira la respuesta llega al instante,
    así que no hay hueco donde colarse y pasa incluso con las guardas
    quitadas. Comprobado.

    El que protege de verdad es el siguiente, que provoca la carrera a mano.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("alsacia");
        await esperarA(() => resultados().length > 0);
        pulsarResultado();

        await esperarA(() => vistaVisible() === "vista-llegadas");
        await esperarA(() => marcadoresTrenesActuales.length > 0);

        const conLaEstacionAbierta = marcadoresTrenesActuales.length;

        document.getElementById("boton-volver").click();

        // Se le da tiempo de sobra a cualquier respuesta que viniera en vuelo.
        await new Promise((listo) => setTimeout(listo, 2500));

        responder({
          conLaEstacionAbierta,
          alSalir: marcadoresTrenesActuales.length,
          estacion: STOP_ID_METRO,
        });
    """)

    assert resultado["conLaEstacionAbierta"] > 0, "el test no probó nada"
    assert resultado["alSalir"] == 0, "quedaron trenes en el mapa tras salir"
    assert resultado["estacion"] is None


def test_una_respuesta_tardia_no_pinta_trenes_de_otra_estacion(render):
    """
    La carrera, provocada a mano: se lanza el poller y se sale ANTES de que
    llegue la respuesta. Sin la comprobación posterior a la espera, esos
    trenes se pintarían igualmente.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("alsacia");
        await esperarA(() => resultados().length > 0);
        pulsarResultado();
        await esperarA(() => vistaVisible() === "vista-llegadas");

        // Se lanza el poller y, sin esperarlo, se sale.
        const enVuelo = actualizarTrenesMetro();
        document.getElementById("boton-volver").click();
        await enVuelo;
        await new Promise((listo) => setTimeout(listo, 1500));

        responder(marcadoresTrenesActuales.length);
    """)

    assert resultado == 0, "una respuesta tardía repintó los trenes"
