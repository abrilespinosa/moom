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
        document.getElementById("filtro-accesibles").click();
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
        document.getElementById("filtro-accesibles").click();

        responder({
          pasanEnElMapa: TODAS_LAS_PARADAS.filter((p) => pasaElFiltroDeModo(p))
                           .map((p) => p.nombre)
                           .sort(),
        });
    """)

    assert resultado["pasanEnElMapa"] == ["Alsacia", "Chueca"]


def test_accesibles_se_cruza_con_el_modo_en_vez_de_sustituirlo(render):
    """
    Era una quinta píldora del grupo excluyente, así que activarla hacía
    desaparecer la EMT y el CRTM enteros. Quien iba en silla buscando una
    parada de BUS accesible leía eso como "no hay ninguna", cuando lo cierto
    es que ese dato no existe: solo el Metro lo publica.

    Ahora son dos ejes independientes y se cruzan.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        const nombres = () => TODAS_LAS_PARADAS.filter((p) => pasaElFiltroDeModo(p))
                                .map((p) => p.nombre).sort();

        document.getElementById("filtro-accesibles").click();
        const soloAcc = nombres();

        // Cruzado con Metro: las accesibles que además son de Metro.
        document.querySelector('[data-filtro="METRO"]').click();
        const metroAcc = nombres();

        // Cruzado con urbano: no hay ninguna, porque la EMT no publica el dato.
        document.querySelector('[data-filtro="EMT"]').click();
        const emtAcc = nombres();

        // Y al apagarlo vuelven todas las de la EMT.
        document.getElementById("filtro-accesibles").click();
        const emtTodas = nombres();

        responder({ soloAcc, metroAcc, emtAcc, emtTodas,
                    pulsado: document.getElementById("filtro-accesibles")
                               .getAttribute("aria-pressed") });
    """)

    assert resultado["soloAcc"] == ["Alsacia", "Chueca"]
    assert resultado["metroAcc"] == ["Alsacia", "Chueca"]
    assert resultado["emtAcc"] == [], "la EMT no publica accesibilidad"
    assert "Cibeles" in resultado["emtTodas"], "al apagarlo vuelven todas"

    # El estado tiene que llegar a un lector de pantalla, no solo verse.
    assert resultado["pulsado"] == "false"


def test_el_nombre_accesible_lleva_todo_lo_que_lleva_la_ficha(render):
    """
    Un aria-label explícito SUSTITUYE al contenido del botón, no lo acompaña.
    Como la ficha lleva dentro el icono, el nombre, la distancia y el
    distintivo de accesibilidad con su .solo-lector, poner solo el nombre en
    la etiqueta silenciaba los otros tres: la píldora de silla de ruedas
    —hecha justo para quien depende de ella— era inaudible.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);

        // Se finge que hay ubicación para que aparezca la distancia.
        ubicacionUsuario = { lat: 40.4183, lon: -3.6240 };

        escribirEnBuscador("alsacia");
        await esperarA(() => resultados().length > 0);
        const fila = resultados().find((li) => li.textContent.includes("Alsacia"));

        responder({
          etiqueta: fila.querySelector(".resultado-principal")
                      .getAttribute("aria-label"),
          hayDistintivo: !!fila.querySelector(".accesibilidad-compacta"),
        });
    """)

    assert resultado["hayDistintivo"] is True
    etiqueta = resultado["etiqueta"]

    assert "Alsacia" in etiqueta
    assert "Metro" in etiqueta
    # Lo que antes se perdía:
    assert "accesibilidad" in etiqueta.lower(), etiqueta
    assert "min" in etiqueta or "metro" in etiqueta.lower(), etiqueta


def test_lo_que_se_sabe_del_bus_se_cuenta_una_vez_y_no_en_cada_ficha(render):
    """
    Los dos hechos de la EMT —flota con rampa y NaviLens— son ciertos y están
    verificados, pero son IDÉNTICOS en las 4.894 paradas. Un distintivo que
    sale siempre no distingue nada: solo ocupa sitio delante del tiempo, que
    es el dato por el que se abre la aplicación.

    Por eso viven en "Planos y tarifas", que se consulta una vez. En Metro es
    al revés y su distintivo sí va en la ficha: allí el dato varía, 166
    estaciones con él y 76 sin él.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        escribirEnBuscador("cibeles");
        await esperarA(() => resultados().length > 0);
        pulsarResultado();
        await esperarA(() => vistaVisible() === "vista-llegadas");
        const fichaBus = document.getElementById("codigo-parada-actual").textContent;

        document.getElementById("boton-volver").click();
        document.getElementById("boton-informacion").click();
        await esperarA(() => vistaVisible() === "vista-informacion");
        const consulta = document.querySelector(".bloque-accesibilidad").textContent;

        responder({ fichaBus, consulta });
    """)

    # En la ficha de la parada, nada: sería ruido en las 4.894.
    assert "NaviLens" not in resultado["fichaBus"]
    assert "rampa" not in resultado["fichaBus"]

    # Contado una vez, donde se consulta.
    assert "NaviLens" in resultado["consulta"]
    assert "rampa" in resultado["consulta"]
    # Y acotando lo que NO se sabe, que es la parte honesta.
    assert "bordillo" in resultado["consulta"] or "acera" in resultado["consulta"]


def test_la_nota_del_filtro_solo_sale_con_el_filtro_puesto(render):
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);
        const nota = document.getElementById("nota-accesibles");
        const antes = nota.getBoundingClientRect().height;

        document.getElementById("filtro-accesibles").click();
        const durante = nota.getBoundingClientRect().height;

        document.getElementById("filtro-accesibles").click();
        responder({ antes, durante, despues: nota.getBoundingClientRect().height,
                    texto: nota.textContent.trim() });
    """)

    assert resultado["antes"] == 0, "la nota no debe salir sin filtrar"
    assert resultado["durante"] > 0, "con el filtro puesto hay que explicar por qué faltan los buses"
    assert resultado["despues"] == 0
    assert "EMT" in resultado["texto"]
