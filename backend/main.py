"""
main.py

Servidor web (API) que expone los datos de EMT Madrid en una URL local,
para que el futuro frontend (mapa en el navegador) pueda consultarlos.

Cómo arrancarlo (desde la raíz del proyecto, en terminal):
    uvicorn backend.main:app --reload

Luego puedes visitar en el navegador, por ejemplo:
    http://127.0.0.1:8000/parada/72
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.emt_client import obtener_llegadas_parada
from backend.gtfs_loader import cargar_todas_las_paradas

# Esta variable "app" es el corazón de FastAPI: representa nuestro servidor.
# Uvicorn (el programa que lo ejecuta) busca específicamente una variable
# llamada "app" en este archivo.
app = FastAPI(title="Moom API")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En desarrollo, permitimos cualquier origen
    allow_methods=["*"],
    allow_headers=["*"],
)

PARADAS = cargar_todas_las_paradas()

@app.get("/paradas")
def listar_paradas():
    """
    Devuelve todas las paradas de la red EMT (id, nombre, lat, lon).
    """
    return PARADAS

@app.get("/")
def inicio():
    """
    Ruta raíz, solo para confirmar que el servidor está vivo.
    Visitar http://127.0.0.1:8000/ debería mostrar este mensaje.
    """
    return {"mensaje": "Moom API funcionando. Prueba /parada/{numero_de_parada}"}


@app.get("/parada/{stop_id}")
def llegadas_parada(stop_id: str):
    """
    Devuelve los autobuses que se acercan a la parada indicada.

    Ejemplo de uso: GET /parada/72
    """
    return obtener_llegadas_parada(stop_id)