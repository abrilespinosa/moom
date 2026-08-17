# Moom — Seguimiento de transporte público de Madrid en tiempo real

Aplicación para visualizar en un mapa, en tiempo real, el transporte público de Madrid: autobuses urbanos de la EMT, autobuses interurbanos del CRTM y Metro de Madrid. Proyecto personal en desarrollo, inspirado en FlightRadar.

*Moom* viene de **mo**vilidad + **M**adrid.

**▶ Pruébalo: <https://moom-abril-espinosa.vercel.app>**

## Estado del proyecto

Desplegado y funcionando, con las tres redes en tiempo real. En desarrollo activo.

Funciona en móvil, tableta y escritorio, y no necesita instalación ni cuenta.

## Funcionalidades actuales

**Autobuses urbanos (EMT)**
- Autenticación con la API de EMT Madrid (Mobility Labs) mediante email/contraseña, con caché del token en memoria (~24h).
- Próximas llegadas por parada, agrupadas por línea y destino, con caché de 30 segundos para no agotar la cuota diaria.
- Posición de los autobuses que se acercan a la parada seleccionada.

**Autobuses interurbanos (CRTM)**
- Paradas cargadas desde el GTFS del CRTM y visibles en el mapa con su propio icono.
- Próximas llegadas por parada, agrupadas por línea y destino, usando la misma API pública del CRTM que Metro.
- Las llegadas que solo provienen de la tabla de horarios, sin corrección en tiempo real, se marcan como tales para no dar a entender más precisión de la que hay.
- No se muestran los autobuses en el mapa: la API devuelve posiciones, pero están congeladas y no reflejan el movimiento real.

**Metro de Madrid**
- Próximos trenes por estación, agrupados por línea y destino (un bloque por línea y sentido).
- Distintivos con el número y el color oficial de cada línea que pasa por la estación.
- Posición en el mapa de los trenes que se acercan a la estación seleccionada, con el color oficial de cada línea y un tooltip con el sentido.
- Las 242 estaciones resuelven internamente su código de andén, que es el único que entiende la API del CRTM.

**Búsqueda por línea**
- Un único buscador para paradas y líneas: al escribir un número, las líneas aparecen primero y se prioriza la coincidencia exacta (quien busca "27" quiere la línea 27, no la 270).
- Al elegir una línea se ve su recorrido completo, con las paradas en orden y separadas por sentido; desde ahí se salta a las llegadas de cualquiera de ellas.
- Funciona nada más clonar el repositorio: los recorridos vienen precalculados en `backend/data/precalculado/`, así que no hacen falta los archivos GTFS pesados (ver [Datos precalculados](#datos-precalculados)).
- Hay 21 líneas que los datos abiertos no detallan (la F y la G de la EMT, la Línea 3 de Metro y varias interurbanas). Se pueden buscar y abrir igual, avisando de que su recorrido no está disponible; sus paradas y sus tiempos en vivo funcionan con normalidad.

**Favoritos y cercanía**
- Paradas y líneas se pueden marcar como favoritas, y se guardan en el navegador (`localStorage`).
- Con el buscador vacío, la lista muestra los favoritos, filtrados por el modo de transporte activo igual que una búsqueda.
- Al compartir tu ubicación aparece un grupo **Cerca de ti** con las paradas más próximas, y cada una indica a qué distancia está y cuánto se tarda andando. Es una estimación: línea recta más un 25% por el rodeo de las manzanas, y tira ligeramente alto a propósito, porque quedarse corto hace perder el autobús.

**Mapa e interfaz**
- Leaflet con tiles de CartoDB Voyager.
- Paradas visibles a partir de zoom 15 y solo dentro del área en pantalla, para no dibujar miles de marcadores a la vez.
- Filtros por fuente: Todos / Urbano / Interurbano / Metro.
- Botón de geolocalización para centrar el mapa en tu posición.
- Panel lateral redimensionable arrastrando el divisor; el ancho elegido se recuerda entre visitas.
- **En móvil y en tableta vertical** el panel deja de ser una columna y pasa a ser una hoja que sube desde abajo, arrastrable desde la banda naranja, con el mapa a pantalla completa detrás. En tableta horizontal y en escritorio se mantiene la vista de dos paneles, que es donde tiene sentido.
- Refresco automático: cada 10 s para EMT y cada 20 s para Metro, acompasado con el ritmo al que cada API actualiza sus datos. Si un refresco falla, se avisa en el panel en vez de seguir mostrando los tiempos viejos como si fueran actuales.

## Estructura del proyecto

```
backend/
  emt_client.py        # Autenticación EMT y llegadas en tiempo real
  metro_client.py      # API pública del CRTM: estaciones, tiempos y posición de vehículos
  gtfs_loader.py       # Carga de paradas, líneas y colores desde archivos GTFS
  main.py              # Servidor FastAPI y endpoints
  data/
    emt/               # GTFS de EMT (stops.txt, routes.txt)
    crtm/              # GTFS interurbano de CRTM
    metro/             # GTFS de Metro
    precalculado/      # Paradas, líneas y colores ya resueltos, en JSON
frontend/
  index.html           # Estructura de la página
  style.css            # Estilos del mapa y los paneles
  app.js               # Lógica del mapa, búsqueda, favoritos, llegadas y vehículos
  assets/              # Logo e iconos de parada y estación
scripts/
  precalcular_datos.py # Genera backend/data/precalculado/ desde el GTFS crudo
tests/                 # Suite de pytest (32 tests, sin red)
api/index.py           # Punto de entrada del backend en Vercel
vercel.json            # Reparto de rutas entre frontend estático y API
```

## Endpoints

| Endpoint | Descripción |
|---|---|
| `GET /paradas` | Las 13.542 paradas de las tres redes con id, nombre, coordenadas y fuente |
| `GET /parada/{stop_id}` | Próximas llegadas de autobús. Para EMT devuelve el JSON de su API; para ids `par_` (interurbano) devuelve las llegadas agrupadas por línea y destino |
| `GET /lineas` | Las 603 líneas de las tres redes, sin recorrido, para el buscador |
| `GET /linea/{id}` | Una línea con sus paradas en orden, separadas por sentido (ej. `EMT-027`) |
| `GET /metro/parada/{cod_stop}` | Próximos trenes en una estación, agrupados por línea y destino |
| `GET /metro/parada/{cod_stop}/lineas` | Solo las líneas de una estación; la mitad barata del anterior, para el mapa |
| `GET /metro/linea/{cod_line}/vehiculos` | Posición de los trenes de una línea. Acepta `?cod_stop=est_XXX` para obtener los cercanos a una estación concreta |
| `GET /metro/lineas/colores` | Colores oficiales de las líneas de Metro; el frontend lo pide una vez al arrancar |

Cuando una API externa no responde, los endpoints que dependen de ella devuelven `503` con un mensaje, en vez de un error genérico.

## Datos precalculados

`backend/data/` ocupa 188 MB en disco, pero al repositorio solo van `stops.txt` y `routes.txt` de cada fuente. Los archivos pesados —`stop_times.txt` son 1,9 millones de filas— están excluidos.

Eso dejaba un problema: la búsqueda por línea los necesitaba, así que un clon limpio se quedaba sin ella. La clave es que esos 188 MB se leen al arrancar y se tiran: de todos esos viajes solo sobrevive **uno representativo por línea y sentido**. El resultado son 2 MB, que sí caben en el repositorio.

Por eso `backend/data/precalculado/` va versionado. Se regenera con:

```bash
python -m scripts.precalcular_datos
```

**Hay que volver a ejecutarlo cada vez que se descargue un volcado GTFS nuevo**, o la aplicación seguirá sirviendo los datos del anterior. De paso, el arranque baja de 2,77 s a 0,03 s.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

32 tests en menos de medio segundo. **Ninguno sale a la red**: solo se prueban rutas que responden desde memoria o que cortan antes de llamar a EMT o al CRTM, comprobado ejecutándolos con las conexiones salientes bloqueadas. Una caída de una API externa no puede poner la suite en rojo.

Cubren la lógica pura (agrupación de llegadas, distinción entre tiempo real y horario teórico, filtrado de líneas que no son de Metro, validación de identificadores) y varios invariantes de los datos, que es donde más duelen los fallos de este proyecto: un volcado GTFS nuevo puede romperlos en silencio y no se nota hasta que una estación desaparece del mapa.

Se ejecutan también en GitHub Actions en cada push.

## Despliegue

Está desplegado en Vercel: el frontend como archivos estáticos y FastAPI como función, montada bajo `/api`. Al compartir dominio, en producción no hace falta CORS.

La pieza que hay que respetar es `.vercelignore`: sin él, el despliegue se lleva los 188 MB de GTFS crudo. Ojo a que se aplica al build estático **pero no al paquete de la función**, que necesita además `excludeFiles` en `vercel.json` para lo mismo.

## Requisitos

- Python 3.10 o superior (el despliegue usa 3.14)
- Una cuenta en [Mobility Labs Madrid](https://mobilitylabs.emtmadrid.es) con tu email y contraseña registrados (solo necesaria para los autobuses de EMT; Metro y CRTM usan una API pública sin autenticación)

## Configuración

1. Clona el repositorio y entra en la carpeta:
   ```bash
   git clone https://github.com/abrilespinosa/moom.git
   cd moom
   ```
2. Crea y activa un entorno virtual **en la raíz del proyecto**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Copia `.env.example` a `.env` y rellénalo con tus credenciales de Mobility Labs:
   ```bash
   cp .env.example .env
   ```

## Cómo arrancarlo

Hacen falta **dos terminales**, una para el backend y otra para el frontend.

Terminal 1 — backend, desde la raíz del proyecto:
```bash
source venv/bin/activate
uvicorn backend.main:app --reload
```

Terminal 2 — frontend, desde la carpeta `frontend/`:
```bash
cd frontend
python3 -m http.server 5500
```

Abre <http://localhost:5500> en el navegador.

> **Importante:** el frontend tiene que servirse por HTTP. Abrir `frontend/index.html` directamente con doble clic (`file://`) no funciona: bloquea la geolocalización y cambia el comportamiento de `fetch`.
>
> El backend hay que arrancarlo **desde la raíz del proyecto**, no desde dentro de `backend/`: `main.py` importa con rutas tipo `from backend.emt_client import ...` y los archivos GTFS se abren con rutas relativas al directorio de trabajo.

## Atribución

Este proyecto usa datos de la API de EMT Madrid (Mobility Labs). Según sus condiciones de uso, debe mencionarse a EMT Madrid MobilityLabs como fuente de los datos.

Los datos de Metro e interurbanos proceden del Consorcio Regional de Transportes de Madrid (CRTM).

## Licencia

El **código** de este repositorio se publica bajo licencia [MIT](LICENSE).

Los **datos** no lo están. Los archivos GTFS de `backend/data/` pertenecen a la EMT de Madrid y al CRTM, y se rigen por las condiciones de uso de sus respectivos portales de datos abiertos; aquí se incluyen únicamente para que el proyecto funcione al clonarlo. Lo mismo aplica a los datos que devuelven sus APIs en tiempo real.

Una nota sobre esas APIs: la de EMT es oficial y está documentada. La del CRTM (`crtm.es/widgets/api`) es la que alimenta los widgets de su propia web — es pública y no requiere autenticación, pero no está documentada ni tiene condiciones de uso publicadas. El proyecto la usa con moderación (cachés en memoria e intervalos de sondeo ajustados al ritmo real al que cambian los datos), pero conviene saber que no hay garantía de estabilidad.

## Notas

Los archivos GTFS pesados (`shapes.txt`, `stop_times.txt`, `trips.txt`, `calendar*.txt`) están excluidos del repositorio: solo se versionan `stops.txt` y `routes.txt` de cada fuente. Un clon limpio funciona igual, incluida la búsqueda por línea, gracias a los [datos precalculados](#datos-precalculados); solo hacen falta los archivos pesados para **regenerarlos** tras descargar un volcado nuevo de los portales de EMT y CRTM.

Los GTFS publicados por EMT y CRTM no incluyen ningún viaje de 21 de sus líneas (entre ellas la F y la G de la EMT y la Línea 3 de Metro), así que de esas no se puede mostrar el recorrido. Sus paradas y sus tiempos en vivo funcionan con normalidad.
