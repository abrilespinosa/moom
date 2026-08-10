// URL de tu servidor FastAPI corriendo en local
const URL_BACKEND = "http://127.0.0.1:8000";

// Número de parada que vamos a consultar
let STOP_ID = null;

// Código de estación de Metro actualmente seleccionada (formato CRTM,
// ej. "est_90_58"). Separado de STOP_ID porque Metro usa su propio
// endpoint y su propio intervalo de refresco.
let STOP_ID_METRO = null;

let marcadoresTrenesActuales = [];

// Guardamos aquí todas las paradas descargadas, para poder
// buscarlas localmente sin volver a llamar al backend.
let TODAS_LAS_PARADAS = [];

// Número y colores oficiales de cada línea de Metro, indexados por su
// código ("4__2___"). Son 13 líneas y no cambian nunca, así que se piden
// UNA sola vez al arrancar en vez de por cada estación que se selecciona.
let COLORES_LINEAS_METRO = {};

// Filtro de fuente activo: "todos", "EMT" (urbano) o "CRTM" (interurbano).
// Lo consulta actualizarVisibilidadParadas() para decidir qué paradas
// dibujar, junto con el zoom y el área visible.
let filtroActivo = "todos";

// Creamos el mapa centrado en Madrid. Zoom 14 muestra ya el detalle
// de la ciudad (barrios, calles principales) en vez de toda la
// Comunidad de Madrid, que se veía vacía con el estilo minimalista.
const mapa = L.map("mapa").setView([40.4168, -3.7038], 14);

// CartoDB "Voyager": más detalle y calidez que Positron (colores
// suaves en parques/agua, nombres de barrio) sin llegar a la
// densidad del OSM estándar. Mismo proveedor, gratuito, sin API key.
L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
  {
    attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
  }
).addTo(mapa);

// Nivel de zoom a partir del cual se muestran las paradas. Por debajo
// de este nivel, Madrid entera tendría miles de puntos superpuestos,
// así que las ocultamos hasta que el usuario haga zoom a un barrio.
const ZOOM_MINIMO_PARADAS = 15;

// Guardamos aquí cada círculo de parada junto con su marcador Leaflet,
// para poder añadirlo o quitarlo del mapa según el zoom actual.
let marcadoresParadas = [];

// Tamaño con el que se renderiza cada icono de parada en el mapa.
// iconAnchor = [mitad del ancho, alto completo] ancla la imagen por
// su base (donde están las ruedas del bus dibujado), igual que un
// pin de Google Maps ancla por su punta inferior.
// IMPORTANTE: estos tamaños respetan la proporción real de cada PNG
// (ya recortado a su contenido, sin sobrante transparente). Si el
// ratio ancho/alto del icono no coincide con [ancho, alto] aquí,
// Leaflet ESTIRA la imagen para encajarla y el bus se ve deformado.
// normal: ratio 426/512 (0.832) | seleccionado: ratio 506/512 (0.988)
// — son distintos entre sí porque el borde blanco ensancha más de
// lo que alarga, así que cada estado necesita su propio tamaño.
const TAMANO_ICONO_NORMAL = [25, 30];
const TAMANO_ICONO_SELECCIONADO = [39, 39];

// El rombo de Metro tiene una proporción muy distinta a los iconos de
// bus (es ancho, no vertical): ratio ~1.66:1 en la versión normal y
// ~1.60:1 en la seleccionada (el contorno blanco no cambia el ratio
// tanto como pasaba con el borde grueso de los iconos de bus). Por eso
// necesita su propio tamaño en vez de reutilizar TAMANO_ICONO_NORMAL.
const TAMANO_ICONO_METRO_NORMAL = [30, 18];
const TAMANO_ICONO_METRO_SELECCIONADO = [46, 29];

function crearIcono(archivo, tamano) {
  return L.icon({
    iconUrl: `assets/${archivo}`,
    iconSize: tamano,
    iconAnchor: [tamano[0] / 2, tamano[1]],
  });
}

// Los iconos se crean UNA sola vez y se reutilizan para todas las
// paradas/estaciones. Nunca se crea un icono nuevo por parada.
const ICONOS = {
  EMT: {
    normal: crearIcono("bus-urbano.png", TAMANO_ICONO_NORMAL),
    seleccionado: crearIcono("bus-urbano-selected.png", TAMANO_ICONO_SELECCIONADO),
  },
  CRTM: {
    normal: crearIcono("bus-interurbano.png", TAMANO_ICONO_NORMAL),
    seleccionado: crearIcono("bus-interurbano-selected.png", TAMANO_ICONO_SELECCIONADO),
  },
  METRO: {
    normal: crearIcono("metro.png", TAMANO_ICONO_METRO_NORMAL),
    seleccionado: crearIcono("metro-selected.png", TAMANO_ICONO_METRO_SELECCIONADO),
  },
};

// Dado el campo "fuente" de una parada ("EMT" o "CRTM"), devuelve el
// icono normal correspondiente. Si algún día llega una fuente nueva
// que no esperamos, usamos EMT como valor por defecto en vez de romper.
function iconoNormalPara(parada) {
  return ICONOS[parada.fuente]?.normal ?? ICONOS.EMT.normal;
}

function iconoSeleccionadoPara(parada) {
  return ICONOS[parada.fuente]?.seleccionado ?? ICONOS.EMT.seleccionado;
}

// Guardamos qué parada está resaltada ahora, para poder devolverla
// a su estilo normal cuando el usuario seleccione otra distinta.
let paradaSeleccionada = null;

// Opacidad de las paradas que NO son la seleccionada, mientras hay alguna
// seleccionada. Con zoom 17 el mapa se llena de iconos de parada que
// compiten con los vehículos, que es lo que de verdad se está mirando.
// Atenuarlas en vez de ocultarlas conserva la referencia de qué hay
// alrededor, y se deshace solo con volver al buscador.
const OPACIDAD_PARADA_ATENUADA = 0.35;

// Los vehículos (autobuses y trenes) van por encima de los iconos de
// parada, para que no queden tapados por ellos. Por debajo del marcador
// de ubicación, que usa 1000.
const Z_INDEX_VEHICULOS = 500;

async function dibujarParadas() {
  const respuesta = await fetch(`${URL_BACKEND}/paradas`);
  const paradas = await respuesta.json();

  TODAS_LAS_PARADAS = paradas;

  paradas.forEach((parada) => {
    // OJO: ya no usamos ".addTo(mapa)" aquí. Creamos el marcador pero
    // no lo añadimos todavía — eso lo decide actualizarVisibilidadParadas().
    const marcador = L.marker([parada.lat, parada.lon], {
      icon: iconoNormalPara(parada),
    });

    marcador.on("click", () => {
      seleccionarParada(parada);
    });

    // Guardamos el marcador dentro de la propia parada. Así, cuando
    // seleccionarParada() se llama desde el buscador (que solo tiene
    // los datos, no el marcador), igualmente podemos encontrarlo.
    parada.circuloEnMapa = marcador;

    // Y guardamos la referencia inversa: el marcador necesita saber
    // de qué parada es para poder consultar su "fuente" al filtrar,
    // sin tener que buscar en el array de 13.320 paradas cada vez.
    marcador.parada = parada;

    marcadoresParadas.push(marcador);
  });

  // Una vez creados todos los círculos, decidimos cuáles mostrar
  // según el zoom con el que arrancó el mapa.
  actualizarVisibilidadParadas();
}

// Añade o quita los marcadores de parada del mapa según el zoom Y el
// área visible actual. Antes solo filtrábamos por zoom: al cruzar
// ZOOM_MINIMO_PARADAS, las ~13.320 paradas se recorrían igual, pero
// con circleMarker (forma vectorial barata) no se notaba el coste.
// Ahora cada parada es una imagen PNG, más cara de crear/posicionar,
// así que añadir potencialmente miles de golpe causaba el lag al
// cruzar el zoom. getBounds() nos da el rectángulo visible actual;
// con eso, solo se añaden las paradas que realmente se ven en pantalla
// (normalmente decenas, no miles), sin tocar la lógica de zoom.
function actualizarVisibilidadParadas() {
  const zoomActual = mapa.getZoom();
  const zoomSuficiente = zoomActual >= ZOOM_MINIMO_PARADAS;
  const limitesVisibles = mapa.getBounds();

  marcadoresParadas.forEach((marcador) => {
    const estaEnElMapa = mapa.hasLayer(marcador);
    const dentroDeVista = limitesVisibles.contains(marcador.getLatLng());

    // Cada marcador necesita saber a qué parada pertenece para poder
    // consultar su "fuente". Lo guardamos en el siguiente paso, al
    // crear el marcador en dibujarParadas().
    const pasaElFiltro =
      filtroActivo === "todos" || marcador.parada.fuente === filtroActivo;

    const debeVerse = zoomSuficiente && dentroDeVista && pasaElFiltro;

    if (debeVerse && !estaEnElMapa) {
      marcador.addTo(mapa);
    } else if (!debeVerse && estaEnElMapa) {
      mapa.removeLayer(marcador);
    }

    // La opacidad se decide aquí, y no al seleccionar la parada, porque
    // los marcadores entran y salen del mapa constantemente al moverlo:
    // uno que aparece en pantalla estando ya seleccionada otra parada
    // tiene que nacer atenuado, no a plena opacidad.
    if (debeVerse) {
      const esLaSeleccionada = marcador.parada === paradaSeleccionada;
      const debeAtenuarse = paradaSeleccionada !== null && !esLaSeleccionada;
      marcador.setOpacity(debeAtenuarse ? OPACIDAD_PARADA_ATENUADA : 1);
    }
  });
}

// Reevaluamos qué paradas mostrar tanto al hacer zoom (zoomend) como
// al arrastrar el mapa (moveend) — si no escucháramos moveend, al
// desplazarte sin cambiar de zoom las paradas nuevas que entran en
// pantalla no aparecerían hasta el siguiente zoom.
mapa.on("zoomend", actualizarVisibilidadParadas);
mapa.on("moveend", actualizarVisibilidadParadas);

dibujarParadas();

// Los colores de línea se cargan una vez al arrancar. Si esta petición
// fallara, COLORES_LINEAS_METRO se queda vacío y los chips simplemente no
// se pintan: es información decorativa, no debe impedir que se vean los
// tiempos de llegada.
async function cargarColoresLineasMetro() {
  try {
    const respuesta = await fetch(`${URL_BACKEND}/metro/lineas/colores`);
    COLORES_LINEAS_METRO = await respuesta.json();
  } catch (error) {
    console.error("No se pudieron cargar los colores de las líneas:", error);
  }
}

cargarColoresLineasMetro();

// --- Referencias a los elementos del DOM que vamos a manipular ---
const inputBuscar = document.getElementById("input-buscar");
const listaResultados = document.getElementById("lista-resultados");
const vistaBusqueda = document.getElementById("vista-busqueda");
const vistaLlegadas = document.getElementById("vista-llegadas");
const nombreParadaActual = document.getElementById("nombre-parada-actual");
const codigoParadaActual = document.getElementById("codigo-parada-actual");
const iconoParadaActual = document.getElementById("icono-parada-actual");
const chipsLineas = document.getElementById("chips-lineas");
const tituloSeccion = document.getElementById("titulo-seccion");
const listaLlegadas = document.getElementById("lista-llegadas");
const botonVolver = document.getElementById("boton-volver");
const subtituloHeader = document.getElementById("subtitulo-header");
const botonesFiltro = document.querySelectorAll(".filtro-boton");

// Un solo listener sirve para los tres botones: leemos data-filtro
// del botón pulsado en vez de tener una función distinta por botón.
botonesFiltro.forEach((boton) => {
  boton.addEventListener("click", () => {
    filtroActivo = boton.dataset.filtro;

    // Solo un botón puede estar "activo" (resaltado) a la vez.
    botonesFiltro.forEach((b) => b.classList.remove("activo"));
    boton.classList.add("activo");

    actualizarVisibilidadParadas();
  });
});

// --- Lógica del buscador ---
inputBuscar.addEventListener("input", () => {
  const texto = inputBuscar.value.toLowerCase().trim();
  listaResultados.innerHTML = "";

  if (texto === "") {
    return;
  }

  const coincidencias = TODAS_LAS_PARADAS.filter(
    (parada) =>
      parada.nombre.toLowerCase().includes(texto) ||
      parada.id.includes(texto)
  ).slice(0, 15);

  coincidencias.forEach((parada) => {
    const item = document.createElement("li");
    item.textContent = `${parada.nombre} (parada ${parada.id})`;
    item.addEventListener("click", () => seleccionarParada(parada));
    listaResultados.appendChild(item);
  });
});

// Se llama tanto al hacer clic en el mapa como al elegir un resultado
// de búsqueda. Centraliza el cambio de vista para no repetir código.
function seleccionarParada(parada) {
  // Solo una de las dos puede estar "activa" a la vez. Si seleccionas
  // una estación de Metro, STOP_ID de bus se limpia, y viceversa, para
  // que los dos intervalos (actualizarAutobuses / actualizarTiemposMetro)
  // no sigan refrescando datos de una parada que ya no se está viendo.
  if (parada.fuente === "METRO") {
    STOP_ID = null;
    STOP_ID_METRO = parada.id;
  } else {
    STOP_ID = parada.id;
    STOP_ID_METRO = null;
  }

  // Limpiamos SIEMPRE los vehículos de los dos modos, no solo los del que
  // acabamos de abandonar.
  //
  // Cada poller borra sus propios marcadores antes de redibujarlos, pero
  // esa limpieza está DESPUÉS de su salida temprana: al pasar de una
  // parada de bus a una de Metro, STOP_ID se acaba de poner a null, así
  // que actualizarAutobuses() sale por el "return" del principio y nunca
  // llega a borrar nada. Los autobuses de la parada anterior se quedaban
  // en el mapa hasta pulsar "Volver a buscar" (y lo mismo con los trenes
  // al hacer el cambio contrario).
  //
  // Limpiar aquí los dos es seguro: justo al final de esta función se
  // llama al poller del modo elegido, que vuelve a dibujar los suyos.
  limpiarMarcadoresAutobuses();
  limpiarMarcadoresTrenes();
  limpiarChipsLineas();

  // Si había una parada resaltada de antes, le devolvemos su icono
  // normal antes de resaltar la nueva.
  if (paradaSeleccionada && paradaSeleccionada.circuloEnMapa) {
    paradaSeleccionada.circuloEnMapa.setIcon(iconoNormalPara(paradaSeleccionada));
  }

  // Resaltamos la parada recién elegida, si su marcador está dibujado
  // en el mapa (puede no estarlo si el zoom actual es muy bajo).
  if (parada.circuloEnMapa) {
    parada.circuloEnMapa.setIcon(iconoSeleccionadoPara(parada));
  }
  paradaSeleccionada = parada;

  // Centramos el mapa en la parada elegida, con buen zoom
  mapa.setView([parada.lat, parada.lon], 17);

  // Y reevaluamos la opacidad de todas las paradas visibles: acaba de
  // cambiar cuál es la seleccionada. No basta con el "moveend" que
  // dispara setView, porque si vuelves a elegir la misma parada el mapa
  // no se mueve y ese evento no llega.
  actualizarVisibilidadParadas();

  // Cambiamos de vista: ocultamos buscador, mostramos llegadas
  vistaBusqueda.style.display = "none";
  vistaLlegadas.style.display = "flex";
  subtituloHeader.textContent = "Próximas llegadas";

  pintarCabeceraParada(parada);

  // "Tiempos reales" es el nombre que usa la app oficial para el panel de
  // Metro; en autobús encaja mejor hablar de llegadas.
  tituloSeccion.textContent =
    parada.fuente === "METRO" ? "Tiempos reales" : "Próximas llegadas";

  // Limpiamos el buscador para la próxima vez que se use
  inputBuscar.value = "";
  listaResultados.innerHTML = "";

  // Las estaciones de Metro usan un endpoint y un formato de respuesta
  // distintos a las paradas de bus (EMT/CRTM), así que necesitamos
  // distinguirlas aquí y llamar a la función de actualización correcta.
  if (parada.fuente === "METRO") {
    actualizarTiemposMetro();
    actualizarTrenesMetro();
  } else {
    actualizarAutobuses();
  }
}

// Botón para volver del estado "llegadas" al estado "buscador"
botonVolver.addEventListener("click", () => {
  STOP_ID = null;
  STOP_ID_METRO = null;
  vistaLlegadas.style.display = "none";
  vistaBusqueda.style.display = "block";
  subtituloHeader.textContent = "Busca una parada para ver sus llegadas";

  // Quitamos el resaltado, ya no hay una parada "activa"
  if (paradaSeleccionada && paradaSeleccionada.circuloEnMapa) {
    paradaSeleccionada.circuloEnMapa.setIcon(iconoNormalPara(paradaSeleccionada));
  }
  paradaSeleccionada = null;

  // Ya no hay parada seleccionada, así que todas vuelven a plena opacidad.
  actualizarVisibilidadParadas();

  // Limpiamos las tarjetas de la parada anterior...
  listaLlegadas.innerHTML = "";

  // ...y también los marcadores de bus que quedaban en el mapa.
  limpiarMarcadoresAutobuses();
  limpiarMarcadoresTrenes();
  limpiarChipsLineas();
});

// Convierte segundos en un texto legible: "En camino" si está muy
// cerca, o "X min" en caso contrario.
function formatearMinutos(segundos) {
  const minutos = Math.floor(segundos / 60);
  return minutos < 1 ? "En camino" : `${minutos}`;
}

// Cada fuente se refresca al ritmo al que de verdad cambian sus datos,
// no al que nos gustaría que cambiaran.
//
// EMT (autobuses): 10s. La API devuelve segundos restantes hasta la
// llegada, que van bajando de forma continua, así que refrescar seguido
// sí aporta información nueva.
//
// CRTM (Metro): 20s. Medido en vivo contra la API, el CRTM solo actualiza
// las posiciones de los trenes cada 20-30s, y la caché de tiempos de
// espera del backend es también de 20s. Pedirlo cada 10s significaba que
// una de cada dos peticiones devolvía exactamente lo mismo que la
// anterior: el doble de tráfico para cero información nueva.
const INTERVALO_REFRESCO_EMT = 10000;
const INTERVALO_REFRESCO_METRO = 20000;

// Guardamos los marcadores actuales del mapa para poder borrarlos y
// redibujarlos cada vez que llegan datos nuevos.
let marcadoresActuales = [];

// Limpia del mapa los marcadores de autobús de la actualización anterior.
// Está en su propia función porque hace falta llamarla tanto al redibujar
// como al mostrar un mensaje (si no, los buses de la parada anterior se
// quedarían clavados en el mapa mientras el panel dice otra cosa).
function limpiarMarcadoresAutobuses() {
  marcadoresActuales.forEach((marcador) => mapa.removeLayer(marcador));
  marcadoresActuales = [];
}

// La equivalente para los trenes de Metro. Mismo motivo, y además hace
// falta al cambiar de modo: ver la nota en seleccionarParada().
function limpiarMarcadoresTrenes() {
  marcadoresTrenesActuales.forEach((marcador) => mapa.removeLayer(marcador));
  marcadoresTrenesActuales = [];
}

// Vacía el panel y deja un único mensaje explicativo. Reutiliza el estilo
// de "mensaje-vacio" que ya existía para el caso de "no hay autobuses".
function mostrarMensajeEnPanel(texto) {
  listaLlegadas.innerHTML = `<div id="mensaje-vacio">${texto}</div>`;
}

// Pinta un distintivo redondo por cada línea que pasa por la estación,
// con su número y sus colores oficiales.
//
// Se le pasa la lista de códigos de línea tal como la devuelve el backend
// en /metro/parada. Las líneas que no estén en COLORES_LINEAS_METRO se
// omiten en vez de pintarse en gris: si el diccionario no cargó, es mejor
// no enseñar nada que enseñar chips sin sentido.
function pintarChipsLineas(codLines) {
  chipsLineas.innerHTML = "";

  codLines.forEach((codLinea) => {
    const linea = COLORES_LINEAS_METRO[codLinea];
    if (!linea) {
      return;
    }

    const chip = document.createElement("span");
    chip.className = "chip-linea";
    chip.textContent = linea.numero;
    chip.title = `Línea ${linea.numero}`;
    // Inline y no por clase CSS: los colores salen del GTFS, así que no
    // queremos una regla de estilo por cada línea.
    chip.style.backgroundColor = `#${linea.color}`;
    chip.style.color = `#${linea.color_texto}`;

    chipsLineas.appendChild(chip);
  });
}

// Los chips pertenecen a la estación seleccionada, así que hay que
// vaciarlos al cambiar de parada. Si no, los de la estación anterior se
// quedarían bajo el nombre de una parada de autobús — el mismo problema
// que tenían los marcadores de vehículo al cambiar de modo.
function limpiarChipsLineas() {
  chipsLineas.innerHTML = "";
}

// Construye una tarjeta de llegada, la misma para autobuses y para trenes:
// distintivo de línea a la izquierda y, a su derecha, el destino con el
// tiempo más próximo debajo en grande.
//
//   etiqueta    lo que va dentro del distintivo ("27", "10", "R")
//   destino     hacia dónde va
//   tiempos     segundos que faltan, YA ordenados de menor a mayor
//   color       fondo del distintivo en hexadecimal sin "#", opcional:
//               si no se pasa, se queda el azul de la EMT que define el CSS
//   colorTexto  color del número, para que se lea sobre ese fondo
//   soloHorario si es cierto, esta hora sale de la tabla de horarios y no
//               de un seguimiento en vivo: se avisa con una etiqueta para
//               no dar a entender más precisión de la que hay
function crearTarjetaLlegada({
  etiqueta,
  destino,
  tiempos,
  color,
  colorTexto,
  soloHorario = false,
}) {
  const item = document.createElement("li");
  item.className = "tarjeta-bus";

  // Tiempos secundarios (todos menos el primero), unidos por coma.
  // Ej: si tiempos = [120, 540], queda "9 min" como secundario.
  const tiemposSecundarios = tiempos
    .slice(1)
    .map((s) => formatearMinutos(s))
    .join(", ");

  const estilo = color
    ? ` style="background-color:#${color}; color:#${colorTexto ?? "FFFFFF"}"`
    : "";

  // "En camino" ya se explica solo, así que en ese caso no añadimos "min".
  const unidad = Math.floor(tiempos[0] / 60) < 1 ? "" : "min";

  item.innerHTML = `
    <div class="tarjeta-linea"${estilo}>${etiqueta}</div>
    <div class="tarjeta-info">
      <div class="tarjeta-destino">${destino}</div>
      <div class="tiempo-proximo">${formatearMinutos(
        tiempos[0]
      )}<span class="unidad">${unidad}</span>${
    soloHorario ? '<span class="etiqueta-horario">horario</span>' : ""
  }</div>
      ${
        tiemposSecundarios
          ? `<div class="tarjeta-tiempos">Siguiente: ${tiemposSecundarios} min</div>`
          : ""
      }
    </div>
  `;

  return item;
}

// Verde corporativo de los autobuses interurbanos. Va aquí como constante y
// no en un diccionario como los de Metro porque las 354 líneas del GTFS del
// CRTM comparten exactamente este color, igual que las 236 de la EMT
// comparten su azul (ese vive en el CSS, como valor por defecto).
const COLOR_LINEA_INTERURBANA = { color: "8EBF42", colorTexto: "FFFFFF" };

// Pinta en el panel una lista de llegadas ya agrupadas por línea + destino,
// tal como la devuelven /metro/parada y /parada para las interurbanas.
//
//   grupos          lo que manda el backend, con horas ISO absolutas
//   mensajeVacio    qué decir si no viene ninguna
//   colorPorDefecto colores del distintivo para las líneas que no estén en
//                   COLORES_LINEAS_METRO (es decir, las interurbanas)
function pintarLlegadasAgrupadas(grupos, mensajeVacio, colorPorDefecto) {
  // El backend da la hora absoluta de llegada; aquí la convertimos en
  // segundos restantes contra el reloj del navegador y ordenamos.
  const tarjetas = grupos.map((grupo) => ({
    ...grupo,
    tiempos: grupo.tiempos.map(minutosHastaLlegada).sort((a, b) => a - b),
  }));

  tarjetas.sort((a, b) => a.tiempos[0] - b.tiempos[0]);

  listaLlegadas.innerHTML = "";

  if (tarjetas.length === 0) {
    mostrarMensajeEnPanel(mensajeVacio);
    return;
  }

  tarjetas.forEach((tarjeta) => {
    const linea = COLORES_LINEAS_METRO[tarjeta.codLine];

    listaLlegadas.appendChild(
      crearTarjetaLlegada({
        etiqueta: tarjeta.linea,
        destino: tarjeta.destino,
        tiempos: tarjeta.tiempos,
        color: linea?.color ?? colorPorDefecto?.color,
        colorTexto: linea?.color_texto ?? colorPorDefecto?.colorTexto,
        // Solo el interurbano distingue: en Metro enVivo llega como null.
        soloHorario: tarjeta.enVivo === false,
      })
    );
  });
}

// Icono que representa cada modo en la tarjeta de cabecera. Son los mismos
// PNG que ya usa el mapa, reaprovechados a mayor tamaño.
const ICONO_CABECERA_POR_FUENTE = {
  EMT: "bus-urbano.png",
  CRTM: "bus-interurbano.png",
  METRO: "metro.png",
};

// Rellena la tarjeta de identidad de la parada: icono del modo, nombre y,
// solo en autobús, el código de parada (el que está escrito en la
// marquesina y sirve para buscarla). En Metro se omite porque su id
// interno, del tipo "est_90_58", no le dice nada a nadie.
function pintarCabeceraParada(parada) {
  const archivo =
    ICONO_CABECERA_POR_FUENTE[parada.fuente] ?? ICONO_CABECERA_POR_FUENTE.EMT;

  iconoParadaActual.src = `assets/${archivo}`;
  nombreParadaActual.textContent = parada.nombre;
  codigoParadaActual.textContent =
    parada.fuente === "METRO" ? "" : `Parada ${parada.id}`;
}

async function actualizarAutobuses() {
  if (STOP_ID === null) {
    return; // todavía no se ha seleccionado ninguna parada
  }

  try {
    const respuesta = await fetch(`${URL_BACKEND}/parada/${STOP_ID}`);
    const datos = await respuesta.json();

    // Las paradas interurbanas (CRTM) vienen ya agrupadas por línea y
    // destino, con la misma forma que las de Metro. Hay que comprobarlo
    // ANTES de tocar datos.data, que solo existe en la respuesta de EMT.
    //
    // No se pintan vehículos en el mapa para el interurbano: la API sí los
    // devuelve, pero con posiciones congeladas (ver la nota de cabecera en
    // metro_client.py), así que dibujarlos sería mentir.
    if (datos.llegadas) {
      limpiarMarcadoresAutobuses();
      pintarLlegadasAgrupadas(
        datos.llegadas,
        "No hay autobuses en camino ahora mismo.",
        COLOR_LINEA_INTERURBANA
      );
      return;
    }

    // Red de seguridad heredada: si algún día el backend vuelve a declarar
    // una parada sin tiempo real, se muestra su mensaje en vez de fallar.
    if (datos.tiempo_real_disponible === false) {
      limpiarMarcadoresAutobuses();
      mostrarMensajeEnPanel(datos.mensaje);
      return;
    }

    // Red de seguridad para respuestas inesperadas de la API de EMT (por
    // ejemplo si se agota la cuota diaria o la parada no existe): sin esto
    // volveríamos a caer en el catch sin ningún mensaje para el usuario.
    const autobuses = datos?.data?.[0]?.Arrive;
    if (!autobuses) {
      limpiarMarcadoresAutobuses();
      mostrarMensajeEnPanel("No se pudieron obtener las llegadas de esta parada.");
      return;
    }

    // --- 1. Dibujamos los marcadores en el mapa (igual que antes) ---
    limpiarMarcadoresAutobuses();

    autobuses.forEach((bus) => {
      const [lon, lat] = bus.geometry.coordinates;
      if (lon === 0 && lat === 0) {
        return;
      }

      const iconoLinea = L.divIcon({
        className: "icono-bus",
        html: `<div class="circulo-bus">${bus.line}</div>`,
        iconSize: [30, 30],
      });

      const marcador = L.marker([lat, lon], {
        icon: iconoLinea,
        zIndexOffset: Z_INDEX_VEHICULOS,
      }).addTo(mapa);
      marcador.bindPopup(
        `Línea ${bus.line} → ${bus.destination}<br>Llega en ${bus.estimateArrive} segundos`
      );

      marcadoresActuales.push(marcador);
    });

    // --- 2. Agrupamos los buses por línea+destino para el panel ---
    // Clave: "27|Plaza de Castilla". Así, ida y vuelta de una misma
    // línea no se mezclan en la misma tarjeta.
    const grupos = {};
    autobuses.forEach((bus) => {
      const clave = `${bus.line}|${bus.destination}`;
      if (!grupos[clave]) {
        grupos[clave] = {
          line: bus.line,
          destination: bus.destination,
          tiempos: [],
        };
      }
      grupos[clave].tiempos.push(bus.estimateArrive);
    });

    // Convertimos el objeto "grupos" en un array para poder ordenarlo
    const tarjetas = Object.values(grupos);

    // Dentro de cada tarjeta, el tiempo más próximo va primero
    tarjetas.forEach((tarjeta) => tarjeta.tiempos.sort((a, b) => a - b));

    // Las tarjetas se ordenan por su tiempo más próximo (tiempos[0])
    tarjetas.sort((a, b) => a.tiempos[0] - b.tiempos[0]);

    // --- 3. Pintamos las tarjetas en el panel izquierdo ---
    listaLlegadas.innerHTML = "";

    if (tarjetas.length === 0) {
      mostrarMensajeEnPanel("No hay autobuses en camino ahora mismo.");
      return;
    }

    tarjetas.forEach((tarjeta) => {
      // Sin color: las 236 líneas de la EMT comparten el mismo azul, que ya
      // viene puesto por defecto en .tarjeta-linea.
      listaLlegadas.appendChild(
        crearTarjetaLlegada({
          etiqueta: tarjeta.line,
          destino: tarjeta.destination,
          tiempos: tarjeta.tiempos,
        })
      );
    });
  } catch (error) {
    console.error("Error al actualizar los autobuses:", error);
  }
}

setInterval(actualizarAutobuses, INTERVALO_REFRESCO_EMT);

// Convierte una hora ISO absoluta (ej. "2026-06-21T16:43:51+02:00") en
// minutos restantes desde ahora. A diferencia de bus (que da segundos
// restantes directamente), Metro da la hora exacta de llegada, así que
// calculamos la diferencia contra el reloj del navegador.
function minutosHastaLlegada(horaISO) {
  const ahora = new Date();
  const llegada = new Date(horaISO);
  const segundosRestantes = (llegada - ahora) / 1000;
  return Math.max(0, segundosRestantes);
}

async function actualizarTiemposMetro() {
  if (STOP_ID_METRO === null) {
    return; // todavía no se ha seleccionado ninguna estación de Metro
  }

  try {
    const respuesta = await fetch(`${URL_BACKEND}/metro/parada/${STOP_ID_METRO}`);
    const datos = await respuesta.json();

    // Igual que en las paradas de bus: si el backend no pudo resolver el
    // andén de esta estación, avisamos en vez de reventar al recorrer
    // datos.llegadas, que en ese caso no existe.
    if (!datos.llegadas) {
      mostrarMensajeEnPanel(
        datos.mensaje ?? "No se pudieron obtener los tiempos de esta estación."
      );
      return;
    }

    // Los chips salen de esta misma respuesta, que ya trae codLines
    // filtrado a líneas de Metro. Repintarlos en cada refresco es
    // inofensivo y evita tener que sincronizarlos por otro camino.
    pintarChipsLineas(datos.codLines ?? []);

    // Sin color por defecto: todas las líneas de Metro están en
    // COLORES_LINEAS_METRO, así que cada tarjeta encuentra el suyo. Si el
    // diccionario no hubiera cargado, quedaría el azul que pone el CSS.
    pintarLlegadasAgrupadas(
      datos.llegadas,
      "No hay trenes en camino ahora mismo."
    );
  } catch (error) {
    console.error("Error al actualizar los tiempos de Metro:", error);
  }
}

setInterval(actualizarTiemposMetro, INTERVALO_REFRESCO_METRO);

// Dado el texto de itinerario que devuelve la API (ej. "2-Las Rosas-
// Cuatro Caminos"), nos quedamos solo con el último tramo tras el
// último guión: el destino final hacia el que circula ese tren.
// No usamos el primer guión porque el número de línea también lleva
// uno delante; el ÚLTIMO segmento es siempre el destino, incluso si
// el propio nombre de una estación trajera un guión interno.
function destinoDesdeDescripcion(descripcion) {
  const partes = descripcion.split("-");
  return partes[partes.length - 1].trim();
}

async function actualizarTrenesMetro() {
  if (STOP_ID_METRO === null) {
    return; // todavía no se ha seleccionado ninguna estación de Metro
  }

  try {
    // Primero necesitamos saber qué líneas pasan por esta estación.
    // Ya hacemos esta llamada en actualizarTiemposMetro(), pero la
    // repetimos aquí: son funciones independientes y cada una debe
    // poder fallar o recargarse sin depender de que la otra ya corrió.
    const respuestaEstacion = await fetch(`${URL_BACKEND}/metro/parada/${STOP_ID_METRO}`);
    const datosEstacion = await respuestaEstacion.json();

    if (!datosEstacion.codLines) {
      return; // estación sin info de líneas disponible (caso raro)
    }

    // Pedimos los vehículos de TODAS las líneas de la estación a la
    // vez (Promise.all), en vez de una por una: si Gran Vía tiene 2
    // líneas, lanzamos 2 peticiones en paralelo y esperamos a ambas,
    // en lugar de esperar la primera para empezar la segunda.
    // Pasamos la estación que se está mirando (cod_stop). La API del CRTM
    // no devuelve todos los trenes de la línea, sino los más cercanos a la
    // estación por la que preguntas: sin este parámetro el backend usaba la
    // cabecera del itinerario y salían siempre los mismos trenes parados en
    // los extremos de la línea, en vez de los que se acercan a ti.
    const respuestas = await Promise.all(
      datosEstacion.codLines.map((codLinea) =>
        fetch(
          `${URL_BACKEND}/metro/linea/${codLinea}/vehiculos?cod_stop=${STOP_ID_METRO}`
        ).then((r) => r.json())
      )
    );

    // Limpiamos los trenes de la actualización anterior antes de
    // pintar los nuevos, igual que ya haces con marcadoresActuales
    // en actualizarAutobuses().
    limpiarMarcadoresTrenes();

    respuestas.forEach((datosLinea) => {
      const color = datosLinea.color ?? "0078BC"; // azul de respaldo si faltase
      const colorTexto = datosLinea.colorTexto ?? "FFFFFF";

      datosLinea.vehiculos.forEach((tren) => {
        const { latitude, longitude } = tren.coordinates;
        const numeroLinea = tren.line.shortDescription;
        const destino = destinoDesdeDescripcion(tren.line.description);

        const iconoTren = L.divIcon({
          className: "icono-bus", // misma clase "neutralizadora" que ya usas en buses (quita el fondo blanco por defecto de Leaflet)
          html: `<div class="circulo-tren" style="background-color:#${color}; color:#${colorTexto};">${numeroLinea}</div>`,
          iconSize: [28, 28],
        });

        const marcador = L.marker([latitude, longitude], {
          icon: iconoTren,
          zIndexOffset: Z_INDEX_VEHICULOS,
        }).addTo(mapa);
        marcador.bindTooltip(`Sentido ${destino}`);

        marcadoresTrenesActuales.push(marcador);
      });
    });
  } catch (error) {
    console.error("Error al actualizar los trenes de Metro:", error);
  }
}

setInterval(actualizarTrenesMetro, INTERVALO_REFRESCO_METRO);

// --- BOTÓN "MI UBICACIÓN" ---
const botonUbicacion = document.getElementById("boton-ubicacion");

// Guardamos el marcador de ubicación para poder moverlo en vez de
// crear uno nuevo cada vez que el usuario pulse el botón otra vez.
let marcadorUbicacion = null;

const iconoUbicacion = L.divIcon({
  className: "icono-ubicacion",
  html: '<div class="halo-ubicacion"><div class="punto-ubicacion"></div></div>',
  iconSize: [36, 36],
  iconAnchor: [18, 18], // centrado, a diferencia de los buses (que anclan por la base)
});

botonUbicacion.addEventListener("click", () => {
  // geolocation puede no existir en navegadores muy antiguos o en
  // contextos no seguros (http:// que no sea localhost).
  if (!navigator.geolocation) {
    alert("Tu navegador no admite geolocalización.");
    return;
  }

  navigator.geolocation.getCurrentPosition(
    // Éxito: el navegador nos da la posición
    (posicion) => {
      const lat = posicion.coords.latitude;
      const lon = posicion.coords.longitude;

      if (marcadorUbicacion) {
        marcadorUbicacion.setLatLng([lat, lon]);
      } else {
        marcadorUbicacion = L.marker([lat, lon], {
          icon: iconoUbicacion,
          zIndexOffset: 1000, // por encima de las paradas, para que no quede tapado
        }).addTo(mapa);
      }

      mapa.setView([lat, lon], 16);
    },
    // Error: permiso denegado, GPS no disponible, timeout, etc.
    (error) => {
      console.error("Error de geolocalización:", error);
      alert("No se pudo obtener tu ubicación. Revisa los permisos del navegador.");
    }
  );
});