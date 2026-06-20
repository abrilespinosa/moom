# Moom — Seguimiento de transporte público de Madrid en tiempo real

Aplicación personal para visualizar en un mapa la posición en tiempo real de los autobuses de la EMT de Madrid. Proyecto educativo en desarrollo, inspirado en FlightRadar, con planes de ampliar a Metro, interurbanos (CRTM) y otros modos de transporte.

## Estado del proyecto

🚧 En desarrollo — Backend funcional con datos de EMT urbana + frontend con mapa interactivo.

## Funcionalidades actuales

- **Autenticación con la API de EMT Madrid** (Mobility Labs) mediante email/contraseña, con caché del token en memoria (~24h).
- **Datos GTFS de EMT** cargados en memoria al arrancar el servidor (paradas, rutas).
- **API local con FastAPI**:
  - `GET /paradas` — devuelve todas las paradas disponibles.
  - `GET /parada/{stop_id}` — devuelve las próximas llegadas de autobuses a una parada concreta.
- **Caché de llegadas** con TTL de 30 segundos por parada, para no agotar la cuota diaria de la API de EMT.
- **Mapa interactivo** (Leaflet + tiles de CartoDB Voyager) con:
  - Paradas visibles a partir de cierto nivel de zoom, para no saturar el mapa.
  - Búsqueda de paradas por nombre o ID.
  - Selección de parada (clic en mapa o desde el buscador), resaltada en el mapa.
  - Panel de llegadas agrupadas por línea + destino, con tiempo más próximo destacado.
  - Actualización automática cada 10 segundos.

## Estructura del proyecto

```
backend/
  emt_client.py       # Autenticación EMT y consulta de llegadas en tiempo real
  gtfs_loader.py       # Carga de paradas desde archivos GTFS
  main.py              # Servidor FastAPI y endpoints
  data/
    emt/                # GTFS de EMT (stops.txt, routes.txt)
frontend/
  index.html           # Estructura de la página
  style.css            # Estilos del mapa y los paneles
  app.js                # Lógica del mapa, búsqueda y llegadas
```

## Requisitos

- Python 3.10+
- Una cuenta en [Mobility Labs Madrid](https://mobilitylabs.emtmadrid.es) con tu email y contraseña registrados

## Configuración

1. Clona el repositorio.
2. Copia `.env.example` a un nuevo archivo `.env`:
   ```bash
   cp .env.example .env
   ```
3. Rellena `.env` con tu `EMT_EMAIL` y `EMT_PASSWORD` reales de Mobility Labs.
4. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
5. Arranca el servidor backend desde la raíz del proyecto:
   ```bash
   uvicorn backend.main:app --reload
   ```
6. Abre `frontend/index.html` en el navegador.

## Atribución

Este proyecto usa datos de la API de EMT Madrid (Mobility Labs). Según sus condiciones de uso, debe mencionarse a EMT Madrid MobilityLabs como fuente de los datos.

## Roadmap

- [x] Estructura inicial del proyecto
- [x] Conexión y autenticación con la API de EMT
- [x] Obtener posición en tiempo real de una línea de autobús (por parada)
- [x] Servidor local que expone los datos como JSON (FastAPI)
- [x] Mapa interactivo en el navegador (Leaflet)
- [x] Panel de búsqueda de paradas y llegadas agrupadas por línea/destino
- [ ] Integrar líneas interurbanas de CRTM (en progreso en rama `feature/crtm-interurbanos`, pendiente de mergear)
- [ ] Diferenciar visualmente paradas EMT vs. CRTM en el mapa
- [ ] Manejar correctamente IDs de parada de CRTM en `/parada/{stop_id}`
- [ ] Combinar varias paradas para ver más autobuses simultáneamente
- [ ] Servir el frontend con un servidor local en vez de abrirlo como archivo
- [ ] Persistencia en PostgreSQL
- [ ] Despliegue
- [ ] Ampliación a Metro de Madrid y otros modos de transporte
- [ ] Investigar acceso a tiempo real de interurbanos (sin API pública confirmada por ahora)