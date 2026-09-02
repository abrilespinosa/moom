"""
Devuelve las tildes a los nombres de las estaciones de Metro.

EL PROBLEMA. El volcado GTFS de Metro escribe en mayúsculas y por el camino ha
perdido las tildes agudas: guarda "GRAN VIA", "ANTON MARTIN" y "MENENDEZ
PELAYO". La ñ y la ü sí las conserva ("ESPAÑA", "ARGÜELLES"), así que lo que
falta es solo el acento. Poner el nombre en minúsculas no lo arregla: de
"GRAN VIA" solo se puede sacar "Gran Via", que sigue estando mal escrito.

Y no hay ninguna fuente de datos limpia. Se comprobó consultando la API del
CRTM en vivo, que es de donde vienen los tiempos: para el andén 4_11 devuelve
{"name": "GRAN VIA"}, exactamente lo mismo. No es que no la hayamos buscado.

CÓMO SE RESUELVE. Se leen los nombres del anexo de Wikipedia, que sí los
escribe bien, y se cruzan con los nuestros IGNORANDO tildes, mayúsculas y
apóstrofos. Un nombre de Wikipedia solo se acepta si, normalizado así, coincide
con una estación nuestra y ADEMÁS es la única grafía con esa forma. O sea que
no se está creyendo a Wikipedia sobre qué estaciones existen —eso lo dice el
GTFS— sino solo sobre dónde lleva tilde una palabra que ya tenemos letra por
letra.

Esa verificación importa: un resumen automático de esta misma página devolvió
estaciones que no existen en Madrid ("Jaume I", que es de Valencia). Leyendo el
wikitexto crudo y exigiendo coincidencia exacta, ese error no puede colarse:
"Jaume I" no casa con ninguna estación nuestra y se descarta solo.

Resultado hoy: 234 de 242 casan, 0 ambiguas. Las 8 restantes son los
intercambiadores ("Intercambiador de Plaza de Castilla", "Puerta del Sol",
"Atocha-Renfe", "Méndez Álvaro Estación Sur"), que en el GTFS ya vienen bien
escritos y no necesitan nada.

Se ejecuta a mano, como el resto de scripts de precálculo:
    python -m scripts.precalcular_nombres_metro
"""

import json
import os
import re
import unicodedata

import requests

from backend.gtfs_loader import DIRECTORIO_PRECALCULADO, cargar_todas_las_paradas

URL_ANEXO = (
    "https://es.wikipedia.org/wiki/"
    "Anexo:Estaciones_del_Metro_de_Madrid?action=raw"
)

# Wikipedia pide un User-Agent que identifique a quien consulta.
CABECERAS = {"User-Agent": "moom/1.0 (proyecto personal; datos de transporte)"}

# [[Destino|Lo que se ve]] o [[Ambas cosas a la vez]].
ENLACE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]")


def normalizar(nombre):
    """
    Deja el nombre en su esqueleto: sin tildes, sin mayúsculas y sin apóstrofos.

    Los apóstrofos se borran en vez de convertirse en espacio por O'Donnell:
    el GTFS lo escribe "ODONNELL", todo junto, y Wikipedia "O'Donnell". Si el
    apóstrofo pasara a espacio, "o donnell" y "odonnell" no casarían.
    """
    sin_apostrofos = nombre.replace("'", "").replace("’", "")
    descompuesto = unicodedata.normalize("NFD", sin_apostrofos.lower())
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", sin_tildes).strip()


def descargar_anexo():
    # requests y no urllib: esta instalación de Python no encuentra el
    # almacén de certificados del sistema y urllib falla con
    # CERTIFICATE_VERIFY_FAILED. requests trae el suyo, y además ya es
    # dependencia del proyecto.
    respuesta = requests.get(URL_ANEXO, headers=CABECERAS, timeout=(5, 30))
    respuesta.raise_for_status()

    return respuesta.text


def grafias_del_anexo(wikitexto):
    """
    Todas las grafías candidatas, agrupadas por su forma normalizada.

    Se cogen TODOS los enlaces y no solo las celdas de la tabla: las filas no
    tienen un formato uniforme y con un patrón estricto se quedaban fuera
    cuatro estaciones (Embajadores, Noviciado, O'Donnell y Plaza de España).
    Coger de más no es peligroso porque después hay que casar exactamente.
    """
    por_forma = {}

    for destino, mostrado in ENLACE.findall(wikitexto):
        visible = (mostrado or destino).strip()

        # Fuera los enlaces internos de Wikipedia (Imagen:, Anexo:...) y los
        # restos de plantilla.
        if not visible or ":" in visible or visible.startswith("link="):
            continue

        por_forma.setdefault(normalizar(visible), set()).add(visible)

    return por_forma


def construir():
    wikitexto = descargar_anexo()
    por_forma = grafias_del_anexo(wikitexto)

    nombres = {}
    sin_casar = []
    ambiguas = []

    for parada in cargar_todas_las_paradas():
        if parada["fuente"] != "METRO":
            continue

        candidatas = por_forma.get(normalizar(parada["nombre"]))

        if not candidatas:
            sin_casar.append(parada["nombre"])
            continue

        if len(candidatas) > 1:
            # Dos grafías distintas con el mismo esqueleto: no hay forma de
            # elegir sin adivinar, así que se deja el nombre como está.
            ambiguas.append((parada["nombre"], sorted(candidatas)))
            continue

        nombres[parada["id"]] = next(iter(candidatas))

    return nombres, sin_casar, ambiguas


if __name__ == "__main__":
    os.makedirs(DIRECTORIO_PRECALCULADO, exist_ok=True)
    nombres, sin_casar, ambiguas = construir()

    ruta = os.path.join(DIRECTORIO_PRECALCULADO, "nombres_metro.json")
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(nombres, archivo, ensure_ascii=False, separators=(",", ":"))

    print(f"{ruta}: {len(nombres)} estaciones")

    con_tilde = sum(
        1
        for n in nombres.values()
        if any(unicodedata.combining(c) for c in unicodedata.normalize("NFD", n))
    )
    print(f"  con alguna tilde: {con_tilde}")

    if ambiguas:
        print(f"  AMBIGUAS ({len(ambiguas)}), se quedan como estaban:")
        for nombre, candidatas in ambiguas:
            print(f"    {nombre}: {candidatas}")

    if sin_casar:
        print(f"  sin casar ({len(sin_casar)}):")
        for nombre in sin_casar:
            print(f"    {nombre}")
