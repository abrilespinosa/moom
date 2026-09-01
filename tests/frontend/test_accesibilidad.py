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


# --- EL DISTINTIVO Y EL FILTRO DE ESTACIONES ACCESIBLES ---
#
# Lo que se comprueba aquí no es que se pinte un icono, es QUÉ estación lo
# recibe. Los datos vienen de la lista oficial de Metro con tres grados, y uno
# de ellos —"solo_medidas"— tiene encaminamientos y avisos sonoros pero NI
# ascensor NI rampa. Marcarlo con una silla sería el error que más daño hace
# de todos los posibles en esta aplicación, así que tiene test propio.


def test_el_distintivo_sale_en_los_resultados_y_solo_donde_toca(render):
    """
    Antes solo se veía al abrir el panel, o sea DESPUÉS de haber elegido; el
    dato sirve justo para lo contrario, para elegir.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);

        const conDistintivo = (nombre) => {
          escribirEnBuscador(nombre);
          const fila = resultados().find(
            (li) => (li.textContent || "").includes(nombre)
          );
          return fila ? !!fila.querySelector(".accesibilidad-compacta") : null;
        };

        responder({
          universal: conDistintivo("Alsacia"),
          soloAscensor: conDistintivo("Chueca"),
          soloMedidas: conDistintivo("Lavapies"),
          sinDato: conDistintivo("Tirso de Molina"),
          bus: conDistintivo("Cibeles"),
        });
    """)

    assert resultado["universal"] is True
    assert resultado["soloAscensor"] is True

    # Sin ascensor ni rampa: no lleva silla. Para quien va en silla esto es
    # indistinguible de no tener dato, y así debe quedarse.
    assert resultado["soloMedidas"] is False
    assert resultado["sinDato"] is False

    # Ni la EMT ni el CRTM publican accesibilidad por parada, así que en un
    # autobús no puede aparecer nunca.
    assert resultado["bus"] is False


def test_el_filtro_de_accesibles_deja_solo_las_que_lo_son(render):
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        document.querySelector('[data-filtro="accesibles"]').click();
        escribirEnBuscador("a");
        await esperarA(() => resultados().length > 0);

        const filas = resultados();

        responder({
          nombres: filas.map((li) => li.textContent.trim().split("(")[0].trim()),
          // Ninguna línea debe colarse: preguntar por líneas accesibles no
          // significa nada, y no llevan el campo.
          hayLineas: filas.some((li) => li.classList.contains("resultado-linea")),
          todasConDistintivo: filas.every(
            (li) => !!li.querySelector(".accesibilidad-compacta")
          ),
        });
    """)

    assert resultado["hayLineas"] is False
    assert resultado["todasConDistintivo"] is True

    nombres = " · ".join(resultado["nombres"])
    assert "Alsacia" in nombres
    assert "Chueca" in nombres
    # Las dos que no lo son quedan fuera aunque su nombre lleve una "a".
    assert "Lavapies" not in nombres
    assert "Tirso de Molina" not in nombres
    assert "Cibeles" not in nombres


def test_el_mapa_y_la_lista_filtran_con_el_mismo_criterio(render):
    """
    Eran dos copias de la misma regla, una en el buscador y otra en los
    marcadores. Con un filtro que no es un modo de transporte, la copia del
    mapa habría seguido enseñando paradas que la lista ya no enseñaba.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        document.querySelector('[data-filtro="accesibles"]').click();

        responder({
          pasanEnElMapa: TODAS_LAS_PARADAS.filter((p) => pasaElFiltroDeModo(p))
                           .map((p) => p.nombre)
                           .sort(),
        });
    """)

    assert resultado["pasanEnElMapa"] == ["Alsacia", "Chueca"]
