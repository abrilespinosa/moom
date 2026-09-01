/*
 * Service worker: solo la concha de la aplicación.
 *
 * Lo que resuelve: hoy, sin conexión, la página no abre siquiera. Con esto la
 * interfaz aparece al instante —incluso en el metro, sin cobertura— y en la
 * segunda visita no se vuelven a descargar 130 KB de tipografía ni el CSS.
 *
 * LO QUE NO HACE, Y ES DELIBERADO: no guarda ni una sola respuesta de la API.
 * Enseñar unas llegadas cacheadas sin decir de cuándo son sería exactamente lo
 * contrario del principio del proyecto —un dato viejo informa, pero solo si se
 * dice que es viejo—. Para eso hace falta antes un indicador de frescura en el
 * panel; mientras no exista, la API va siempre a la red y sin caché.
 *
 * ESTRATEGIA, y el porqué: red primero para HTML, CSS y JS.
 *
 * La tentación es caché primero, que es más rápido. Pero este proyecto no
 * tiene compilación y por tanto sus archivos no llevan hash en el nombre:
 * app.js se llama app.js para siempre. Con caché primero, quien haya abierto
 * la página una vez se queda clavado en esa versión hasta que expire algo, y
 * un fallo desplegado no llega nunca a quien ya la visitó. Es la forma clásica
 * de convertir un service worker en un problema peor que el que resuelve.
 *
 * Las fuentes y los iconos sí van caché primero: su contenido no cambia sin
 * cambiar de nombre, y son lo más pesado de la primera visita.
 */

// Al subir este número se descarta la caché anterior entera. Hay que subirlo
// cuando cambie la LISTA de abajo; para los cambios de contenido no hace
// falta, porque la estrategia de red primero ya los recoge sola.
const VERSION = "moom-v2";

// Lo mínimo para que la aplicación se dibuje sin red. No se precachea el
// callejero (254 KB): eso es dato, no concha.
const CONCHA = [
  "/",
  "/index.html",
  "/style.css",
  "/tipografia.css",
  "/app.js",
  "/privacidad.html",
  "/assets/logo.svg",
  "/assets/favicon.svg",
  "/assets/fuentes/inter-latin.woff2",
  "/assets/leaflet/leaflet.js",
  "/assets/leaflet/leaflet.css",
];

// Lo que se guarda para siempre porque su contenido no cambia sin cambiar de
// nombre: tipografías e imágenes.
const INMUTABLE = /\.(woff2|png|svg)$/;

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches
      .open(VERSION)
      // addAll falla entero si UN archivo falla, y eso dejaría la instalación
      // a medias por, digamos, un icono renombrado. Uno a uno y tolerante.
      .then((cache) => Promise.allSettled(CONCHA.map((ruta) => cache.add(ruta))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches
      .keys()
      .then((nombres) =>
        Promise.all(
          nombres.filter((n) => n !== VERSION).map((n) => caches.delete(n))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evento) => {
  const peticion = evento.request;
  const url = new URL(peticion.url);

  // Fuera de aquí: cualquier cosa que no sea un GET a nuestro propio dominio.
  // Eso deja pasar de largo los tiles de CARTO, que es lo único que sigue
  // viniendo de fuera.
  if (peticion.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }

  // La API nunca se cachea. Ver la nota de arriba.
  if (url.pathname.startsWith("/api/")) {
    return;
  }

  if (INMUTABLE.test(url.pathname)) {
    evento.respondWith(cachePrimero(peticion));
  } else {
    evento.respondWith(redPrimero(peticion));
  }
});

async function cachePrimero(peticion) {
  const guardado = await caches.match(peticion);

  if (guardado) {
    return guardado;
  }

  const respuesta = await fetch(peticion);

  if (respuesta.ok) {
    const cache = await caches.open(VERSION);
    cache.put(peticion, respuesta.clone());
  }

  return respuesta;
}

async function redPrimero(peticion) {
  try {
    const respuesta = await fetch(peticion);

    // Solo se guarda lo que salió bien. Cachear un 404 o un 500 lo serviría
    // después aunque el servidor ya estuviera arreglado.
    if (respuesta.ok) {
      const cache = await caches.open(VERSION);
      cache.put(peticion, respuesta.clone());
    }

    return respuesta;
  } catch (error) {
    const guardado = await caches.match(peticion);

    if (guardado) {
      return guardado;
    }

    throw error;
  }
}
