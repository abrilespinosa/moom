// Dónde está el backend, que no es el mismo sitio en local y en producción.
//
// En Vercel los dos comparten dominio (el backend cuelga de /api, ver
// vercel.json), así que basta una ruta relativa: además de ahorrar la
// configuración de CORS, el frontend deja de tener escrito un dominio
// concreto y el mismo archivo sirve para cualquier despliegue.
//
// En local no vale, porque el flujo de desarrollo son dos servidores en
// puertos distintos: el frontend en el 5500 y uvicorn en el 8000. Una ruta
// relativa apuntaría al 5500, donde no hay backend. De ahí la distinción.
const EN_DESARROLLO_LOCAL = location.port === "5500";

const URL_BACKEND = EN_DESARROLLO_LOCAL ? "http://127.0.0.1:8000" : "/api";

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

// Las mismas paradas indexadas por id. El recorrido de una línea llega
// como lista de ids, y para seleccionar una hace falta su objeto completo
// (coordenadas y marcador), así que sin este índice habría que recorrer
// las 13.542 paradas en cada clic.
let PARADAS_POR_ID = new Map();

// Número y colores oficiales de cada línea de Metro, indexados por su
// código ("4__2___"). Son 13 líneas y no cambian nunca, así que se piden
// UNA sola vez al arrancar en vez de por cada estación que se selecciona.
let COLORES_LINEAS_METRO = {};

// Todas las líneas de las tres redes, sin su recorrido: número, nombre,
// fuente y color. Se piden una vez al arrancar para poder filtrarlas
// mientras se escribe, igual que se hace con las paradas. El recorrido de
// cada una se pide aparte, solo al elegirla.
let TODAS_LAS_LINEAS = [];

// Las mismas líneas indexadas por id ("EMT-027"). Los favoritos se guardan
// como ids, así que al pintarlos hay que recuperar cada línea entera.
let LINEAS_POR_ID = new Map();

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
  let paradas;

  // La única petición sin la que la aplicación no es nada: si falla, el
  // mapa se queda sin un solo marcador. Antes ni siquiera se capturaba, así
  // que con el backend apagado quedaba un mapa vacío y perfectamente
  // silencioso, indistinguible de una zona sin paradas.
  try {
    paradas = await pedirJson(`${URL_BACKEND}/paradas`);
  } catch (error) {
    console.error("No se pudieron cargar las paradas:", error);
    mostrarAvisoConexion(
      "No se ha podido conectar con el servidor, así que el mapa está vacío. Comprueba que el backend está arrancado y recarga la página."
    );
    return;
  }

  TODAS_LAS_PARADAS = paradas;
  PARADAS_POR_ID = new Map(paradas.map((parada) => [parada.id, parada]));

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
    // sin tener que buscar en el array de 13.542 paradas cada vez.
    marcador.parada = parada;

    marcadoresParadas.push(marcador);
  });

  // Una vez creados todos los círculos, decidimos cuáles mostrar
  // según el zoom con el que arrancó el mapa.
  actualizarVisibilidadParadas();

  // Igual que con las líneas: las paradas favoritas se guardan por id y no
  // se pueden pintar hasta tener aquí la lista completa.
  actualizarResultadosBusqueda();
}

// Añade o quita los marcadores de parada del mapa según el zoom Y el
// área visible actual. Antes solo filtrábamos por zoom: al cruzar
// ZOOM_MINIMO_PARADAS, las ~13.542 paradas se recorrían igual, pero
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
    COLORES_LINEAS_METRO = await pedirJson(`${URL_BACKEND}/metro/lineas/colores`);
  } catch (error) {
    console.error("No se pudieron cargar los colores de las líneas:", error);
  }
}

cargarColoresLineasMetro();

// Las líneas también se cargan una vez al arrancar. Si la petición falla o
// el backend no tiene los GTFS pesados, la lista queda vacía y el buscador
// simplemente no ofrece líneas; buscar paradas sigue funcionando.
async function cargarLineas() {
  try {
    TODAS_LAS_LINEAS = await pedirJson(`${URL_BACKEND}/lineas`);
    LINEAS_POR_ID = new Map(TODAS_LAS_LINEAS.map((linea) => [linea.id, linea]));

    // Las líneas favoritas no se pueden pintar hasta que llega esta lista,
    // así que repintamos el buscador ahora que ya la tenemos.
    actualizarResultadosBusqueda();
  } catch (error) {
    console.error("No se pudieron cargar las líneas:", error);
  }
}

cargarLineas();

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
const botonFavoritoParada = document.getElementById("boton-favorito-parada");
const botonFavoritoLinea = document.getElementById("boton-favorito-linea");
const vistaLinea = document.getElementById("vista-linea");
const botonVolverLinea = document.getElementById("boton-volver-linea");
const distintivoLinea = document.getElementById("distintivo-linea");
const nombreLinea = document.getElementById("nombre-linea");
const fuenteLinea = document.getElementById("fuente-linea");
const sentidosLinea = document.getElementById("sentidos-linea");
const tituloRecorrido = document.getElementById("titulo-recorrido");
const listaRecorrido = document.getElementById("lista-recorrido");
const subtituloHeader = document.getElementById("subtitulo-header");
const avisoConexion = document.getElementById("aviso-conexion");
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

    // Los resultados del buscador también dependen del modo activo, así
    // que hay que rehacerlos: si estabas viendo líneas de EMT y cambias a
    // Metro, las de EMT deben desaparecer de la lista.
    actualizarResultadosBusqueda();
  });
});

// --- FAVORITOS ---
//
// Se guardan en localStorage, no en el backend: no hay usuarios ni base de
// datos, así que son los favoritos de ESTE navegador y no viajan a otro
// dispositivo. Cuando exista la persistencia en PostgreSQL del roadmap,
// este módulo es lo único que habría que cambiar: el resto de la interfaz
// solo llama a esFavorito() y alternarFavorito().
//
// Guardamos únicamente ids ("EMT-027", "est_4_323"), nunca el objeto
// entero: nombres y coordenadas cambian con cada volcado GTFS, mientras
// que el id es lo único estable entre volcados.
const CLAVE_FAVORITOS = "moom:favoritos";

// Dos conjuntos separados porque los ids de línea y de parada son de
// espacios distintos y se pintan de forma distinta.
let FAVORITOS = { paradas: new Set(), lineas: new Set() };

function cargarFavoritos() {
  try {
    const guardado = JSON.parse(localStorage.getItem(CLAVE_FAVORITOS)) ?? {};
    FAVORITOS = {
      paradas: new Set(guardado.paradas ?? []),
      lineas: new Set(guardado.lineas ?? []),
    };
  } catch (error) {
    // JSON corrupto, o localStorage no disponible (navegación privada de
    // Safari, cookies bloqueadas). Los favoritos se quedan solo en memoria
    // durante esta sesión, que es mejor que impedir que arranque el resto.
    console.error("No se pudieron leer los favoritos guardados:", error);
  }
}

function guardarFavoritos() {
  try {
    localStorage.setItem(
      CLAVE_FAVORITOS,
      JSON.stringify({
        paradas: [...FAVORITOS.paradas],
        lineas: [...FAVORITOS.lineas],
      })
    );
  } catch (error) {
    console.error("No se pudieron guardar los favoritos:", error);
  }
}

cargarFavoritos();

// "tipo" es "paradas" o "lineas", el mismo nombre que la clave de FAVORITOS.
function esFavorito(tipo, id) {
  return FAVORITOS[tipo].has(id);
}

function alternarFavorito(tipo, id) {
  const guardados = FAVORITOS[tipo];

  if (guardados.has(id)) {
    guardados.delete(id);
  } else {
    guardados.add(id);
  }

  guardarFavoritos();
  return guardados.has(id);
}

// La estrella va en SVG y no como carácter (★/☆) para que herede el color
// del CSS y pueda pasar de contorno a relleno con una clase, sin cambiar el
// texto del botón.
const ESTRELLA_SVG = `
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 3.6l2.6 5.28 5.83.85-4.22 4.11.997 5.8L12 16.9l-5.21 2.74.996-5.8-4.22-4.11 5.83-.85z" />
  </svg>
`;

function pintarEstadoFavorito(boton, guardado) {
  const etiqueta = guardado ? "Quitar de favoritos" : "Guardar en favoritos";

  boton.classList.toggle("activo", guardado);
  boton.setAttribute("aria-pressed", guardado ? "true" : "false");
  // El botón no tiene texto, solo el dibujo de la estrella, así que sin
  // aria-label un lector de pantalla lo anunciaría como "botón" a secas.
  boton.setAttribute("aria-label", etiqueta);
  boton.title = etiqueta;
}

// Deja un botón listo para alternar el favorito de un elemento concreto.
//
// Se asigna "onclick" en vez de addEventListener a propósito: los dos
// botones de cabecera son los MISMOS elementos para todas las paradas y
// líneas, así que se preparan de nuevo en cada selección. Con
// addEventListener se irían acumulando manejadores de las paradas
// anteriores y un solo clic guardaría varias a la vez.
function prepararBotonFavorito(boton, tipo, id) {
  boton.innerHTML = ESTRELLA_SVG;
  pintarEstadoFavorito(boton, esFavorito(tipo, id));

  boton.onclick = (evento) => {
    // En una fila del buscador, el clic en la estrella no debe abrir además
    // la parada o la línea.
    evento.stopPropagation();

    pintarEstadoFavorito(boton, alternarFavorito(tipo, id));

    // Si lo que se acaba de tocar es una fila de la lista de favoritos, esa
    // fila ya no pertenece ahí: repintamos para que desaparezca.
    if (vistaBusqueda.style.display !== "none") {
      actualizarResultadosBusqueda();
    }
  };

  return boton;
}

function crearBotonFavorito(tipo, id) {
  const boton = document.createElement("button");
  boton.className = "boton-favorito";
  return prepararBotonFavorito(boton, tipo, id);
}

// --- Lógica del buscador ---
//
// Un único cuadro busca a la vez líneas y paradas, y ambos respetan el
// filtro de modo activo. Las líneas van primero porque son muchas menos y
// la búsqueda por número suele ser más precisa: quien escribe "27" casi
// siempre quiere la línea 27, no las paradas cuyo código lleva un 27.

const MAXIMO_LINEAS = 8;
const MAXIMO_PARADAS = 12;

function pasaElFiltroDeModo(elemento) {
  return filtroActivo === "todos" || elemento.fuente === filtroActivo;
}

function buscarLineas(texto) {
  const coincidencias = TODAS_LAS_LINEAS.filter(
    (linea) =>
      pasaElFiltroDeModo(linea) &&
      (linea.numero.toLowerCase().startsWith(texto) ||
        linea.nombre.toLowerCase().includes(texto))
  );

  // El número exacto primero: buscando "27" interesa más la línea 27 que
  // la 270, aunque las dos empiecen igual.
  coincidencias.sort((a, b) => {
    const exactaA = a.numero.toLowerCase() === texto ? 0 : 1;
    const exactaB = b.numero.toLowerCase() === texto ? 0 : 1;
    return exactaA - exactaB || a.numero.localeCompare(b.numero, "es", { numeric: true });
  });

  return coincidencias.slice(0, MAXIMO_LINEAS);
}

function buscarParadas(texto) {
  return TODAS_LAS_PARADAS.filter(
    (parada) =>
      pasaElFiltroDeModo(parada) &&
      (parada.nombre.toLowerCase().includes(texto) || parada.id.includes(texto))
  ).slice(0, MAXIMO_PARADAS);
}

function encabezadoDeGrupo(texto) {
  const item = document.createElement("li");
  item.className = "grupo-resultados";
  item.textContent = texto;
  return item;
}

// Nombre legible de cada red, para distinguir en los resultados una línea
// de otra con el mismo número: la 1 existe en EMT y en Metro a la vez.
const NOMBRE_DE_FUENTE = {
  EMT: "Bus urbano",
  CRTM: "Bus interurbano",
  METRO: "Metro",
};

function crearResultadoDeLinea(linea) {
  const item = document.createElement("li");
  item.className = "resultado-linea";

  const estilo = linea.color
    ? ` style="background-color:#${linea.color}; color:#${linea.colorTexto ?? "FFFFFF"}"`
    : "";

  item.innerHTML = `
    <span class="tarjeta-linea"${estilo}>${linea.numero}</span>
    <span class="texto">
      <span class="titulo">${linea.nombre}</span>
      <span class="subtitulo">${NOMBRE_DE_FUENTE[linea.fuente] ?? linea.fuente}</span>
    </span>
  `;

  // La estrella va en cada resultado, no solo en la lista de favoritos: así
  // se puede guardar una línea nada más encontrarla, sin tener que abrirla.
  item.appendChild(crearBotonFavorito("lineas", linea.id));

  item.addEventListener("click", () => seleccionarLinea(linea));
  return item;
}

// El código que se enseña de una parada: el que está escrito en la
// marquesina, no el id interno del GTFS.
//
// Las paradas de la EMT ya vienen con su número pelado ("72"), pero las
// del CRTM llevan el prefijo del volcado ("par_8_09568") y las estaciones
// de Metro otro parecido ("est_4_323"). Ese prefijo indica el modo de
// transporte y le sirve al backend para saber a qué API preguntar, pero
// para quien mira la pantalla es ruido: en la parada pone 09568.
function codigoDeParada(parada) {
  return parada.id.replace(/^[a-z]+_\d+_/, "");
}

function crearResultadoDeParada(parada) {
  const item = document.createElement("li");

  // El nombre va dentro de un span y no suelto como texto para que pueda
  // truncar con puntos suspensivos cuando no cabe junto a la estrella.
  const texto = document.createElement("span");
  texto.className = "texto";
  texto.textContent = `${parada.nombre} (parada ${codigoDeParada(parada)})`;
  item.appendChild(texto);
  item.appendChild(crearBotonFavorito("paradas", parada.id));

  item.addEventListener("click", () => seleccionarParada(parada));
  return item;
}

// Con el buscador vacío, el panel enseña lo que hay guardado en vez de
// quedarse en blanco. Respeta el filtro de modo activo, igual que los
// resultados de búsqueda: si estás en "Metro", no aparecen tus paradas de
// bus favoritas.
//
// Los ids guardados que ya no existen (un volcado GTFS que renumera una
// parada, o las líneas cuando el backend no tiene los GTFS pesados) se
// omiten al pintar, pero NO se borran de localStorage: pueden volver a
// existir con el siguiente volcado.
function pintarFavoritos() {
  const lineas = [...FAVORITOS.lineas]
    .map((id) => LINEAS_POR_ID.get(id))
    .filter((linea) => linea && pasaElFiltroDeModo(linea));

  const paradas = [...FAVORITOS.paradas]
    .map((id) => PARADAS_POR_ID.get(id))
    .filter((parada) => parada && pasaElFiltroDeModo(parada));

  if (lineas.length === 0 && paradas.length === 0) {
    const pista = document.createElement("li");
    pista.className = "pista-favoritos";
    pista.textContent =
      "Aquí aparecerán tus paradas y líneas favoritas. Guárdalas con la estrella.";
    listaResultados.appendChild(pista);
    return;
  }

  listaResultados.appendChild(encabezadoDeGrupo("Favoritos"));
  lineas.forEach((l) => listaResultados.appendChild(crearResultadoDeLinea(l)));
  paradas.forEach((p) => listaResultados.appendChild(crearResultadoDeParada(p)));
}

function actualizarResultadosBusqueda() {
  const texto = inputBuscar.value.toLowerCase().trim();
  listaResultados.innerHTML = "";

  if (texto === "") {
    pintarFavoritos();
    return;
  }

  const lineas = buscarLineas(texto);
  const paradas = buscarParadas(texto);

  if (lineas.length === 0 && paradas.length === 0) {
    listaResultados.appendChild(encabezadoDeGrupo("Sin resultados"));
    return;
  }

  if (lineas.length > 0) {
    listaResultados.appendChild(encabezadoDeGrupo("Líneas"));
    lineas.forEach((l) => listaResultados.appendChild(crearResultadoDeLinea(l)));
  }

  if (paradas.length > 0) {
    listaResultados.appendChild(encabezadoDeGrupo("Paradas"));
    paradas.forEach((p) => listaResultados.appendChild(crearResultadoDeParada(p)));
  }
}

inputBuscar.addEventListener("input", actualizarResultadosBusqueda);

// El panel tiene tres pantallas y solo una visible a la vez: el buscador,
// el recorrido de una línea y las llegadas de una parada.
function mostrarVista(nombre) {
  vistaBusqueda.style.display = nombre === "busqueda" ? "block" : "none";
  vistaLinea.style.display = nombre === "linea" ? "flex" : "none";
  vistaLlegadas.style.display = nombre === "llegadas" ? "flex" : "none";
}

// Desde dónde se llegó al panel de llegadas. Sirve para que "Volver"
// regrese al recorrido de la línea cuando se entró por ahí, en vez de
// mandar siempre al buscador y obligar a buscar la línea otra vez.
let vistaDeOrigen = "busqueda";

// Se llama al hacer clic en el mapa, al elegir un resultado de búsqueda y
// al pulsar una parada del recorrido de una línea. Centraliza el cambio de
// vista para no repetir código.
function seleccionarParada(parada, origen = "busqueda") {
  vistaDeOrigen = origen;
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

  mostrarVista("llegadas");
  subtituloHeader.textContent = "Próximas llegadas";

  pintarCabeceraParada(parada);

  // "Tiempos reales" es el nombre que usa la app oficial para el panel de
  // Metro; en autobús encaja mejor hablar de llegadas.
  tituloSeccion.textContent =
    parada.fuente === "METRO" ? "Tiempos reales" : "Próximas llegadas";

  // Aviso de que se está pidiendo, antes de lanzar la petición.
  //
  // La API del CRTM tarda entre medio segundo y cinco en devolver los
  // tiempos de espera (medido), y hasta ahora el panel se quedaba vacío
  // todo ese rato, que es exactamente lo que parece una aplicación rota.
  // Esto solo se pinta al SELECCIONAR: los refrescos posteriores ya tienen
  // tarjetas en pantalla y sustituirlas por un mensaje sería un parpadeo.
  mostrarMensajeEnPanel(
    parada.fuente === "METRO"
      ? "Buscando próximos trenes…"
      : "Buscando próximas llegadas…"
  );

  // Limpiamos el buscador para la próxima vez que se use. Repintar la lista
  // en vez de vaciarla deja los favoritos ya puestos para cuando se vuelva.
  inputBuscar.value = "";
  actualizarResultadosBusqueda();

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

// Botón para salir del panel de llegadas. Vuelve al recorrido de la línea
// si se entró desde ahí, y al buscador en cualquier otro caso.
botonVolver.addEventListener("click", () => {
  STOP_ID = null;
  STOP_ID_METRO = null;
  mostrarVista(vistaDeOrigen);
  subtituloHeader.textContent =
    vistaDeOrigen === "linea"
      ? "Recorrido de la línea"
      : "Busca una parada o una línea";

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

// --- VISTA DE LÍNEA ---

// Línea que se está mirando, con sus sentidos y paradas, tal como la
// devuelve /linea/{id}.
let lineaActual = null;

botonVolverLinea.addEventListener("click", () => {
  lineaActual = null;
  mostrarVista("busqueda");
  subtituloHeader.textContent = "Busca una parada o una línea";
});

// Pinta la lista ordenada de paradas de uno de los sentidos, y marca su
// botón como activo.
function pintarSentido(indice) {
  const sentido = lineaActual.sentidos[indice];

  [...sentidosLinea.children].forEach((boton, i) =>
    boton.classList.toggle("activo", i === indice)
  );

  tituloRecorrido.textContent = `${sentido.paradas.length} paradas`;
  listaRecorrido.innerHTML = "";

  sentido.paradas.forEach((paradaDeLaLinea, posicion) => {
    const item = document.createElement("li");
    item.className = "parada-recorrido";
    item.innerHTML = `
      <span class="orden">${posicion + 1}</span>
      <span class="nombre">${paradaDeLaLinea.nombre}</span>
    `;

    // El recorrido solo trae id y nombre. Para seleccionar la parada hace
    // falta el objeto completo que ya tenemos cargado, porque lleva las
    // coordenadas y la referencia a su marcador en el mapa.
    const parada = PARADAS_POR_ID.get(paradaDeLaLinea.id);

    if (parada) {
      item.addEventListener("click", () => seleccionarParada(parada, "linea"));
    } else {
      // Puede pasar si el volcado de líneas y el de paradas no van a la
      // par. Se muestra igual para no romper el orden del recorrido, pero
      // sin poder abrirla.
      item.style.cursor = "default";
      item.style.opacity = "0.5";
      item.title = "Esta parada no está en el mapa";
    }

    listaRecorrido.appendChild(item);
  });
}

async function seleccionarLinea(linea) {
  try {
    const datos = await pedirJson(
      `${URL_BACKEND}/linea/${encodeURIComponent(linea.id)}`
    );

    if (!datos.encontrada) {
      console.error("Línea no encontrada:", linea.id);
      return;
    }

    lineaActual = datos;

    const estilo = datos.color
      ? `background-color:#${datos.color}; color:#${datos.colorTexto ?? "FFFFFF"}`
      : "";
    distintivoLinea.setAttribute("style", estilo);
    distintivoLinea.textContent = datos.numero;
    nombreLinea.textContent = datos.nombre;
    fuenteLinea.textContent = NOMBRE_DE_FUENTE[datos.fuente] ?? datos.fuente;

    // El id del recorrido y el de la lista del buscador son el mismo, así
    // que la estrella queda sincronizada entre las dos vistas.
    prepararBotonFavorito(botonFavoritoLinea, "lineas", datos.id);

    // Un botón por sentido. Casi siempre son dos, pero alguna línea trae
    // más de un itinerario, así que se generan sobre la marcha.
    sentidosLinea.innerHTML = "";
    datos.sentidos.forEach((sentido, i) => {
      const boton = document.createElement("button");
      boton.className = "boton-sentido";
      boton.textContent = sentido.destino || `Sentido ${i + 1}`;
      boton.title = sentido.destino;
      boton.addEventListener("click", () => pintarSentido(i));
      sentidosLinea.appendChild(boton);
    });

    // 21 líneas reales (la F, la G, la Línea 3 de Metro…) no aparecen en el
    // trips.txt que publican EMT y CRTM, así que llegan aquí sin recorrido.
    // Se abren igual, con su nombre y su color, y lo que falta se explica en
    // vez de dejar una lista vacía sin motivo aparente.
    if (datos.sentidos.length === 0) {
      tituloRecorrido.textContent = "Recorrido no disponible";
      listaRecorrido.innerHTML = `
        <li class="recorrido-no-disponible">
          Los datos abiertos de esta línea no incluyen su lista de paradas.
          Sus paradas sí están en el mapa y sus tiempos de llegada funcionan
          con normalidad.
        </li>
      `;
    } else {
      pintarSentido(0);
    }

    mostrarVista("linea");
    subtituloHeader.textContent = "Recorrido de la línea";

    inputBuscar.value = "";
    actualizarResultadosBusqueda();
  } catch (error) {
    console.error("Error al cargar el recorrido de la línea:", error);
    // Aquí no hay dato viejo que conservar: se pulsó una línea y no se abrió
    // nada, así que sin aviso el clic parecería no haber funcionado.
    mostrarAvisoConexion("No se ha podido cargar el recorrido de esta línea.");
  }
}

// Hora del reloj en formato 24h ("14:05").
//
// Se compone a mano en vez de usar toLocaleTimeString para no depender del
// idioma del navegador: en una configuración anglosajona saldría "2:05 PM",
// que no es lo que espera nadie mirando horarios de Madrid.
function horaDelReloj(fecha) {
  const horas = String(fecha.getHours()).padStart(2, "0");
  const minutos = String(fecha.getMinutes()).padStart(2, "0");
  return `${horas}:${minutos}`;
}

// Convierte los segundos que faltan en un texto legible, devuelto en dos
// piezas para que la tarjeta pueda pintar el número grande y la unidad
// pequeña, como en la app oficial.
//
//   menos de 1 min   ->  { valor: "En camino", unidad: ""    }
//   menos de 1 hora  ->  { valor: "7",         unidad: "min" }
//   1 hora o más     ->  { valor: "14:05",     unidad: ""    }
//
// A partir de la hora se deja de contar hacia atrás y se da la hora de
// paso. Una cuenta atrás sirve para decidir si te da tiempo a llegar a la
// parada; a partir de cierta distancia lo que se quiere saber es a qué hora
// hay que estar allí. En interurbano se publican llegadas con muchísima
// antelación — se han visto de más de diez horas, que son los primeros
// autobuses del día siguiente — y ahí "10 h 52 min" no le dice nada a nadie.
function formatearEspera(segundos) {
  const minutos = Math.floor(segundos / 60);

  if (minutos < 1) {
    return { valor: "En camino", unidad: "" };
  }

  if (minutos < 60) {
    return { valor: `${minutos}`, unidad: "min" };
  }

  // Reconstruimos la hora de llegada sumando la espera al reloj actual.
  // Metro e interurbano traen la hora absoluta del backend, pero la de EMT
  // llega solo como segundos restantes, así que este camino es el único que
  // vale para las tres fuentes.
  return {
    valor: horaDelReloj(new Date(Date.now() + segundos * 1000)),
    unidad: "",
  };
}

// La misma espera pero en una sola cadena, para los tiempos secundarios,
// que van todos seguidos en texto pequeño y no se separan por tamaño.
function textoEspera(segundos) {
  const { valor, unidad } = formatearEspera(segundos);
  return unidad ? `${valor} ${unidad}` : valor;
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

// Los tres pollers y las cargas iniciales fallaban en silencio: su catch
// solo escribía en la consola, así que ante un backend caído o sin red el
// panel se quedaba enseñando los últimos tiempos indefinidamente, sin
// distinguirse de unos datos frescos. Estas dos funciones son el aviso.
//
// No borramos lo que ya hay en pantalla: unos tiempos de hace treinta
// segundos siguen siendo más útiles que un panel vacío, siempre que quede
// claro que son viejos.
function mostrarAvisoConexion(texto) {
  avisoConexion.textContent = texto;
  avisoConexion.hidden = false;
}

// Un único aviso compartido por todos los pollers. Cuando falla la red
// suele fallar todo a la vez, así que la simplificación se sostiene; el
// caso raro es que actualizarTiemposMetro y actualizarTrenesMetro discrepen
// en el mismo ciclo, y entonces el aviso parpadea un momento. Preferible a
// llevar la cuenta de qué poller está fallando.
function ocultarAvisoConexion() {
  avisoConexion.hidden = true;
}

// fetch NO lanza excepción ante un 4xx o 5xx: solo falla si la petición no
// llega a completarse. Sin esta comprobación, el 503 del backend seguía su
// camino y reventaba más adelante al leer campos que no existen, o peor,
// se colaba como una respuesta vacía legítima ("no hay trenes ahora
// mismo"), que es justo lo contrario de lo que ha pasado.
async function pedirJson(url) {
  const respuesta = await fetch(url);

  if (!respuesta.ok) {
    throw new Error(`${respuesta.status} al pedir ${url}`);
  }

  return respuesta.json();
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
    .map((s) => textoEspera(s))
    .join(", ");

  const estilo = color
    ? ` style="background-color:#${color}; color:#${colorTexto ?? "FFFFFF"}"`
    : "";

  // El número va grande y la unidad pequeña. En "En camino" la unidad sale
  // vacía, porque el texto ya se explica solo.
  const { valor, unidad } = formatearEspera(tiempos[0]);

  item.innerHTML = `
    <div class="tarjeta-linea"${estilo}>${etiqueta}</div>
    <div class="tarjeta-info">
      <div class="tarjeta-destino">${destino}</div>
      <div class="tiempo-proximo">${valor}<span class="unidad">${unidad}</span>${
    soloHorario ? '<span class="etiqueta-horario">horario</span>' : ""
  }</div>
      ${
        tiemposSecundarios
          ? `<div class="tarjeta-tiempos">Siguiente: ${tiemposSecundarios}</div>`
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
    parada.fuente === "METRO" ? "" : `Parada ${codigoDeParada(parada)}`;

  prepararBotonFavorito(botonFavoritoParada, "paradas", parada.id);
}

async function actualizarAutobuses() {
  if (STOP_ID === null) {
    return; // todavía no se ha seleccionado ninguna parada
  }

  try {
    const datos = await pedirJson(`${URL_BACKEND}/parada/${STOP_ID}`);
    ocultarAvisoConexion();

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
    mostrarAvisoConexion(
      "No se han podido actualizar las llegadas. Los tiempos que ves pueden estar desfasados."
    );
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
    const datos = await pedirJson(
      `${URL_BACKEND}/metro/parada/${STOP_ID_METRO}`
    );
    ocultarAvisoConexion();

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
    mostrarAvisoConexion(
      "No se han podido actualizar los tiempos. Los que ves pueden estar desfasados."
    );
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
    // Primero necesitamos saber qué líneas pasan por esta estación. Esta
    // llamada se mantiene aparte de la del panel a propósito: son funciones
    // independientes y cada una debe poder fallar o recargarse sin depender
    // de que la otra ya corrió.
    //
    // Pero pide la variante "/lineas", que solo hace la llamada barata al
    // CRTM. Antes pedía /metro/parada entero y se quedaba esperando a unos
    // tiempos de espera que aquí no se usan y que el panel ya está pidiendo
    // en paralelo: los trenes tardaban en salir entre medio segundo y cinco
    // de más, según lo que tardase el CRTM ese día.
    const datosEstacion = await pedirJson(
      `${URL_BACKEND}/metro/parada/${STOP_ID_METRO}/lineas`
    );

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
        pedirJson(
          `${URL_BACKEND}/metro/linea/${codLinea}/vehiculos?cod_stop=${STOP_ID_METRO}`
        )
      )
    );

    ocultarAvisoConexion();

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
    // Los trenes del mapa se quedan donde estaban. Es el mismo criterio que
    // con los tiempos: una posición de hace un minuto informa más que un
    // mapa vacío, mientras el aviso deje claro que no está al día.
    mostrarAvisoConexion(
      "No se ha podido actualizar la posición de los trenes."
    );
  }
}

setInterval(actualizarTrenesMetro, INTERVALO_REFRESCO_METRO);

// --- ANCHO DEL PANEL ---
//
// El panel y el mapa son dos columnas de un grid cuya primera medida es la
// variable CSS --ancho-panel. Arrastrar el divisor solo cambia esa
// variable: el navegador recoloca las dos columnas y no hay que tocar
// tamaños a mano en ningún sitio.
const divisor = document.getElementById("divisor");
const panel = document.getElementById("panel");

const ANCHO_PANEL_POR_DEFECTO = 380;
const ANCHO_PANEL_MINIMO = 300; // por debajo, los filtros no caben en una fila
const ANCHO_MAPA_MINIMO = 320; // que el mapa nunca quede reducido a nada
const CLAVE_ANCHO_PANEL = "moom:ancho-panel";

let anchoPanel = ANCHO_PANEL_POR_DEFECTO;

function aplicarAnchoPanel(ancho) {
  // El máximo depende del tamaño de la ventana, así que se recalcula cada
  // vez en vez de guardarse: al reducir la ventana, un panel que antes
  // cabía puede dejar de caber.
  const maximo = Math.max(
    ANCHO_PANEL_MINIMO,
    window.innerWidth - ANCHO_MAPA_MINIMO
  );

  anchoPanel = Math.min(Math.max(Math.round(ancho), ANCHO_PANEL_MINIMO), maximo);
  document.body.style.setProperty("--ancho-panel", `${anchoPanel}px`);

  // Leaflet mide el contenedor una sola vez y guarda ese tamaño. Si el mapa
  // cambia de ancho sin que cambie la ventana —justo lo que pasa aquí— no
  // se entera y deja franjas grises sin tiles hasta el siguiente zoom.
  mapa.invalidateSize();
}

function guardarAnchoPanel() {
  try {
    localStorage.setItem(CLAVE_ANCHO_PANEL, String(anchoPanel));
  } catch (error) {
    console.error("No se pudo guardar el ancho del panel:", error);
  }
}

try {
  const guardado = Number(localStorage.getItem(CLAVE_ANCHO_PANEL));
  aplicarAnchoPanel(guardado > 0 ? guardado : ANCHO_PANEL_POR_DEFECTO);
} catch (error) {
  console.error("No se pudo leer el ancho del panel:", error);
}

// setPointerCapture hace que el divisor siga recibiendo los eventos aunque
// el puntero se salga de él, que es lo normal al arrastrar rápido. Sin eso
// habría que escuchar en document y acordarse de dejar de hacerlo.
divisor.addEventListener("pointerdown", (evento) => {
  evento.preventDefault(); // no seleccionar texto del panel al arrastrar
  divisor.setPointerCapture(evento.pointerId);
  divisor.classList.add("arrastrando");
});

divisor.addEventListener("pointermove", (evento) => {
  if (!divisor.hasPointerCapture(evento.pointerId)) {
    return;
  }
  // El ancho es la distancia entre el borde izquierdo del panel y el
  // puntero, no clientX a secas: el body tiene margen alrededor.
  aplicarAnchoPanel(evento.clientX - panel.getBoundingClientRect().left);
});

divisor.addEventListener("pointerup", (evento) => {
  divisor.releasePointerCapture(evento.pointerId);
  divisor.classList.remove("arrastrando");
  guardarAnchoPanel();
});

// Con el divisor enfocado, las flechas lo mueven de 16 en 16 píxeles.
divisor.addEventListener("keydown", (evento) => {
  const paso = { ArrowLeft: -16, ArrowRight: 16 }[evento.key];
  if (paso === undefined) {
    return;
  }
  evento.preventDefault();
  aplicarAnchoPanel(anchoPanel + paso);
  guardarAnchoPanel();
});

divisor.addEventListener("dblclick", () => {
  aplicarAnchoPanel(ANCHO_PANEL_POR_DEFECTO);
  guardarAnchoPanel();
});

// Al cambiar el tamaño de la ventana hay que volver a acotar: el panel
// guardado puede ser más ancho de lo que cabe ahora.
window.addEventListener("resize", () => aplicarAnchoPanel(anchoPanel));

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

// --- HOJA INFERIOR (SOLO MÓVIL) ---
//
// En pantalla estrecha el panel deja de ser una columna y pasa a ser una
// hoja que sube desde abajo. La geometría (cuánto mide y cuánto asoma
// recogida) vive en el CSS, en --hoja-alto y --hoja-recogida; aquí solo se
// lee, para no tener los mismos números escritos en dos sitios.
//
// Solo hay dos posiciones de reposo, recogida y desplegada. Se descartaron
// los puntos intermedios: obligan a recordar en qué posición se dejó la
// hoja y no aportan nada, porque el contenido ya se desplaza por dentro.
const consultaMovil = window.matchMedia("(max-width: 768px)");
const cabeceraPanel = document.getElementById("panel-header");

let hojaDesplegada = false;
let arrastreHoja = null;

function alturaRecogidaEnPixeles() {
  const valor = getComputedStyle(document.body)
    .getPropertyValue("--hoja-recogida")
    .trim();

  const numero = parseFloat(valor);

  // La declaración está en vh para que se adapte a cada teléfono, así que
  // hay que convertirla; se acepta px por si algún día se cambia.
  return valor.endsWith("vh") ? (numero / 100) * window.innerHeight : numero;
}

// Cuánto hay que bajar la hoja para dejarla recogida: su alto total menos
// lo que debe seguir asomando.
function topeRecogido() {
  return Math.max(0, panel.offsetHeight - alturaRecogidaEnPixeles());
}

function colocarHoja(desplazamiento) {
  document.body.style.setProperty("--hoja-y", `${desplazamiento}px`);
}

function fijarEstadoHoja(desplegada) {
  hojaDesplegada = desplegada;
  colocarHoja(desplegada ? 0 : topeRecogido());
}

cabeceraPanel.addEventListener("pointerdown", (evento) => {
  if (!consultaMovil.matches) {
    return; // en escritorio la cabecera no es un tirador
  }

  arrastreHoja = {
    yInicial: evento.clientY,
    desplazamientoInicial: hojaDesplegada ? 0 : topeRecogido(),
  };

  cabeceraPanel.setPointerCapture(evento.pointerId);
  panel.classList.add("arrastrando");
});

cabeceraPanel.addEventListener("pointermove", (evento) => {
  if (!arrastreHoja) {
    return;
  }

  const recorrido = evento.clientY - arrastreHoja.yInicial;

  // Acotado a los dos topes: sin esto la hoja se puede arrastrar fuera de
  // la pantalla por arriba o despegarse del borde inferior.
  const desplazamiento = Math.min(
    Math.max(arrastreHoja.desplazamientoInicial + recorrido, 0),
    topeRecogido()
  );

  colocarHoja(desplazamiento);
});

cabeceraPanel.addEventListener("pointerup", (evento) => {
  if (!arrastreHoja) {
    return;
  }

  const recorrido = evento.clientY - arrastreHoja.yInicial;

  // Se decide por el gesto, no por dónde quedó la hoja: un empujón corto y
  // rápido hacia arriba despliega aunque no se haya recorrido ni la mitad,
  // que es como se comporta cualquier hoja de este tipo. El umbral de 60px
  // evita que un toque con temblor cuente como arrastre.
  if (Math.abs(recorrido) > 60) {
    fijarEstadoHoja(recorrido < 0);
  } else {
    fijarEstadoHoja(hojaDesplegada);
  }

  cabeceraPanel.releasePointerCapture(evento.pointerId);
  panel.classList.remove("arrastrando");
  arrastreHoja = null;
});

// Un toque limpio en la cabecera, sin arrastre, alterna las dos posiciones.
cabeceraPanel.addEventListener("click", () => {
  if (consultaMovil.matches && !arrastreHoja) {
    fijarEstadoHoja(!hojaDesplegada);
  }
});

// Al cruzar el punto de ruptura cambian tanto el tamaño del mapa como su
// posicionamiento, y Leaflet mide su contenedor una sola vez: sin esto
// quedan franjas grises sin tiles, igual que al arrastrar el divisor.
consultaMovil.addEventListener("change", (evento) => {
  if (evento.matches) {
    fijarEstadoHoja(false);
  } else {
    // En escritorio la variable no pinta nada, pero se limpia para que al
    // volver a móvil no quede fijado un desplazamiento medido con la
    // ventana de otro tamaño.
    document.body.style.removeProperty("--hoja-y");
  }

  mapa.invalidateSize();
});

// Al girar el teléfono cambia innerHeight y con él los dos topes.
window.addEventListener("resize", () => {
  if (consultaMovil.matches) {
    fijarEstadoHoja(hojaDesplegada);
  }
});
