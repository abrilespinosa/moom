# Moom — Seguimiento de transporte público de Madrid en tiempo real

Aplicación para visualizar en un mapa, en tiempo real, el transporte público de Madrid: autobuses urbanos de la EMT, autobuses interurbanos del CRTM y Metro de Madrid. Proyecto personal en desarrollo, inspirado en FlightRadar.

*Moom* viene de **mo**vilidad + **M**adrid.

**▶ Pruébalo: <https://moom-abril-espinosa.vercel.app>**

## Estado del proyecto

Desplegado y funcionando, con las tres redes en tiempo real. En desarrollo activo.

Funciona en móvil, tableta y escritorio, y no necesita instalación ni cuenta.

## Qué hace

**Las tres redes en un mapa y un buscador.** Los canales oficiales las tienen
separadas: EMT, Metro y CRTM tienen cada uno su aplicación y su propio sistema
de identificadores.

- **Llegadas en tiempo real** por parada en las tres redes, agrupadas por línea
  y destino.
- **Vehículos en el mapa**: autobuses de la EMT y trenes de Metro, con el color
  oficial de cada línea.
- **Buscador único** de paradas y líneas, con filtros por red. Al escribir un
  número las líneas van primero: quien busca «27» quiere la línea 27, no la 270.
- **Recorrido de una línea** por sentido, y desde ahí a las llegadas de
  cualquiera de sus paradas.
- **Horarios de paso**, con la salvedad de abajo.
- **Favoritos, recientes y «Cerca de ti»**, con distancia y tiempo andando.
- **Avisos de servicio de la EMT**, con el estado de cada uno.
- **Planos oficiales y tarifas**, en «Planos y tarifas».
- **Cada vista tiene su dirección** (`#/parada/72`), así que una parada se
  puede guardar en marcadores o en la pantalla de inicio y compartir.
- **Se instala y abre sin conexión**: la interfaz se guarda en el dispositivo.
  Los tiempos necesitan red, y no se enseñan llegadas viejas sin decir de cuándo
  son.

### Lo que no se inventa

Buena parte del trabajo está en no aparentar más precisión de la que dan los
datos:

- **Interurbano: tiempos sí, posiciones no.** La API del CRTM devuelve
  coordenadas de esos autobuses, pero están congeladas —verificado: cero metros
  en varios minutos—, así que no se pintan en el mapa.
- **Llegada en vivo frente a horario teórico.** En el interurbano se distingue
  una de otra y se dice cuál es cuál.
- **Horarios: cada red publica una cosa distinta.** El CRTM da horas de paso
  reales. La EMT y el Metro solo publican **frecuencias**, así que se muestran
  las franjas («de 6:00 a 9:00, cada 5 min»): decir «pasa a las 7:03» sería
  inventarlo. En 101 líneas interurbanas los datos no distinguen laborables de
  festivos, y se avisa.
- **21 líneas no tienen recorrido** en los datos abiertos —entre ellas la F de
  la EMT y la Línea 3 de Metro—, porque no aparecen ni una vez en `trips.txt`.
  Se pueden buscar y abrir igual, avisando; sus llegadas funcionan.
- **Accesibilidad**: ver más abajo.
- **Estimaciones marcadas como tales.** La distancia andando es línea recta más
  un 25% por el rodeo de las manzanas, y tira alto a propósito: quedarse corto
  hace perder el autobús.

### Accesibilidad

Cumplir **WCAG 2.1 AA** es un requisito del proyecto. Toda la aplicación se
maneja con teclado, con foco visible, etiquetas, landmarks y
`prefers-reduced-motion`.

Sobre la accesibilidad **del transporte**, que es otra cosa:

- **Metro**: cada estación dice si tiene ascensor o rampa, y se puede filtrar.
  Son 166 de 242, de la [lista oficial](https://www.metromadrid.es/es/accesibilidad).
  Las que tienen medidas complementarias pero **no** ascensor ni rampa no llevan
  el símbolo de silla: marcarlas sería el error que más daño hace.
- **Autobús**: no existe el dato por parada. La EMT no publica siquiera la
  columna y el CRTM marca casi todas las suyas con un valor por defecto. Así que
  **del bordillo y la acera no se afirma nada**. Lo que sí vale para todas las
  paradas de la EMT, y se cuenta una vez en «Planos y tarifas»: su flota es
  [100% de piso bajo y rampa](https://www.emtmadrid.es/Empresa/RSC/Accesibilidad),
  y todas tienen [código NaviLens](https://www.emtmadrid.es/Noticias/EMT-instala-codigos-NaviLens-en-sus-paradas-para-m.aspx)
  desde mayo de 2023, validado por la ONCE y el CERMI.

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
  tipografia.css       # Inter, servida desde el propio dominio
  privacidad.html      # Privacidad, condiciones de uso y atribuciones
  app.js               # Lógica del mapa, búsqueda, favoritos, llegadas y vehículos
  sw.js                # Service worker: la interfaz, sin conexión
  manifest.json        # Para poder instalarla en la pantalla de inicio
  assets/              # Logo, iconos de parada y estación, y los archivos de fuente
scripts/
  precalcular_datos.py        # Paradas, líneas y colores, desde el GTFS crudo
  precalcular_horarios.py     # Horarios de paso de cada línea
  precalcular_accesibilidad.py# Estaciones de Metro accesibles
  precalcular_nombres_metro.py# La ortografía correcta de las estaciones
tests/                 # Suite del backend, sin red
  frontend/            # Tests de navegador, aparte (ver Tests)
api/index.py           # Punto de entrada del backend en Vercel
vercel.json            # Reparto de rutas entre frontend estático y API
```

## Endpoints

| Endpoint | Descripción |
|---|---|
| `GET /paradas` | Las 13.533 paradas de las tres redes con id, nombre, coordenadas y fuente |
| `GET /paradas/cerca` | Las más próximas a un punto (`?lat=&lon=`). Unos 4 KB frente a los 254 de la lista completa, para poder empezar a usar la aplicación antes de que llegue |
| `GET /parada/{stop_id}` | Próximas llegadas de autobús. Para EMT devuelve el JSON de su API; para ids `par_` (interurbano) devuelve las llegadas agrupadas por línea y destino |
| `GET /lineas` | Las 603 líneas de las tres redes, sin recorrido, para el buscador |
| `GET /linea/{id}` | Una línea con sus paradas en orden, separadas por sentido (ej. `EMT-027`) |
| `GET /linea/{id}/horarios` | Horarios de paso por sentido y tipo de día. Devuelve horas reales en el interurbano y franjas de frecuencia en EMT y Metro |
| `GET /incidencias` | Los avisos de servicio de la EMT, cada uno con su estado calculado a partir de su ventana de vigencia |
| `GET /metro/parada/{cod_stop}` | Próximos trenes en una estación, agrupados por línea y destino |
| `GET /metro/parada/{cod_stop}/lineas` | Solo las líneas de una estación; la mitad barata del anterior, para el mapa |
| `GET /metro/linea/{cod_line}/vehiculos` | Posición de los trenes de una línea. Acepta `?cod_stop=est_XXX` para obtener los cercanos a una estación concreta |
| `GET /metro/lineas/colores` | Colores oficiales de las líneas de Metro; el frontend lo pide una vez al arrancar |

Cuando una API externa no responde, los endpoints que dependen de ella devuelven `503` con un mensaje, en vez de un error genérico.

## Datos precalculados

`backend/data/` ocupa 188 MB en disco, pero al repositorio solo van `stops.txt` y `routes.txt` de cada fuente. Los archivos pesados —`stop_times.txt` son 1,9 millones de filas— están excluidos.

Eso dejaba un problema: la búsqueda por línea los necesitaba, así que un clon limpio se quedaba sin ella. La clave es que esos 188 MB se leen al arrancar y se tiran: de todos esos viajes solo sobrevive **uno representativo por línea y sentido**. El resultado son 2,7 MB, que sí caben en el repositorio.

Por eso `backend/data/precalculado/` va versionado. Se regenera con:

```bash
python -m scripts.precalcular_datos
```

**Hay que volver a ejecutarlo cada vez que se descargue un volcado GTFS nuevo**, o la aplicación seguirá sirviendo los datos del anterior. De paso, el arranque baja de 2,77 s a 0,03 s.

Junto a los tres archivos que salen del GTFS hay otros tres que se generan aparte, cada uno con su script, porque los datos abiertos no los traen:

| Archivo | Qué es | Cómo se regenera |
|---|---|---|
| `horarios.json` | Horas de paso del interurbano y franjas de frecuencia de EMT y Metro | `python -m scripts.precalcular_horarios` |
| `accesibilidad.json` | Las 166 estaciones de la lista oficial de Metro, con su grado | `python -m scripts.precalcular_accesibilidad` |
| `nombres_metro.json` | La ortografía correcta de 234 estaciones, con sus tildes | `python -m scripts.precalcular_nombres_metro` |

Los dos últimos van **por id de estación**, así que un volcado que renumere los ids los deja sin casar. Hay tests que lo detectan.

## Tests

```bash
pip install -r requirements-dev.txt
pytest              # 58 del backend, medio segundo, sin red
pytest -m navegador # 52 que abren Chrome, unos 30 s
```

**Ninguno sale a la red.** Los del backend solo prueban rutas que responden
desde memoria o que cortan antes de llamar a EMT o al CRTM, así que una caída
de una API externa no puede ponerlos en rojo. Los de navegador copian la página
a un temporal y allí cambian dos cosas: el backend apunta a uno de mentira y
Leaflet se sustituye por un doble. Así no se prueba código de otros.

**Van aparte a propósito**: media docena de segundos frente a media décima. Lo
que hace útil a la suite del backend es poder lanzarla a cada cambio.

Cubren la lógica pura —agrupación de llegadas, tiempo real frente a horario
teórico, validación de identificadores— y sobre todo **invariantes de los
datos**, que es donde más duele este proyecto: un volcado GTFS nuevo puede
romper algo en silencio y no se nota hasta que una estación desaparece del
mapa.

Necesitan Chrome; su ruta se puede dar con `CHROME_PARA_TESTS`. En GitHub
Actions van en un job propio, y ese job **falla si no encuentra Chrome**: unos
tests que se saltan solos darían verde sin haber probado nada.

## Despliegue

Está desplegado en Vercel: el frontend como archivos estáticos y FastAPI como función, montada bajo `/api`. Al compartir dominio, en producción no hace falta CORS.

El repositorio está conectado, así que **cada cambio que entra en `main` se despliega solo**, y cada rama genera un preview con su propia URL. `main` está protegida: no admite pushes directos y exige que los dos jobs de tests estén en verde antes de poder mergear un PR, de modo que a producción no llega nada sin probar.

La pieza que hay que respetar es `.vercelignore`: sin él, el despliegue se lleva los 188 MB de GTFS crudo. Ojo a que se aplica al build estático **pero no al paquete de la función**, que necesita además `excludeFiles` en `vercel.json` para lo mismo.

## Cómo arrancarlo

Hace falta Python 3.10 o superior y, **solo para los autobuses de la EMT**, una
cuenta en [Mobility Labs Madrid](https://mobilitylabs.emtmadrid.es). Metro y el
interurbano usan una API pública sin autenticación.

```bash
git clone https://github.com/abrilespinosa/moom.git && cd moom
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # y rellénalo con tus credenciales
```

Después, **dos terminales**:

```bash
# 1 — backend, desde la raíz
uvicorn backend.main:app --reload

# 2 — frontend, desde frontend/
python3 -m http.server 5500
```

Y <http://localhost:5500>.

> Dos cosas rompen el arranque si se ignoran. El frontend **tiene que servirse
> por HTTP**: abrir el archivo con doble clic (`file://`) bloquea la
> geolocalización y cambia el comportamiento de `fetch`. Y el backend se
> arranca **desde la raíz**, no desde `backend/`, porque `main.py` importa como
> `from backend.emt_client import ...` y los GTFS se abren con rutas relativas
> al directorio de trabajo.

## Privacidad

No hay cuentas, ni base de datos, ni analítica, ni cookies. **Moom no recoge ningún dato personal.**

Al compartir tu ubicación, las coordenadas se usan solo dentro de tu navegador para ordenar las paradas por cercanía: **no se envían al servidor ni a ningún tercero**, y no se guardan. Los favoritos y el ancho del panel viven en `localStorage`, en tu equipo.

La tipografía **se sirve desde el propio dominio** y no desde Google Fonts, para que abrir el mapa no transmita la IP de cada visitante a Google. **CARTO es el único tercero** al que el navegador pide algo, y solo por las imágenes del mapa: Leaflet también se sirve desde el propio dominio. Está declarado en [`frontend/privacidad.html`](frontend/privacidad.html), junto con las condiciones de uso y las atribuciones.

Esa lista no se mantiene sola: `tests/test_terceros_del_frontend.py` falla si aparece un servidor ajeno que no esté declarado en esa página, o si alguien vuelve a cargar una fuente desde Google.

## Atribución

Este proyecto usa datos de la API de EMT Madrid (Mobility Labs). Según sus condiciones de uso, debe mencionarse a EMT Madrid MobilityLabs como fuente de los datos.

Los datos de Metro e interurbanos proceden del Consorcio Regional de Transportes de Madrid (CRTM).

## Licencia

El **código** de este repositorio se publica bajo licencia [MIT](LICENSE).

Los **datos** no lo están. Los archivos GTFS de `backend/data/` pertenecen a la EMT de Madrid y al CRTM, y se rigen por las condiciones de uso de sus respectivos portales de datos abiertos; aquí se incluyen únicamente para que el proyecto funcione al clonarlo. Lo mismo aplica a los datos que devuelven sus APIs en tiempo real.

Una nota sobre esas APIs: la de EMT es oficial y está documentada. La del CRTM (`crtm.es/widgets/api`) es la que alimenta los widgets de su propia web — es pública y no requiere autenticación, pero no está documentada ni tiene condiciones de uso publicadas. El proyecto la usa con moderación (cachés en memoria e intervalos de sondeo ajustados al ritmo real al que cambian los datos), pero conviene saber que no hay garantía de estabilidad.
