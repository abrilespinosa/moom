"""
Punto de entrada del backend en Vercel.

Vercel convierte cada archivo de api/ en una función serverless y busca en
él una variable llamada "app" que hable ASGI, que es justo lo que es una
aplicación de FastAPI.

Por qué se monta en vez de exportar backend.main.app directamente: en
Vercel el frontend y el backend comparten dominio, así que hay que repartir
las rutas entre los dos. La raíz "/" tiene que servir el index.html del
mapa, y si el backend estuviera colgado también de "/" chocaría con él.
Montándolo bajo /api, todas sus rutas quedan desplazadas (/api/paradas,
/api/metro/parada/...) sin tocar ni un decorador de main.py.

El reparto de rutas propiamente dicho está en vercel.json.
"""

from fastapi import FastAPI

from backend.main import app as api_moom

app = FastAPI()
app.mount("/api", api_moom)
