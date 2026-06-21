// URL de tu servidor FastAPI corriendo en local
const URL_BACKEND = "http://127.0.0.1:8000";

// Número de parada que vamos a consultar
let STOP_ID = null;

// Guardamos aquí todas las paradas descargadas, para poder
// buscarlas localmente sin volver a llamar al backend.
let TODAS_LAS_PARADAS = [];

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

function crearIcono(archivo, tamano) {
  return L.icon({
    iconUrl: `assets/${archivo}`,
    iconSize: tamano,
    iconAnchor: [tamano[0] / 2, tamano[1]],
  });
}

// Los 4 iconos posibles se crean UNA sola vez y se reutilizan para
// las 13.320 paradas. Nunca se crea un icono nuevo por parada.
const ICONOS = {
  EMT: {
    normal: crearIcono("bus-urbano.png", TAMANO_ICONO_NORMAL),
    seleccionado: crearIcono("bus-urbano-selected.png", TAMANO_ICONO_SELECCIONADO),
  },
  CRTM: {
    normal: crearIcono("bus-interurbano.png", TAMANO_ICONO_NORMAL),
    seleccionado: crearIcono("bus-interurbano-selected.png", TAMANO_ICONO_SELECCIONADO),
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
  });
}

// Reevaluamos qué paradas mostrar tanto al hacer zoom (zoomend) como
// al arrastrar el mapa (moveend) — si no escucháramos moveend, al
// desplazarte sin cambiar de zoom las paradas nuevas que entran en
// pantalla no aparecerían hasta el siguiente zoom.
mapa.on("zoomend", actualizarVisibilidadParadas);
mapa.on("moveend", actualizarVisibilidadParadas);

dibujarParadas();

// --- Referencias a los elementos del DOM que vamos a manipular ---
const inputBuscar = document.getElementById("input-buscar");
const listaResultados = document.getElementById("lista-resultados");
const vistaBusqueda = document.getElementById("vista-busqueda");
const vistaLlegadas = document.getElementById("vista-llegadas");
const nombreParadaActual = document.getElementById("nombre-parada-actual");
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
  STOP_ID = parada.id;

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

  // Cambiamos de vista: ocultamos buscador, mostramos llegadas
  vistaBusqueda.style.display = "none";
  vistaLlegadas.style.display = "flex";
  subtituloHeader.textContent = "Próximas llegadas";
  nombreParadaActual.textContent = `${parada.nombre} · parada ${parada.id}`;

  // Limpiamos el buscador para la próxima vez que se use
  inputBuscar.value = "";
  listaResultados.innerHTML = "";

  actualizarAutobuses();
}

// Botón para volver del estado "llegadas" al estado "buscador"
botonVolver.addEventListener("click", () => {
  STOP_ID = null;
  vistaLlegadas.style.display = "none";
  vistaBusqueda.style.display = "block";
  subtituloHeader.textContent = "Busca una parada para ver sus llegadas";

  // Quitamos el resaltado, ya no hay una parada "activa"
  if (paradaSeleccionada && paradaSeleccionada.circuloEnMapa) {
    paradaSeleccionada.circuloEnMapa.setIcon(iconoNormalPara(paradaSeleccionada));
  }
  paradaSeleccionada = null;

  // Limpiamos las tarjetas de la parada anterior...
  listaLlegadas.innerHTML = "";

  // ...y también los marcadores de bus que quedaban en el mapa.
  marcadoresActuales.forEach((marcador) => mapa.removeLayer(marcador));
  marcadoresActuales = [];
});

// Convierte segundos en un texto legible: "En camino" si está muy
// cerca, o "X min" en caso contrario.
function formatearMinutos(segundos) {
  const minutos = Math.floor(segundos / 60);
  return minutos < 1 ? "En camino" : `${minutos}`;
}

// Guardamos los marcadores actuales del mapa para poder borrarlos y
// redibujarlos cada vez que llegan datos nuevos.
let marcadoresActuales = [];

async function actualizarAutobuses() {
  if (STOP_ID === null) {
    return; // todavía no se ha seleccionado ninguna parada
  }

  try {
    const respuesta = await fetch(`${URL_BACKEND}/parada/${STOP_ID}`);
    const datos = await respuesta.json();
    const autobuses = datos.data[0].Arrive;

    // --- 1. Dibujamos los marcadores en el mapa (igual que antes) ---
    marcadoresActuales.forEach((marcador) => mapa.removeLayer(marcador));
    marcadoresActuales = [];

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

      const marcador = L.marker([lat, lon], { icon: iconoLinea }).addTo(mapa);
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
      listaLlegadas.innerHTML =
        '<div id="mensaje-vacio">No hay autobuses en camino ahora mismo.</div>';
      return;
    }

    tarjetas.forEach((tarjeta) => {
      const item = document.createElement("li");
      item.className = "tarjeta-bus";

      // Tiempos secundarios (todos menos el primero), unidos por coma.
      // Ej: si tiempos = [120, 540], queda "9 min" como secundario.
      const tiemposSecundarios = tarjeta.tiempos
        .slice(1)
        .map((s) => formatearMinutos(s))
        .join(", ");

      item.innerHTML = `
        <div class="tarjeta-linea">${tarjeta.line}</div>
        <div class="tarjeta-info">
          <div class="tarjeta-destino">→ ${tarjeta.destination}</div>
          ${
            tiemposSecundarios
              ? `<div class="tarjeta-tiempos">Siguiente: ${tiemposSecundarios} min</div>`
              : ""
          }
        </div>
        <div class="tiempo-proximo">
          ${formatearMinutos(tarjeta.tiempos[0])}
          <span class="unidad">${
            Math.floor(tarjeta.tiempos[0] / 60) < 1 ? "" : "min"
          }</span>
        </div>
      `;

      listaLlegadas.appendChild(item);
    });
  } catch (error) {
    console.error("Error al actualizar los autobuses:", error);
  }
}

setInterval(actualizarAutobuses, 10000);

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