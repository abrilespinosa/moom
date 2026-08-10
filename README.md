# Moom — Seguimiento de transporte público de Madrid en tiempo real

Aplicación para visualizar en un mapa, en tiempo real, el transporte público de Madrid: autobuses urbanos de la EMT, autobuses interurbanos del CRTM y Metro de Madrid. Proyecto personal en desarrollo, inspirado en FlightRadar.

*Moom* viene de **mo**vilidad + **M**adrid.

## Estado del proyecto

🚧 En desarrollo — Backend funcional con datos de EMT, CRTM y Metro, y frontend con mapa interactivo.

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
- Próximos trenes por estación, agrupados por destino (un bloque por sentido).
- Posición en el mapa de los trenes que se acercan a la estación seleccionada, con el color oficial de cada línea y un tooltip con el sentido.
- Las 240 estaciones resuelven internamente su código de andén, que es el único que entiende la API del CRTM.

**Mapa**
- Leaflet con tiles de CartoDB Voyager.
- Paradas visibles a partir de zoom 15 y solo dentro del área en pantalla, para no dibujar miles de marcadores a la vez.
- Filtros por fuente: Todos / Urbano / Interurbano / Metro.
- Búsqueda de paradas por nombre o ID.
- Botón de geolocalización para centrar el mapa en tu posición.
- Refresco automático: cada 10 s para EMT y cada 20 s para Metro, acompasado con el ritmo al que cada API actualiza sus datos.

## Estructura del proyecto

```
backend/
  emt_client.py        # Autenticación EMT y llegadas en tiempo real
  metro_client.py      # API pública del CRTM: estaciones, tiempos y posición de trenes
  gtfs_loader.py       # Carga de paradas y colores de línea desde archivos GTFS
  main.py              # Servidor FastAPI y endpoints
  data/
    emt/               # GTFS de EMT (stops.txt, routes.txt)
    crtm/              # GTFS interurbano de CRTM
    metro/             # GTFS de Metro
frontend/
  index.html           # Estructura de la página
  style.css            # Estilos del mapa y los paneles
  app.js               # Lógica del mapa, búsqueda, llegadas y trenes
  assets/              # Iconos de parada y estación
```

## Endpoints

| Endpoint | Descripción |
|---|---|
| `GET /paradas` | Todas las paradas (EMT + CRTM + Metro) con id, nombre, coordenadas y fuente |
| `GET /parada/{stop_id}` | Próximas llegadas de autobús. Para EMT devuelve el JSON de su API; para ids `par_` (interurbano) devuelve las llegadas agrupadas por línea y destino |
| `GET /metro/parada/{cod_stop}` | Próximos trenes en una estación, agrupados por destino |
| `GET /metro/linea/{cod_line}/vehiculos` | Posición de los trenes de una línea. Acepta `?cod_stop=est_XXX` para obtener los cercanos a una estación concreta |

## Requisitos

- Python 3.10+
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

## Roadmap

- [x] Estructura inicial del proyecto
- [x] Conexión y autenticación con la API de EMT
- [x] Posición en tiempo real de los autobuses por parada
- [x] Servidor local que expone los datos como JSON (FastAPI)
- [x] Mapa interactivo en el navegador (Leaflet)
- [x] Panel de búsqueda de paradas y llegadas agrupadas por línea/destino
- [x] Integrar paradas interurbanas de CRTM
- [x] Diferenciar visualmente paradas EMT, CRTM y Metro en el mapa
- [x] Integrar Metro: estaciones, panel de llegadas y trenes en el mapa
- [x] Servir el frontend con un servidor local en vez de abrirlo como archivo
- [ ] Chips con el color de cada línea en la cabecera de estación
- [ ] Reducir el ruido visual cuando se solapan muchos marcadores
- [ ] Combinar varias paradas para ver más vehículos simultáneamente
- [ ] Búsqueda y navegación por línea (requiere los GTFS completos: `trips.txt`, `stop_times.txt`)
- [x] Tiempo real de autobuses interurbanos
- [ ] Persistencia en PostgreSQL
- [ ] Despliegue

## Notas

Los archivos GTFS pesados (`shapes.txt`, `stop_times.txt`, `trips.txt`, `calendar*.txt`) están excluidos del repositorio. Solo se versionan `stops.txt` y `routes.txt` de cada fuente. Si alguna funcionalidad futura los necesita, hay que volver a descargarlos de los portales de EMT y CRTM.
