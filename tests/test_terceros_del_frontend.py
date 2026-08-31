"""
Con qué terceros habla el navegador de quien visita la página.

Esto no es una comprobación técnica, es una promesa: la página de privacidad
enumera exactamente a qué servidores ajenos se conecta el navegador, y esa
lista tiene que seguir siendo cierta. Cualquiera puede añadir una fuente, un
icono o una librería desde un CDN sin caer en que, con ello, está mandando la
dirección IP de cada visitante a una empresa más.

Va en la suite rápida y no en la de navegador a propósito: son archivos leídos
del disco, así que cuesta milisegundos y se ejecuta en cada cambio.
"""

import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRECTORIO_FRONTEND = os.path.join(RAIZ, "frontend")

# Los únicos servidores ajenos permitidos, y el motivo de cada uno. Añadir algo
# aquí es una decisión con consecuencias de privacidad: hay que reflejarla
# también en la tabla de frontend/privacidad.html.
TERCEROS_PERMITIDOS = {
    "unpkg.com": "Leaflet, la librería del mapa",
    "basemaps.cartocdn.com": "las imágenes del mapa",
    # No es un servidor al que se pida nada: aparece como atribución del mapa
    # y en enlaces de la página de privacidad.
    "www.openstreetmap.org": "atribución de la cartografía",
    "carto.com": "atribución de la cartografía",
    "www.emtmadrid.es": "enlace al canal oficial",
    "www.metromadrid.es": "enlace al canal oficial",
    "www.crtm.es": "enlace al canal oficial",
    "github.com": "enlace al repositorio",
}

# Cosas que PARECEN un tercero y no lo son. Ninguna genera una petición de red,
# así que ninguna transmite la IP de nadie:
#
# - www.w3.org es el espacio de nombres XML de los SVG incrustados como data:
#   URI. Es un identificador, no una dirección: el navegador no lo descarga
#   nunca. Es el falso positivo clásico de esta clase de comprobación.
# - 127.0.0.1 es el backend en desarrollo local. En producción la constante
#   URL_BACKEND vale "/api", del mismo dominio.
NO_SON_TERCEROS = {"www.w3.org", "127.0.0.1", "localhost"}

# Servidores que NO deben aparecer aunque a alguien le resulten cómodos. Se
# nombran uno a uno, en vez de confiar en la lista blanca, para que el fallo
# diga POR QUÉ es un problema y no solo que hay un host nuevo.
PROHIBIDOS = {
    "fonts.googleapis.com": (
        "Google Fonts envía la IP de cada visitante a Google. La tipografía "
        "está en frontend/assets/fuentes y se declara en tipografia.css."
    ),
    "fonts.gstatic.com": "Ídem: los archivos de fuente se sirven desde el propio dominio.",
    "www.google-analytics.com": "No hay analítica, y la página de privacidad lo afirma.",
    "googletagmanager.com": "No hay analítica, y la página de privacidad lo afirma.",
}

_URL = re.compile(r"https?://([a-zA-Z0-9.-]+)")


def _hosts_del_frontend():
    """Todos los hosts que aparecen en el HTML, el CSS y el JS que se sirven."""
    hosts = {}

    for nombre in os.listdir(DIRECTORIO_FRONTEND):
        if not nombre.endswith((".html", ".css", ".js")):
            continue

        ruta = os.path.join(DIRECTORIO_FRONTEND, nombre)
        with open(ruta, encoding="utf-8") as archivo:
            for linea in archivo:
                # Los comentarios explican por qué NO se usa algo (Google
                # Fonts, por ejemplo), así que citar un host ahí no significa
                # que se le pida nada. Se saltan.
                if linea.lstrip().startswith(("//", "*", "/*", "<!--", "#")):
                    continue

                for host in _URL.findall(linea):
                    hosts.setdefault(host, []).append(f"{nombre}: {linea.strip()[:90]}")

    return hosts


def test_no_se_carga_nada_desde_google():
    """
    El caso con jurisprudencia detrás: en 2022 el tribunal regional de Múnich
    condenó por servir Google Fonts desde los servidores de Google, porque
    transmite la IP del visitante sin base legal. La tipografía se trajo al
    proyecto justamente por esto, y este test evita que vuelva.
    """
    hosts = _hosts_del_frontend()

    for prohibido, motivo in PROHIBIDOS.items():
        coincidencias = [h for h in hosts if prohibido in h]
        assert not coincidencias, (
            f"{prohibido} aparece en el frontend. {motivo}\n"
            f"Dónde: {hosts[coincidencias[0]]}"
        )


def test_los_terceros_son_solo_los_declarados_en_la_pagina_de_privacidad():
    """
    Si este test falla por un host nuevo, lo que hay que hacer NO es añadirlo a
    la lista sin más: primero decidir si de verdad hace falta, y si la
    respuesta es sí, describirlo en la tabla de frontend/privacidad.html. Esa
    página afirma que la lista está completa.
    """
    hosts = _hosts_del_frontend()

    inesperados = {
        host: donde
        for host, donde in hosts.items()
        if host not in TERCEROS_PERMITIDOS
        and host not in NO_SON_TERCEROS
        and not host.endswith(".basemaps.cartocdn.com")
    }

    assert not inesperados, (
        "Terceros no declarados en el frontend: "
        + ", ".join(sorted(inesperados))
        + ". Añádelos a la tabla de frontend/privacidad.html antes de permitirlos aquí."
    )


def test_la_tipografia_se_sirve_desde_el_propio_dominio():
    """La otra mitad: no basta con quitar Google, tiene que haber fuente."""
    ruta = os.path.join(DIRECTORIO_FRONTEND, "tipografia.css")

    with open(ruta, encoding="utf-8") as archivo:
        css = archivo.read()

    assert "@font-face" in css
    assert 'url("assets/fuentes/' in css

    for nombre in ("inter-latin.woff2", "inter-latin-ext.woff2"):
        assert os.path.exists(
            os.path.join(DIRECTORIO_FRONTEND, "assets", "fuentes", nombre)
        ), f"Falta {nombre}: la página se quedaría sin tipografía."

    # La SIL Open Font License exige que su texto acompañe a los archivos allá
    # donde se redistribuyan, y servirlos desde una web es redistribuirlos.
    assert os.path.exists(
        os.path.join(DIRECTORIO_FRONTEND, "assets", "fuentes", "OFL.txt")
    ), "Falta la licencia de Inter junto a los archivos de fuente."
