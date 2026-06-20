// URL de tu servidor FastAPI corriendo en local
const URL_BACKEND = "http://127.0.0.1:8000";

// Número de parada que vamos a consultar
let STOP_ID = null;

// Guardamos aquí todas las paradas descargadas, para poder
// buscarlas localmente sin volver a llamar al backend.
let TODAS_LAS_PARADAS = [];

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

// Estilo normal (gris, pequeño) vs. estilo resaltado (rojo, más grande)
// para distinguir visualmente la parada que el usuario ha seleccionado.
const ESTILO_PARADA_NORMAL = { radius: 6, color: "gray", fillColor: "gray", fillOpacity: 0.8 };
const ESTILO_PARADA_SELECCIONADA = { radius: 9, color: "#cc0000", fillColor: "#cc0000", fillOpacity: 0.9 };

// Guardamos qué parada está resaltada ahora, para poder devolverla
// a su estilo normal cuando el usuario seleccione otra distinta.
let paradaSeleccionada = null;

async function dibujarParadas() {
  const respuesta = await fetch(`${URL_BACKEND}/paradas`);
  const paradas = await respuesta.json();

  TODAS_LAS_PARADAS = paradas;

  paradas.forEach((parada) => {
    // OJO: ya no usamos ".addTo(mapa)" aquí. Creamos el círculo pero
    // no lo añadimos todavía — eso lo decide actualizarVisibilidadParadas().
    const circulo = L.circleMarker(
      [parada.lat, parada.lon],
      ESTILO_PARADA_NORMAL
    );

    circulo.on("click", () => {
      seleccionarParada(parada);
    });

    // Guardamos el círculo dentro de la propia parada. Así, cuando
    // seleccionarParada() se llama desde el buscador (que solo tiene
    // los datos, no el círculo), igualmente podemos encontrarlo.
    parada.circuloEnMapa = circulo;

    marcadoresParadas.push(circulo);
  });

  // Una vez creados todos los círculos, decidimos cuáles mostrar
  // según el zoom con el que arrancó el mapa.
  actualizarVisibilidadParadas();
}

// Añade o quita los círculos de parada del mapa según el zoom actual.
// Se llama al cargar las paradas y cada vez que el usuario hace zoom.
function actualizarVisibilidadParadas() {
  const zoomActual = mapa.getZoom();
  const debenVerse = zoomActual >= ZOOM_MINIMO_PARADAS;

  marcadoresParadas.forEach((circulo) => {
    const estaEnElMapa = mapa.hasLayer(circulo);

    if (debenVerse && !estaEnElMapa) {
      circulo.addTo(mapa);
    } else if (!debenVerse && estaEnElMapa) {
      mapa.removeLayer(circulo);
    }
  });
}

// Cada vez que el usuario termina de hacer zoom (rueda del ratón,
// botones +/-, o doble clic), reevaluamos qué paradas mostrar.
mapa.on("zoomend", actualizarVisibilidadParadas);

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

  // Si había una parada resaltada de antes, la devolvemos a su
  // estilo normal antes de resaltar la nueva.
  if (paradaSeleccionada && paradaSeleccionada.circuloEnMapa) {
    paradaSeleccionada.circuloEnMapa.setStyle(ESTILO_PARADA_NORMAL);
  }

  // Resaltamos la parada recién elegida, si su círculo está dibujado
  // en el mapa (puede no estarlo si el zoom actual es muy bajo).
  if (parada.circuloEnMapa) {
    parada.circuloEnMapa.setStyle(ESTILO_PARADA_SELECCIONADA);
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

  // Quitamos el resaltado rojo, ya no hay una parada "activa"
  if (paradaSeleccionada && paradaSeleccionada.circuloEnMapa) {
    paradaSeleccionada.circuloEnMapa.setStyle(ESTILO_PARADA_NORMAL);
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