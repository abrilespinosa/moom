"""
Convierte una dirección escrita en coordenadas, para poder pedir una ruta a
un sitio y no solo a una parada.

Usa Nominatim, el buscador de OpenStreetMap. Es gratuito y no pide clave,
pero sí exige respetar su política de uso: identificarse con un User-Agent
propio y no pasar de una consulta por segundo. Las dos cosas se cumplen
aquí, y por eso la llamada sale del backend y no del navegador: desde el
frontend cada visitante tendría su propio ritmo y no habría forma de
respetar ese límite ni de cachear nada.
"""

import threading
import time

import requests

URL = "https://nominatim.openstreetmap.org/search"

# Nominatim rechaza a quien no se identifica. Que apunte al repositorio es
# lo que ellos piden: si algo va mal, quieren poder avisar a alguien.
CABECERAS = {"User-Agent": "Moom/1.0 (https://github.com/abrilespinosa/moom)"}

TIMEOUT_SEGUNDOS = (5, 10)

# El rectángulo de la Comunidad de Madrid. Sin acotar, "Alcalá" devuelve
# antes Alcalá de Guadaíra que la calle de Alcalá.
RECUADRO_MADRID = "-4.60,41.20,-3.05,39.85"

# Una consulta por segundo como máximo, que es lo que pide su política de
# uso. El cerrojo es necesario porque los endpoints de FastAPI corren en
# hilos distintos y sin él dos búsquedas simultáneas se saltarían el límite.
_cerrojo = threading.Lock()
_ultima_llamada = 0.0

# Las direcciones no se mueven, así que lo que se busca una vez se guarda
# para siempre. Además de ahorrar tiempo, es la mejor forma de no gastar la
# cuota de un servicio que nos deja usarlo gratis.
_cache = {}


def buscar(texto, limite=5):
    """
    Devuelve una lista de sitios que encajan con el texto.

    Cada uno con su nombre y sus coordenadas, ya en el formato que usa el
    resto de la aplicación.
    """
    consulta = texto.strip().lower()

    if not consulta:
        return []

    if consulta in _cache:
        return _cache[consulta]

    global _ultima_llamada
    with _cerrojo:
        espera = 1.0 - (time.monotonic() - _ultima_llamada)
        if espera > 0:
            time.sleep(espera)
        _ultima_llamada = time.monotonic()

    respuesta = requests.get(
        URL,
        params={
            "q": texto,
            "format": "jsonv2",
            "limit": limite,
            "viewbox": RECUADRO_MADRID,
            "bounded": 1,
            "addressdetails": 1,
        },
        headers=CABECERAS,
        timeout=TIMEOUT_SEGUNDOS,
    )
    respuesta.raise_for_status()

    resultados = [
        {
            "nombre": sitio["display_name"],
            "lat": float(sitio["lat"]),
            "lon": float(sitio["lon"]),
        }
        for sitio in respuesta.json()
    ]

    _cache[consulta] = resultados
    return resultados
