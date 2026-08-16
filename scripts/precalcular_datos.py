"""
Precalcula a JSON lo único que la aplicación necesita del GTFS en caliente.

Por qué existe: backend/data/ ocupa 188 MB en disco, pero al repositorio solo
van stops.txt y routes.txt (2 MB). Los archivos pesados (trips.txt y
stop_times.txt, 1,9 M de filas) están en .gitignore, así que un clon limpio
—o cualquier despliegue— se queda sin búsqueda por línea.

La clave es que esos 188 MB se leen al arrancar y se tiran: de stop_times.txt
solo sobrevive UN viaje representativo por línea y sentido. El resultado son
2,2 MB, que sí caben en el repositorio y en un despliegue.

Uso (desde la raíz del proyecto, como todo lo que importa gtfs_loader):

    python -m scripts.precalcular_datos

Hay que volver a ejecutarlo cada vez que se descargue un volcado GTFS nuevo;
si no, la aplicación seguirá sirviendo los datos del volcado anterior.
"""

import json
import os

from backend.gtfs_loader import (
    DIRECTORIO_PRECALCULADO,
    _lineas_desde_gtfs,
    _paradas_desde_gtfs,
    _colores_metro_desde_gtfs,
)


def _escribir(nombre, datos):
    """
    Guarda `datos` como JSON y devuelve un resumen para imprimir.

    ensure_ascii=False mantiene los acentos legibles en el archivo (que se
    versiona, así que se lee en los diff) y además ocupa menos que los
    escapes \\uXXXX. Sin separators, json.dumps mete un espacio tras cada
    coma: son ~29.000 ids de parada, así que se nota.
    """
    ruta = os.path.join(DIRECTORIO_PRECALCULADO, nombre)

    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, separators=(",", ":"))

    return f"{ruta}: {len(datos)} elementos, {os.path.getsize(ruta) / 1e6:.2f} MB"


if __name__ == "__main__":
    os.makedirs(DIRECTORIO_PRECALCULADO, exist_ok=True)

    # Se leen desde el GTFS crudo a propósito, saltándose la versión
    # precalculada: si no, ejecutar el script dos veces seguidas se limitaría
    # a copiar su propia salida y un volcado nuevo no llegaría a entrar.
    print(_escribir("paradas.json", _paradas_desde_gtfs()))

    lineas = _lineas_desde_gtfs()
    print(_escribir("lineas.json", lineas))

    # Los colores de línea de Metro son el tercer dato estático que la
    # aplicación necesita en caliente, y sin él reventaba en producción:
    # cargar_colores_lineas_metro() abría routes.txt, que no se despliega.
    print(_escribir("colores_metro.json", _colores_metro_desde_gtfs()))

    sin_recorrido = sum(1 for linea in lineas if not linea["sentidos"])
    if sin_recorrido:
        # No es un fallo: son las líneas que no aparecen en trips.txt y se
        # publican igual, con "sentidos" vacío. Se avisa porque un salto
        # grande respecto a las 21 conocidas delata un volcado incompleto.
        print(f"Aviso: {sin_recorrido} líneas sin recorrido (conocidas: 21).")
