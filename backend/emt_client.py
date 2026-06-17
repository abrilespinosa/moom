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
import requests
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("EMT_EMAIL")
PASSWORD = os.getenv("EMT_PASSWORD")

LOGIN_URL = "https://openapi.emtmadrid.es/v1/mobilitylabs/user/login/"


def obtener_token():
    """
    Hace login contra la API de EMT y devuelve el accessToken si todo va bien.
    Si algo falla, lanza un error explicando qué pasó.
    """
    if not EMAIL or not PASSWORD:
        raise ValueError(
            "Faltan las credenciales. Revisa que tu archivo .env tenga "
            "EMT_EMAIL y EMT_PASSWORD definidos."
        )

    headers = {
        "email": EMAIL,
        "password": PASSWORD,
    }

    respuesta = requests.get(LOGIN_URL, headers=headers)
    respuesta.raise_for_status()

    datos = respuesta.json()

    try:
        token = datos["data"][0]["accessToken"]
    except (KeyError, IndexError):
        print("Respuesta inesperada de la API, revisa el JSON completo:")
        print(datos)
        raise

    return token


if __name__ == "__main__":
    token = obtener_token()
    print("Conexión exitosa. Token obtenido:")
    print(token)