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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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

# --- REINTENTOS ---
# El login de EMT falla el saludo TLS con mucha frecuencia. Medido lanzando
# 12 logins seguidos, cada uno con una sesión nueva: 4 fallaron con
# SSLError("EOF occurred in violation of protocol"). Un tercio. Y no es cosa
# del alojamiento: sale igual desde una máquina de casa.
#
# Nunca se había notado porque con un servidor de toda la vida el login
# ocurre UNA vez y el token vale 23h; si esa única vez sale bien, no vuelves
# a mirar. Desplegado en funciones, cada instancia fría hace su propio
# login, así que ese tercio se convierte en autobuses que no aparecen justo
# cuando alguien abre el enlace después de un rato sin tráfico.
#
# Con estos reintentos, los mismos 12 logins salieron 12/12. Y sale casi
# gratis: el fallo de TLS se produce al instante, no agotando el tiempo de
# espera, así que la mediana se quedó en 0,16s y el peor caso en 0,36s.
#
# Se permite reintentar también POST, que por defecto urllib3 excluye por si
# la petición modifica algo. Aquí no: la única llamada POST pide las
# llegadas de una parada, o sea que es una consulta y repetirla no cambia
# nada en el servidor.
_reintentos = Retry(
    total=3,
    connect=3,  # el saludo TLS fallido cae aquí, y falla rápido
    read=1,  # una relectura como mucho: cada una puede costar 15s
    status=2,
    backoff_factor=0.4,
    status_forcelist=(502, 503, 504),
    allowed_methods=frozenset({"GET", "POST"}),
)
_sesion.mount("https://", HTTPAdapter(max_retries=_reintentos))

# (conectar, leer) en segundos, por el mismo motivo que en metro_client.py:
# sin timeout, una conexión colgada retiene un hilo del pool de FastAPI para
# siempre. Aquí el margen de lectura es más holgado porque el login de EMT
# es la llamada más lenta de la aplicación y solo ocurre una vez al día:
# que caduque por impaciencia dejaría sin autobuses toda la sesión.
TIMEOUT_SEGUNDOS = (5, 15)

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

# Tope de entradas de _cache_paradas, por el mismo motivo y con la misma
# política tosca que en metro_client.py: guarda una entrada por parada
# consultada y no se podaba nunca, así que en un proceso de larga vida crece
# sin techo (hay 4.894 paradas de EMT que alcanzar). En Vercel da igual
# porque las instancias se reciclan, pero un uvicorn de días sí lo acumula.
#
# Aquí las entradas caducan a los 30s, así que las viejas ya no se devuelven;
# lo que sobra es la memoria que ocupan, no el riesgo de servir algo rancio.
MAXIMO_ENTRADAS_CACHE = 500


def _guardar_en_cache(cache, clave, valor):
    """
    Guarda una entrada sin dejar que el diccionario crezca sin límite.

    Desaloja la más antigua por orden de inserción: los diccionarios de
    Python lo conservan, y reasignar una clave existente no la mueve al
    final.
    """
    if clave not in cache and len(cache) >= MAXIMO_ENTRADAS_CACHE:
        del cache[next(iter(cache))]

    cache[clave] = valor

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

    respuesta = _sesion.get(LOGIN_URL, headers=headers, timeout=TIMEOUT_SEGUNDOS)
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
        # Sí, que las manden. Vienen en la MISMA respuesta que las llegadas
        # (data[0].Incident), así que no cuesta una petición más. Estaban
        # apagadas desde el principio, y para quien espera en la parada un
        # desvío de su línea importa más que el minuto que falta.
        "Text_IncidencesRequired_YN": "Y",
    }

    respuesta = _sesion.post(
        url, headers=headers, json=cuerpo, timeout=TIMEOUT_SEGUNDOS
    )
    respuesta.raise_for_status()
    
    datos = respuesta.json()
    
    _guardar_en_cache(_cache_paradas, stop_id, (datos, time.time()))

    return datos

def incidencias_de(respuesta_de_llegadas):
    """
    Saca las incidencias de una respuesta de llegadas, o [] si no trae.

    OJO, y es lo que decide cómo se pueden enseñar: NO vienen filtradas por
    parada. Preguntando por la parada 72 devuelve 21 incidencias de TODA la
    red de EMT, la mayoría ya pasadas. Sin filtrar por fecha, cada parada
    mostraría dos docenas de avisos que no aplican, que es peor que no tener
    la función.
    """
    try:
        return respuesta_de_llegadas["data"][0]["Incident"]["ListaIncident"]["data"]
    except (KeyError, IndexError, TypeError):
        # Cuando no hay ninguna, la API no devuelve la lista vacía: devuelve
        # otra forma. Que falte no es un error.
        return []


if __name__ == "__main__":
    STOP_ID = "72"
    resultado = obtener_llegadas_parada(STOP_ID)