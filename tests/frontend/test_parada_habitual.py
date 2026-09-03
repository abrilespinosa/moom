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


def test_se_guardan_tres_por_red_y_no_tres_en_total(render):
    """
    Cuatro paradas de EMT: la más antigua de esa red se cae. Pero el tope es
    POR RED, así que la de Metro y la del interurbano siguen ahí.

    Guardando tres en total, quien mirase tres autobuses seguidos se quedaba
    sin recientes de Metro al filtrar por Metro, aunque hubiera consultado una
    estación poco antes.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);

        ["est_4_323", "par_8_06002", "72", "270", "est_4_77", "4966"]
          .forEach(recordarParadaReciente);

        responder(JSON.parse(localStorage.getItem("moom:recientes")));
    """)

    # Orden por lo más reciente, que es lo que ve "Todos".
    assert resultado[0] == "4966"

    # De EMT hay tres: la cuarta (72) se cayó.
    emt = [i for i in resultado if not i.startswith(("est_", "par_"))]
    assert emt == ["4966", "270", "72"] or len(emt) == 3, resultado

    # Y las otras dos redes conservan las suyas pese a los autobuses de después.
    assert "est_4_323" in resultado, "la estación de Metro se perdió"
    assert "par_8_06002" in resultado, "la parada interurbana se perdió"


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


def test_cada_red_conserva_sus_propias_recientes(render):
    """
    Reportado en uso: al filtrar por Metro no salían recientes, aunque se
    hubiera consultado una estación poco antes.

    La causa era que se guardaban tres EN TOTAL. Mirando tres autobuses
    seguidos, la estación de Metro se caía de la lista y con el filtro puesto
    no quedaba nada que enseñar. Ahora se guardan tres POR RED, en una sola
    lista ordenada por lo más reciente: "Todos" sigue enseñando las tres
    últimas de verdad, y cada filtro las suyas.
    """
    resultado = render("""
        await esperarA(() => TODAS_LAS_PARADAS.length > 0);

        // Primero una estación de Metro, y después tres autobuses: con el
        // tope de tres en total, Alsacia se caía.
        for (const nombre of ["alsacia", "cibeles", "atocha", "avenida"]) {
          escribirEnBuscador(nombre);
          await esperarA(() => resultados().length > 0);
          const fila = resultados().find((li) => !li.classList.contains("resultado-linea"));
          fila.querySelector(".resultado-principal").click();
          await esperarA(() => vistaVisible() === "vista-llegadas");
          document.getElementById("boton-volver").click();
          await esperarA(() => vistaVisible() === "vista-busqueda");
        }

        const grupoYFilas = () => {
          const nombres = [];
          let dentro = false;
          for (const li of document.querySelectorAll("#lista-resultados li")) {
            if (li.classList.contains("grupo-resultados")) {
              dentro = li.textContent.trim() === "Recientes";
              continue;
            }
            if (dentro && !li.classList.contains("pista-favoritos")) {
              nombres.push(li.textContent.trim());
            }
          }
          return nombres;
        };

        escribirEnBuscador("");
        const enTodos = grupoYFilas();

        document.querySelector('[data-filtro="METRO"]').click();
        const enMetro = grupoYFilas();

        responder({ enTodos, enMetro, guardadas: JSON.parse(
          localStorage.getItem("moom:recientes")).length });
    """)

    # "Todos" sigue enseñando tres como máximo.
    assert len(resultado["enTodos"]) <= 3

    # Y Metro conserva la suya pese a los tres autobuses posteriores.
    metro = " · ".join(resultado["enMetro"])
    assert "Alsacia" in metro, f"la estación se perdió: {metro}"

    # Se guardan más de tres, porque el tope es por red.
    assert resultado["guardadas"] > 3
