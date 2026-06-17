# Moom — Seguimiento de transporte público de Madrid en tiempo real

Aplicación personal para visualizar en un mapa la posición en tiempo real de los autobuses de la EMT de Madrid. Proyecto educativo en desarrollo, con planes de ampliar a Metro y otros modos de transporte.

## Estado del proyecto

🚧 En desarrollo — Fase 1: conexión básica con la API de EMT Madrid.

## Requisitos

- Python 3.10+
- Una cuenta y aplicación creada en [Mobility Labs Madrid](https://mobilitylabs.emtmadrid.es), con tu `X-ClientId` y `passKey`

## Configuración

1. Clona el repositorio.
2. Copia `.env.example` a un nuevo archivo `.env`:
```bash
   cp .env.example .env
```
3. Rellena `.env` con tus credenciales reales de Mobility Labs.
4. Instala las dependencias (próximamente, cuando añadamos `requirements.txt`).

## Atribución

Este proyecto usa datos de la API de EMT Madrid (Mobility Labs). Según sus condiciones de uso, debe mencionarse a EMT Madrid MobilityLabs como fuente de los datos.

## Roadmap
- [x] Estructura inicial del proyecto
- [x] Conexión y autenticación con la API de EMT
- [x] Obtener posición en tiempo real de una línea de autobús (por parada)
- [ ] Servidor local que expone los datos como JSON
- [ ] Mapa interactivo en el navegador (Leaflet)
- [ ] Persistencia en PostgreSQL
- [ ] Ampliación a Metro y otros modos de transporte