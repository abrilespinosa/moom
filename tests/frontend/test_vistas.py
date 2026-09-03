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


def test_el_buscador_va_antes_que_los_filtros_y_que_los_avisos(render):
    """
    El orden del panel es el arreglo del P0 de la crítica: había 333,5 px de
    cromo antes del primer resultado en escritorio, y en la hoja de móvil
    recogida quedaban 58,4 px, así que la primera ficha salía cortada.

    Ahora manda el buscador. Los filtros van detrás porque acotan lo que ya
    hay en pantalla, no lo que todavía no se ha buscado, y los avisos detrás
    de ellos. "Planos y tarifas" se fue al pie: es lo único que se consulta
    antes de salir de casa, y se lo estaba cobrando a cada apertura.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        await esperarA(() => !document.getElementById("boton-incidencias").hidden);

        const arriba = (sel) =>
          document.querySelector(sel).getBoundingClientRect().top;

        responder({
          buscador: arriba("#input-buscar"),
          filtros: arriba("#filtros-fuente"),
          avisos: arriba("#boton-incidencias"),
          planosEnElPie: !!document.querySelector("#pie-legal #boton-informacion"),
        });
    """)

    assert resultado["buscador"] < resultado["filtros"]
    assert resultado["filtros"] < resultado["avisos"]
    assert resultado["planosEnElPie"] is True


def test_los_avisos_no_se_meten_entre_la_parada_y_su_tiempo(render):
    """
    El botón vivía por encima de las cinco vistas, así que en la de llegadas
    se colaba entre el nombre de tu parada y su tiempo, que es el dato por el
    que se abre la aplicación. Ahora vive dentro de la vista de búsqueda.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("cibeles");
        await esperarA(() => resultados().length > 0);
        pulsarResultado();
        await esperarA(() => vistaVisible() === "vista-llegadas");

        const visible = (id) => {
          const e = document.getElementById(id);
          return e.getBoundingClientRect().height > 0;
        };

        responder({
          avisos: visible("boton-incidencias"),
          filtros: visible("filtros-fuente"),
        });
    """)

    assert resultado["avisos"] is False
    assert resultado["filtros"] is False


def test_los_bloques_del_panel_respiran_lo_mismo(render):
    """
    Reportado mirando la pantalla: el botón de avisos salía pegado a la
    bandeja de filtros y el aviso de conexión pegado a la banda naranja.

    Los dos nacieron colocados justo bajo la cabecera, donde el margen
    superior sobraba. Al reordenar el panel quedaron detrás de otros bloques
    y se quedaron sin separación, porque su margen la ponía por abajo.

    El ritmo del panel es de 12px, así que se comprueban todos los bordes de
    la pila y no solo el que se reportó.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        await esperarA(() => !document.getElementById("boton-incidencias").hidden);
        mostrarAvisoConexion("Prueba.");
        await esperarA(() => !document.getElementById("aviso-conexion").hidden);

        const r = (s) => document.querySelector(s).getBoundingClientRect();
        const primera = document.querySelector("#lista-resultados > *");

        responder({
          cabeceraAviso: Math.round(r("#aviso-conexion").top - r("#panel-header").bottom),
          avisoBuscador: Math.round(r("#input-buscar").top - r("#aviso-conexion").bottom),
          buscadorFiltros: Math.round(r(".fila-filtros").top - r("#input-buscar").bottom),
          filtrosAvisos: Math.round(r("#boton-incidencias").top - r(".fila-filtros").bottom),
          avisosFicha: primera
            ? Math.round(primera.getBoundingClientRect().top - r("#boton-incidencias").bottom)
            : null,
        });
    """)

    for borde, hueco in resultado.items():
        assert hueco == 12, f"{borde} respira {hueco}px en vez de 12"
