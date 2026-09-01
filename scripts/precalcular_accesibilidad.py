"""
Precalcula qué estaciones de Metro son accesibles, y en qué grado.

    python -m scripts.precalcular_accesibilidad

POR QUÉ ESTA LISTA ESTÁ ESCRITA A MANO, y no sacada de los datos abiertos:
porque los datos abiertos no lo dicen. Se comprobaron tres fuentes y ninguna
sirve.

1. El campo `wheelchair_boarding` del GTFS **nunca vale "sí"**. Separando
   andenes de estaciones, NINGUNA de las 240 estaciones de Metro figura como
   accesible: 113 salen como "sin información" y 127 como "no accesible". En el
   GTFS interurbano no hay un solo "1" en 8.406 paradas. Un campo que jamás
   afirma nada no está relleno, solo lo parece.
2. El portal de datos del CRTM no publica ningún conjunto de accesibilidad
   (se buscó "accesibilidad", "ascensores", "movilidad reducida", "accesible").
3. La API en vivo SÍ trae un campo `access` con tres valores (1, 0, -1, 2),
   pero no se pudo decodificar: da 2 tanto en Pinar de Chamartín, que es
   universalmente accesible, como en Lavapiés, que solo tiene ascensor; y da 0
   en Tribunal, que también es universalmente accesible. No corresponde a las
   categorías reales.

Así que la fuente es la clasificación oficial de Metro de Madrid, en sus tres
categorías, tal como la publican ellos:

    https://www.metromadrid.es/es/accesibilidad#panel2

Es un dato ESTABLE —las obras de accesibilidad tardan años— pero NO ETERNO: cuando Metro habilite estaciones nuevas hay que actualizarla aquí.
Ese es el precio de tenerla, y es preferible a publicar un dato inventado sobre
algo en lo que equivocarse deja a alguien tirado en una estación sin salida.
"""

import json
import os
import re
import unicodedata

from backend.gtfs_loader import DIRECTORIO_PRECALCULADO, cargar_todas_las_paradas

# --- La clasificación oficial de Metro de Madrid ---------------------------

# Ascensores y/o rampas MÁS medidas complementarias (encaminamientos, avisos
# sonoros, contraste...). Es el grado bueno de verdad.
UNIVERSAL = """
Pinar de Chamartín|Chamartín|Plaza de Castilla|Cuatro Caminos|Bilbao|Tribunal|
Gran Vía|Sol|Atocha|Menéndez Pelayo|Pacífico|Portazgo|Goya|
Príncipe de Vergara|Sevilla|Ópera|Canal|Moncloa|Argüelles|Plaza de España|
Callao|Legazpi|Mar de Cristal|Pueblo Nuevo|Aluche|Casa de Campo|
Plaza Elíptica|Conde de Casal|Nuevos Ministerios|Príncipe Pío|
Barrio de la Concepción|Gregorio Marañón|Arroyofresno|Aeropuerto T1-T2-T3|
Paco de Lucía|Pavones|Lago|Batán|Colonia Jardín|Puerta del Sur
"""

# Medidas complementarias pero SIN ascensor ni rampa: para quien va en silla,
# esto no es accesible.
SOLO_MEDIDAS = """
San Blas|Duque de Pastrana
"""

# Ascensor y/o rampa pero sin medidas complementarias: se puede entrar y salir
# en silla, pero le falta el resto.
SOLO_ASCENSOR = """
Bambú|Iglesia|Alto del Arenal|Miguel Hernández|Sierra de Guadalupe|
Villa de Vallecas|Congosto|La Gavia|Las Suertes|Valdecarros|Las Rosas|
Avenida de Guadalajara|Alsacia|La Almudena|La Elipa|Ventura Rodríguez|
Lavapiés|Embajadores|Palos de la Frontera|Delicias|Villaverde Alto|
San Cristóbal|Villaverde Bajo-Cruce|Ciudad de los Ángeles|San Fermín-Orcasur|
Hospital 12 de Octubre|Almendrales|Hortaleza|Manoteras|Canillas|San Lorenzo|
Parque de Santa María|Alameda de Osuna|El Capricho|Pirámides|
Eugenia de Montijo|Empalme|Sainz de Baranda|Lucero|Laguna|Carpetana|Usera|
Arganzuela-Planetario|Guzmán el Bueno|Ciudad Universitaria|
Hospital de Henares|Henares|Jarama|San Fernando|La Rambla|Coslada Central|
Barrio del Puerto|Estadio Metropolitano|Alonso Cano|Islas Filipinas|
Francos Rodríguez|Valdezarza|Antonio Machado|Peñagrande|
Avenida de la Ilustración|Lacoma|Pitis|Colombia|Pinar del Rey|Feria de Madrid|
Barajas|Aeropuerto T4|Arganda del Rey|La Poveda|Rivas-Vaciamadrid|
Rivas Futura|Rivas-Urbanizaciones|Puerta de Arganda|San Cipriano|Vicálvaro|
Valdebernardo|Mirasierra|Hospital Infanta Sofía|Reyes Católicos|Baunatal|
Manuel de Falla|Marqués de la Valdavia|La Moraleja|La Granja|
Ronda de la Comunicación|Las Tablas|Montecarmelo|Tres Olivos|
Aviación Española|Cuatro Vientos|Joaquín Vilumbrales|Abrantes|Pan Bendito|
San Francisco|Carabanchel Alto|La Peseta|La Fortuna|Parque Lisboa|
Alcorcón Central|Parque Oeste|Universidad Rey Juan Carlos|Móstoles Central|
Pradillo|Hospital de Móstoles|Manuela Malasaña|Loranca|
Hospital de Fuenlabrada|Parque Europa|Fuenlabrada Central|
Parque de los Estados|Arroyo Culebro|Conservatorio|Alonso de Mendoza|
Getafe Central|Juan de la Cierva|El Casar|Los Espartales|El Bercial|
El Carrascal|Julián Besteiro|Casa del Reloj|Hospital Severo Ochoa|
Leganés Central|San Nicasio
"""

# El GTFS llama a algunas estaciones de otra forma que la lista de Metro. Son
# justo los grandes intercambiadores, o sea las más importantes de la red: sin
# esto se quedarían sin marcar precisamente las que más gente usa.
ALIAS = {
    "SOL": "Puerta del Sol",
    "ATOCHA": "Atocha-Renfe",
    "MONCLOA": "Intercambiador de Moncloa",
    "PLAZADECASTILLA": "Intercambiador de Plaza de Castilla",
    "PLAZAELIPTICA": "Intercambiador de Plaza Elíptica",
    "PRINCIPEPIO": "Intercambiador de Príncipe Pío",
    "HOSPITALDEHENARES": "Hospital del Henares",
}


def normalizar(nombre):
    """
    Deja el nombre en solo letras y números, sin tildes ni mayúsculas.

    Hace falta porque el volcado mezcla estilos: hay estaciones en mayúsculas
    ("HENARES") y otras en capitalizado ("Puerta del Sol"), con y sin tildes.
    """
    sin_tildes = (
        unicodedata.normalize("NFD", nombre).encode("ascii", "ignore").decode()
    )
    return re.sub(r"[^A-Z0-9]", "", sin_tildes.upper())


def _nombres(bloque):
    return [n.strip() for n in bloque.replace("\n", "").split("|") if n.strip()]


def construir():
    paradas = cargar_todas_las_paradas()
    metro = {
        normalizar(p["nombre"]): p["id"] for p in paradas if p["fuente"] == "METRO"
    }

    accesibilidad = {}
    sin_casar = []

    for grado, bloque in (
        ("universal", UNIVERSAL),
        ("solo_medidas", SOLO_MEDIDAS),
        ("solo_ascensor", SOLO_ASCENSOR),
    ):
        for nombre in _nombres(bloque):
            clave = normalizar(nombre)
            clave = normalizar(ALIAS.get(clave, nombre))

            id_estacion = metro.get(clave)

            if id_estacion is None:
                sin_casar.append(nombre)
                continue

            accesibilidad[id_estacion] = grado

    return accesibilidad, sin_casar


if __name__ == "__main__":
    os.makedirs(DIRECTORIO_PRECALCULADO, exist_ok=True)
    accesibilidad, sin_casar = construir()

    ruta = os.path.join(DIRECTORIO_PRECALCULADO, "accesibilidad.json")
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(accesibilidad, archivo, ensure_ascii=False, separators=(",", ":"))

    print(f"{ruta}: {len(accesibilidad)} estaciones")

    for grado in ("universal", "solo_ascensor", "solo_medidas"):
        n = sum(1 for g in accesibilidad.values() if g == grado)
        print(f"  {grado:14} {n}")

    if sin_casar:
        # Si esto sale, es que un nombre de la lista no existe en el volcado:
        # o Metro lo ha renombrado, o hace falta un alias. Cualquiera de las
        # dos cosas deja una estación sin marcar, así que hay que mirarlo.
        print(f"  SIN CASAR ({len(sin_casar)}): {', '.join(sin_casar)}")
