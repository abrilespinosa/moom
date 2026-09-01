"""
Andamiaje para los tests de frontend.

La idea, en una frase: se copia frontend/ a un directorio temporal, allí se
cambia lo justo para que la página no salga a internet, y se abre con Chrome
en modo headless para leer el DOM que queda después de ejecutar el JavaScript.

Es la misma técnica que ya estaba documentada para depurar a mano; aquí solo
se automatiza. Tres cosas se tocan en la copia, y ninguna en el frontend real:

1. URL_BACKEND apunta al backend de mentira que sirve este mismo archivo, en
   vez de a 127.0.0.1:8000. Así los tests no necesitan un uvicorn levantado ni
   dependen de que EMT o el CRTM respondan.
2. Leaflet se sustituye por leaflet_falso.js. Desde que se autoaloja ya no es
   por la red, sino porque aquí no se prueba Leaflet: es código de otros.
3. Se añade al final un guion de prueba, que es lo que cada test quiere probar.

Todo se sirve desde UN solo servidor y, por tanto, desde un solo origen: así
no hay CORS de por medio, igual que en producción.
"""

import json
import http.server
import os
import re
import shutil
import socketserver
import subprocess
import threading

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIRECTORIO_FRONTEND = os.path.join(RAIZ, "frontend")
LEAFLET_FALSO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leaflet_falso.js")

# Dónde está Chrome. La ruta por defecto es la de macOS, que es donde se
# desarrolla esto; en otro sistema se indica con la variable de entorno
# CHROME_PARA_TESTS en vez de tocar el archivo.
#
# Si no está, los tests se saltan con un motivo legible en vez de reventar con
# un FileNotFoundError: en GitHub Actions no hay Chrome en esta ruta, y que la
# suite entera se caiga por eso sería peor que no ejecutarlos.
CHROME = os.environ.get(
    "CHROME_PARA_TESTS", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)

# Prefijo del backend de mentira. Va colgando del mismo servidor que sirve la
# página para que compartan origen.
RUTA_API = "/api-de-mentira"

# Cuánto tiempo virtual se le deja correr a la página. No son segundos de
# reloj: --virtual-time-budget adelanta los temporizadores, así que esto se
# consume en mucho menos tiempo real.
PRESUPUESTO_MS = 12000


# --- Datos que devuelve el backend de mentira ---------------------------------
#
# Escritos a mano y a propósito pequeños. Tienen la MISMA forma que los del
# backend de verdad (comprobado contra sus endpoints), pero con lo mínimo para
# que se pueda razonar sobre lo que debería salir en pantalla: si un test dice
# que buscar "27" pone la línea 27 primero, aquí se ve por qué.

PARADAS = [
    {"id": "72", "nombre": "Cibeles", "lat": 40.41926, "lon": -3.69333, "fuente": "EMT"},
    {"id": "270", "nombre": "Atocha", "lat": 40.40736, "lon": -3.69175, "fuente": "EMT"},
    {
        "id": "par_8_06002",
        "nombre": "Avenida de America",
        "lat": 40.43819,
        "lon": -3.67736,
        "fuente": "CRTM",
    },
    {
        "id": "est_4_323",
        "nombre": "Alsacia",
        "codAnden": "4_323",
        "lat": 40.41829,
        "lon": -3.62351,
        "fuente": "METRO",
        "accesibilidad": "universal",
    },
    # Las tres de abajo existen para poder distinguir los cuatro casos de
    # accesibilidad, que es lo único que hace comprobable esta parte.
    {
        "id": "est_4_77",
        "nombre": "Chueca",
        "codAnden": "4_77",
        "lat": 40.42260,
        "lon": -3.69700,
        "fuente": "METRO",
        "accesibilidad": "solo_ascensor",
    },
    {
        # El caso peligroso: tiene medidas complementarias pero NI ascensor NI
        # rampa, así que NO puede llevar el icono de silla ni contar como
        # accesible. Es el error que más daño haría de todos los posibles.
        "id": "est_4_88",
        "nombre": "Lavapies",
        "codAnden": "4_88",
        "lat": 40.40880,
        "lon": -3.70090,
        "fuente": "METRO",
        "accesibilidad": "solo_medidas",
    },
    {
        # Y una sin dato ninguno: no todas las estaciones están en la lista
        # oficial de Metro (76 de 242 no aparecen).
        "id": "est_4_99",
        "nombre": "Tirso de Molina",
        "codAnden": "4_99",
        "lat": 40.41190,
        "lon": -3.70320,
        "fuente": "METRO",
    },
]

LINEAS = [
    {
        "id": "EMT-027",
        "numero": "27",
        "nombre": "Plaza Castilla - Embajadores",
        "fuente": "EMT",
        "color": "0178BC",
        "colorTexto": "FFFFFF",
    },
    {
        "id": "EMT-270",
        "numero": "270",
        "nombre": "Canillejas - Torrejon",
        "fuente": "EMT",
        "color": "0178BC",
        "colorTexto": "FFFFFF",
    },
    {
        # Número bajo, pero con "27" en el NOMBRE. Es el caso que hace falta
        # para que el desempate de buscarLineas() se note: buscando "27" esta
        # línea también coincide, y por orden numérico (4 < 27) se colocaría
        # la primera. Sin una línea así en estos datos, el test pasaba igual
        # con el desempate borrado, o sea que no probaba nada.
        "id": "EMT-004",
        "numero": "4",
        "nombre": "Barrio del Pilar - 27 de Enero",
        "fuente": "EMT",
        "color": "0178BC",
        "colorTexto": "FFFFFF",
    },
    {
        "id": "METRO-4__2___",
        "numero": "2",
        "nombre": "Las Rosas - Cuatro Caminos",
        "fuente": "METRO",
        "color": "ED1C24",
        "colorTexto": "FFFFFF",
    },
]

COLORES_METRO = {
    "4__2___": {"numero": "2", "color": "ED1C24", "color_texto": "FFFFFF"},
}

RECORRIDO_27 = {
    "encontrada": True,
    "id": "EMT-027",
    "numero": "27",
    "nombre": "Plaza Castilla - Embajadores",
    "fuente": "EMT",
    "color": "0178BC",
    "colorTexto": "FFFFFF",
    "sentidos": [
        {
            "destino": "EMBAJADORES",
            "paradas": [
                {"id": "72", "nombre": "Cibeles"},
                {"id": "270", "nombre": "Atocha"},
            ],
        }
    ],
}

# Un par de llegadas de EMT con la forma cruda de su API (data[0].Arrive).
LLEGADAS_EMT = {
    "data": [
        {
            # geometry es obligatorio: app.js pinta un marcador por autobús
            # y lee bus.geometry.coordinates ([lon, lat]) antes de nada.
            "Arrive": [
                {
                    "line": "27",
                    "destination": "EMBAJADORES",
                    "estimateArrive": 120,
                    "geometry": {"coordinates": [-3.69333, 40.41926]},
                },
                {
                    "line": "27",
                    "destination": "EMBAJADORES",
                    "estimateArrive": 600,
                    "geometry": {"coordinates": [-3.69500, 40.42000]},
                },
            ]
        }
    ]
}

# Una estación de Metro con una línea y un tren, para poder reproducir la
# carrera entre la respuesta y el botón Volver.
METRO_ALSACIA = {
    "estacion": "ALSACIA",
    "codStop": "est_4_323",
    "codLines": ["4__2___"],
    "llegadas": [
        {
            "codLine": "4__2___",
            "linea": "2",
            "destino": "LAS ROSAS",
            "tiempos": ["2026-08-31T21:05:00+02:00"],
            "enVivo": None,
        }
    ],
}

VEHICULOS_L2 = {
    "linea": "Las Rosas-Cuatro Caminos",
    "codLine": "4__2___",
    "color": "ED1C24",
    "colorTexto": "FFFFFF",
    # "line" es obligatorio: app.js lee tren.line.shortDescription para el
    # número del distintivo y tren.line.description para el sentido. Sin él
    # revienta, el try lo traga y el test miente diciendo que no hay trenes.
    "vehiculos": [
        {
            "codVehicle": "1001",
            "coordinates": {"latitude": 40.4183, "longitude": -3.6235},
            "line": {
                "shortDescription": "2",
                "description": "2-Las Rosas-Cuatro Caminos",
            },
        },
        {
            "codVehicle": "1002",
            "coordinates": {"latitude": 40.4200, "longitude": -3.6300},
            "line": {
                "shortDescription": "2",
                "description": "2-Cuatro Caminos-Las Rosas",
            },
        },
    ],
}

# Tres avisos, uno de cada estado. Con los tres se puede comprobar que el
# contador solo cuenta los EN CURSO y que los terminados se enseñan igual,
# atenuados, porque saber que el desvío ya acabó también informa.
INCIDENCIAS = {
    "enCurso": 1,
    "programadas": 1,
    "incidencias": [
        {
            "titulo": "Corte en Gran Vía. Afectadas 4 líneas de EMT.",
            "descripcion": "Hoy, de 10:00 a 20:00, las líneas 1, 2, 44 y 133 circulan desviadas.",
            "causa": "04 - Manifestación",
            "efecto": "05 - Desvío programado",
            "desde": "01/09/2026 10:00:00",
            "hasta": "01/09/2026 20:00:00",
            "estado": "en_curso",
            "masInfo": "https://www.crtm.es/aviso.pdf",
        },
        {
            "titulo": "Carrera popular en Castellana. Afectadas 9 líneas.",
            "descripcion": "El 3 de septiembre, de 18:30 a 21:00.",
            "causa": "12 - Evento deportivo",
            "efecto": "05 - Desvío programado",
            "desde": "03/09/2026 18:30:00",
            "hasta": "03/09/2026 21:00:00",
            "estado": "programada",
            "masInfo": None,
        },
        {
            "titulo": "Obras en Atocha. Afectada la línea 27.",
            "descripcion": "El 20 de agosto, de 08:00 a 14:00.",
            "causa": "02 - Obras",
            "efecto": "05 - Desvío programado",
            "desde": "20/08/2026 08:00:00",
            "hasta": "20/08/2026 14:00:00",
            "estado": "terminada",
            "masInfo": None,
        },
    ],
}

RESPUESTAS = {
    "/paradas": PARADAS,
    "/incidencias": INCIDENCIAS,
    "/metro/parada/est_4_323": METRO_ALSACIA,
    "/metro/parada/est_4_323/lineas": {"codStop": "est_4_323", "codLines": ["4__2___"]},
    "/metro/linea/4__2___/vehiculos": VEHICULOS_L2,
    "/lineas": LINEAS,
    "/metro/lineas/colores": COLORES_METRO,
    "/linea/EMT-027": RECORRIDO_27,
    "/parada/72": LLEGADAS_EMT,
}


class _Manejador(http.server.SimpleHTTPRequestHandler):
    """Sirve los archivos de la copia y, bajo RUTA_API, el backend de mentira."""

    def do_GET(self):
        ruta = self.path.split("?")[0]

        if ruta.startswith(RUTA_API):
            self._responder_api(ruta[len(RUTA_API) :])
            return

        super().do_GET()

    def _responder_api(self, ruta):
        if ruta in RESPUESTAS:
            cuerpo = json.dumps(RESPUESTAS[ruta]).encode("utf-8")
            self.send_response(200)
        else:
            # Igual que el backend real ante algo que no conoce. Importa que
            # sea un código de error y no un 200 vacío: pedirJson() distingue
            # por el código, y hay un test que depende de ello.
            cuerpo = json.dumps({"error": "no_encontrado"}).encode("utf-8")
            self.send_response(404)

        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *_args):
        """Sin ruido: si no, cada test escupe una línea por archivo servido."""


@pytest.fixture(scope="session", autouse=True)
def exigir_chrome():
    """Sin navegador no hay nada que probar aquí, pero tampoco nada que romper."""
    if not os.path.exists(CHROME):
        pytest.skip(
            f"No se encontró Chrome en {CHROME}. "
            f"Indica su ruta con CHROME_PARA_TESTS para ejecutar estos tests.",
            allow_module_level=True,
        )


@pytest.fixture(scope="session")
def sitio(tmp_path_factory):
    """
    Levanta la copia del frontend servida por HTTP y devuelve su URL base.

    De sesión y no por test: copiar los archivos y arrancar el servidor cuesta
    lo mismo para uno que para todos, y ningún test escribe en el directorio
    (cada uno genera su propia página, ver `render`).
    """
    directorio = tmp_path_factory.mktemp("frontend")

    shutil.copytree(DIRECTORIO_FRONTEND, directorio, dirs_exist_ok=True)
    shutil.copy(LEAFLET_FALSO, directorio / "leaflet_falso.js")

    _apuntar_al_backend_de_mentira(directorio / "app.js")
    _sustituir_leaflet(directorio / "index.html")

    manejador = lambda *args: _Manejador(*args, directory=str(directorio))
    servidor = socketserver.TCPServer(("127.0.0.1", 0), manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()

    puerto = servidor.server_address[1]

    yield {"url": f"http://127.0.0.1:{puerto}", "directorio": directorio}

    servidor.shutdown()
    servidor.server_close()


def _apuntar_al_backend_de_mentira(ruta_app_js):
    codigo = ruta_app_js.read_text(encoding="utf-8")

    # app.js decide su backend por el puerto (5500 es desarrollo local). Aquí
    # el puerto lo asigna el sistema operativo, así que se sustituye la
    # constante entera en vez de intentar acertar con el puerto.
    nuevo, sustituciones = re.subn(
        r'const URL_BACKEND = .*?;',
        f'const URL_BACKEND = "{RUTA_API}";',
        codigo,
        count=1,
    )

    assert sustituciones == 1, "No se encontró URL_BACKEND en app.js"

    ruta_app_js.write_text(nuevo, encoding="utf-8")


def _sustituir_leaflet(ruta_index):
    """
    Cambia Leaflet por el doble.

    Desde que Leaflet se autoaloja, esto ya no es por la red —el archivo está
    en el propio directorio copiado— sino por lo mismo de siempre: aquí no se
    prueba Leaflet, que es código de otros, sino el buscador, los paneles y el
    cambio de vistas. El doble hace que el mapa no reviente al crearse y ya.
    """
    html = ruta_index.read_text(encoding="utf-8")

    html = html.replace(
        '<script src="assets/leaflet/leaflet.js"></script>',
        '<script src="leaflet_falso.js"></script>',
    )

    # Su hoja de estilos tampoco hace falta y solo mete ruido en las medidas.
    html = html.replace('<link rel="stylesheet" href="assets/leaflet/leaflet.css" />', "")

    assert "leaflet_falso.js" in html, "No se sustituyó Leaflet en index.html"
    assert "leaflet/leaflet.js" not in html, "Queda el Leaflet de verdad en index.html"

    ruta_index.write_text(html, encoding="utf-8")


# --- Ejecutar un guion en la página -------------------------------------------

# Ayudas que se le dan a cada guion de prueba. Van aquí y no en cada test para
# que los tests digan QUÉ comprueban y no cómo esperar.
AYUDAS = """
<script>
  // Espera a que una condición se cumpla, hasta un límite. Hace falta porque
  // app.js arranca de forma asíncrona: pide las paradas y las líneas al
  // servidor, y hasta que no llegan no hay nada en pantalla que mirar.
  async function esperarA(condicion, limite = 8000) {
    const hasta = Date.now() + limite;
    while (Date.now() < hasta) {
      if (condicion()) return true;
      await new Promise((listo) => setTimeout(listo, 50));
    }
    return false;
  }

  // Los resultados del buscador incluyen encabezados de grupo ("Cerca de ti",
  // "Líneas"), que no son pulsables. Esta es la lista de los que sí.
  function resultados() {
    return [...document.querySelectorAll("#lista-resultados li:not(.grupo-resultados)")];
  }

  // Lo pulsable de un resultado es un <button class="resultado-principal">
  // dentro del <li>, no el <li>. Pulsar el <li> no hace nada, igual que para
  // una persona: el cambio se hizo para que el teclado pueda alcanzarlo.
  function pulsarResultado(n = 0) {
    resultados()[n].querySelector(".resultado-principal").click();
  }

  function escribirEnBuscador(texto) {
    const campo = document.getElementById("input-buscar");
    campo.value = texto;
    campo.dispatchEvent(new Event("input", { bubbles: true }));
  }

  // El resultado del guion se deja aquí, en JSON, y el test lo lee del DOM.
  // Es mucho más robusto que hacer que Python interprete el HTML entero.
  function responder(valor) {
    const caja = document.createElement("div");
    caja.id = "resultado-prueba";
    caja.textContent = JSON.stringify(valor);
    document.body.appendChild(caja);
  }

  function vistaVisible() {
    for (const id of ["vista-busqueda", "vista-linea", "vista-llegadas", "vista-incidencias"]) {
      const vista = document.getElementById(id);
      if (vista && getComputedStyle(vista).display !== "none") return id;
    }
    return null;
  }
</script>
"""

_RESULTADO = re.compile(
    r'<div id="resultado-prueba">(.*?)</div>', re.DOTALL
)


@pytest.fixture(scope="session")
def render(sitio):
    """
    Devuelve una función render(guion) -> lo que el guion pase a responder().

    El guion es JavaScript que se ejecuta en la página ya cargada. Debe acabar
    llamando a responder(...) con lo que el test quiera comprobar.
    """
    contador = {"n": 0}

    def _render(guion, presupuesto_ms=PRESUPUESTO_MS):
        contador["n"] += 1
        nombre = f"prueba-{contador['n']}.html"

        html = (sitio["directorio"] / "index.html").read_text(encoding="utf-8")
        pagina = html.replace(
            "</body>",
            AYUDAS + f"<script>(async () => {{ {guion} }})();</script></body>",
        )
        (sitio["directorio"] / nombre).write_text(pagina, encoding="utf-8")

        salida = subprocess.run(
            [
                CHROME,
                "--headless",
                "--disable-gpu",
                # Las dos siguientes son para que esto funcione también en un
                # servidor de integración continua, no en local: sin sandbox
                # porque allí se ejecuta como root, y sin /dev/shm porque en
                # un contenedor suele ser diminuto y Chrome se cae al llenarlo.
                "--no-sandbox",
                "--disable-dev-shm-usage",
                f"--virtual-time-budget={presupuesto_ms}",
                "--dump-dom",
                f"{sitio['url']}/{nombre}",
            ],
            capture_output=True,
            text=True,
            timeout=90,
        )

        encontrado = _RESULTADO.search(salida.stdout)

        if not encontrado:
            raise AssertionError(
                "El guion no llamó a responder(). Puede que app.js lanzara un "
                "error antes de llegar.\n\n"
                f"--- DOM devuelto (primeros 2000 caracteres) ---\n"
                f"{salida.stdout[:2000]}"
            )

        return json.loads(_desescapar(encontrado.group(1)))

    return _render


def _desescapar(texto):
    """El DOM volcado trae las entidades HTML escapadas."""
    return (
        texto.replace("&quot;", '"')
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
    )
