"""
emt_client.py

Primer paso de conexión con la API de EMT Madrid (Mobility Labs).

Qué hace este script:
1. Lee las credenciales (email y password de tu cuenta de Mobility Labs) desde el archivo .env
2. Hace login contra la API de EMT
3. Imprime el token de acceso que nos devuelven, para confirmar que la conexión funciona

Nota: la API de EMT cambió su sistema de autenticación. Ya no se usa el
X-ClientId/passKey de una "aplicación" registrada, sino el email y la
contraseña de tu cuenta de usuario de Mobility Labs, enviados en las
cabeceras "email" y "password".

Más adelante este token se usará en otras llamadas para pedir la posición
en tiempo real de los autobuses.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("EMT_EMAIL")
PASSWORD = os.getenv("EMT_PASSWORD")

BASE_URL = "https://openapi.emtmadrid.es/v1"
LOGIN_URL = "https://openapi.emtmadrid.es/v1/mobilitylabs/user/login/"

# Una sola sesión HTTP para todas las llamadas, por el mismo motivo que en
# metro_client.py: requests.get abre una conexión TCP+TLS nueva cada vez y
# el saludo cuesta unos 80ms que aquí no hacen falta. El poller de
# autobuses pregunta cada 10 segundos, así que la conexión se mantiene
# caliente entre refrescos.
_sesion = requests.Session()

# El token dura unas 24h (86399 segundos según la API).
# Le restamos un margen de seguridad de 1 hora para renovarlo antes de que
# caduque realmente, evitando que una petición falle justo en el límite.
MARGEN_SEGURIDAD_SEGUNDOS = 60 * 60

# --- Estado en memoria (caché) ---
# Estas variables viven a nivel de módulo, fuera de cualquier función,
# así que su valor persiste mientras el servidor esté corriendo.
_token_cacheado = None
_token_obtenido_en = None
_cache_paradas = {}

def _token_sigue_siendo_valido():
    """
    Comprueba si el token que tenemos guardado todavía se puede usar,
    es decir, si no tenemos ninguno guardado, o si ya pasó demasiado tiempo.
    """
    if _token_cacheado is None or _token_obtenido_en is None:
        return False

    segundos_transcurridos = time.time() - _token_obtenido_en
    return segundos_transcurridos < (86399 - MARGEN_SEGURIDAD_SEGUNDOS)


def obtener_token():
    """
    Devuelve un token válido para usar contra la API de EMT.

    Si ya tenemos uno guardado en memoria y sigue siendo válido, lo devuelve
    directamente sin hacer ninguna llamada de red. Si no, pide uno nuevo
    haciendo login, lo guarda en memoria, y lo devuelve.
    """
    global _token_cacheado, _token_obtenido_en

    if _token_sigue_siendo_valido():
        return _token_cacheado
    
    if not EMAIL or not PASSWORD:
        raise ValueError(
            "Faltan las credenciales. Revisa que tu archivo .env tenga "
            "EMT_EMAIL y EMT_PASSWORD definidos."
        )

    headers = {
        "email": EMAIL,
        "password": PASSWORD,
    }

    respuesta = _sesion.get(LOGIN_URL, headers=headers)
    respuesta.raise_for_status()

    datos = respuesta.json()

    try:
        token = datos["data"][0]["accessToken"]
    except (KeyError, IndexError):
        print("Respuesta inesperada de la API, revisa el JSON completo:")
        print(datos)
        raise

    # Guardamos el nuevo token y el momento en que lo conseguimos,
    # para que las próximas llamadas a esta función puedan reutilizarlo.
    _token_cacheado = token
    _token_obtenido_en = time.time()

    return token

def _cache_parada_sigue_siendo_valido(stop_id):
    if stop_id not in _cache_paradas:
        return False
    
    datos, momento_guardado = _cache_paradas[stop_id]
    
    segundos_transcurridos = time.time() - momento_guardado
    
    return segundos_transcurridos < 30

def obtener_llegadas_parada(stop_id):
    """
    Consulta qué autobuses se acercan a una parada concreta.

    Parámetros:
        stop_id: el número de la parada (por ejemplo, "72")

    Devuelve la lista de autobuses que se acercan, cada uno con su línea,
    posición (coordenadas), distancia a la parada y tiempo estimado de llegada.
    """
    global _cache_paradas

    if _cache_parada_sigue_siendo_valido(stop_id):
        datos, momento_guardado = _cache_paradas[stop_id]
        return datos

    # Si el caché es válido para esta parada, devolver lo que ya tenemos guardado
    token = obtener_token()
    url = f"{BASE_URL}/transport/busemtmad/stops/{stop_id}/arrives/"
    headers = {"accessToken": token,}

    # Este endpoint requiere un POST con un pequeño cuerpo JSON,
    # aunque no estemos filtrando por una línea concreta.
    cuerpo = {
        "cultureInfo": "ES",
        "Text_StopRequired_YN": "N",
        "Text_EstimationsRequired_YN": "Y",
        "Text_IncidencesRequired_YN": "N",
    }

    respuesta = _sesion.post(url, headers=headers, json=cuerpo)
    respuesta.raise_for_status()
    
    datos = respuesta.json()
    
    _cache_paradas[stop_id] = (datos, time.time())
    
    return datos

if __name__ == "__main__":
    STOP_ID = "72"
    resultado = obtener_llegadas_parada(STOP_ID)