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

**Horarios de paso**
- Al abrir una línea se pueden desplegar sus horarios, separados por sentido y por tipo de día.
- **Cada red publica una cosa distinta y el panel lo respeta.** El interurbano del CRTM da horas de paso reales, así que se muestra la tabla de salidas. La EMT y el Metro solo publican **frecuencias**, así que se muestran las franjas con su intervalo («de 6:00 a 9:00, cada 5 min»): decir «pasa a las 7:03» sería inventarse una precisión que el origen no tiene.
- En 101 de las 340 líneas interurbanas los datos abiertos **no distinguen** laborables de sábados y domingos. En esas se avisa, en vez de dar a entender que solo hay un horario.

**Búsqueda por línea**
- Un único buscador para paradas y líneas: al escribir un número, las líneas aparecen primero y se prioriza la coincidencia exacta (quien busca "27" quiere la línea 27, no la 270).
- Al elegir una línea se ve su recorrido completo, con las paradas en orden y separadas por sentido; desde ahí se salta a las llegadas de cualquiera de ellas.
- Funciona nada más clonar el repositorio: los recorridos vienen precalculados en `backend/data/precalculado/`, así que no hacen falta los archivos GTFS pesados (ver [Datos precalculados](#datos-precalculados)).
- Hay 21 líneas que los datos abiertos no detallan (la F y la G de la EMT, la Línea 3 de Metro y varias interurbanas). Se pueden buscar y abrir igual, avisando de que su recorrido no está disponible; sus paradas y sus tiempos en vivo funcionan con normalidad.

**Avisos de servicio**

- Un botón aparece **solo cuando hay algo**, y lleva a la lista de avisos de la EMT con el estado de cada uno: en curso, programado o ya terminado.
- Los terminados se enseñan igual, atenuados: saber que el desvío de tu línea ya acabó explica por qué el autobús venía raro esta mañana.
- **El contador excluye los terminados.** El día que se construyó esto, 20 de los 21 que devolvía la API ya habían pasado: un contador de «21 avisos» habría sido ruido puro.
- Los avisos llegaban dentro de la misma respuesta que las llegadas y eran **19 KB de sus 22**, pedidos cada diez segundos. Ahora se sirven aparte y la respuesta de una parada baja a 4 KB.

**Planos y tarifas**

- Los planos oficiales de Metro, EMT, interurbano y Cercanías, **enlazados y no copiados**: pertenecen a Metro y al CRTM.
- **Cada uno dice lo que pesa** antes de que lo toques. El esquemático de Metro son 6,2 MB, y con datos móviles en la calle eso es la diferencia entre abrirlo y arrepentirse. Los pesos están medidos, no estimados.
- Las tarifas de un viaje, diez viajes y abonos, **con la fecha desde la que valen**. Cambian al menos una vez al año y desde aquí no hay forma de enterarse: un precio viejo sin fecha es una mentira, con la fecha delante sigue informando.

**Accesibilidad de las estaciones**

- Las estaciones de Metro con ascensor o rampa llevan un distintivo, y hay un interruptor para ver **solo** esas.
- **No es un modo de transporte, así que no está en el grupo de filtros**: se cruza con ellos. Como quinta píldora excluyente, activarlo hacía desaparecer la EMT y el CRTM enteros, y quien buscaba una parada de bus accesible leía «no hay ninguna» cuando lo cierto es que ese dato no existe fuera del Metro.
- Los datos salen de la [lista oficial de Metro de Madrid](https://www.metromadrid.es/es/accesibilidad). **Las estaciones con medidas complementarias pero sin ascensor ni rampa no llevan el símbolo de silla**: para quien va en silla, marcarlas sería el error que más daño hace.
- **El filtro dice explícitamente que solo cubre el Metro**, y al activarlo se explica por qué desaparecen los autobuses. Sin eso, la ausencia se leería como «las paradas de bus no son accesibles», que es justo lo contrario.

**Lo que sí se sabe de las paradas de autobús**

Ninguna de las tres fuentes publica un dato fiable de accesibilidad por parada: la EMT no trae siquiera la columna, y el CRTM marca 5.964 de sus paradas como «no accesible» y ninguna como accesible, que es un valor por defecto y no un inventario. Así que **de la acera y el bordillo de una parada concreta no se afirma nada**. Pero hay dos hechos verificados que sí valen para todas las de la EMT, y se muestran en su ficha:

- **Toda la flota lleva piso bajo y rampa.** Es [el único modo de transporte de Madrid 100% accesible](https://www.emtmadrid.es/Empresa/RSC/Accesibilidad). El distintivo habla del **autobús**, no de la parada.
- **Todas las paradas tienen código NaviLens** desde mayo de 2023: 4.499 marquesinas y 1.041 postes, validado por la ONCE y el CERMI. Se lee con la cámara del móvil hasta a 15 metros y en movimiento, y dice en voz las líneas y los tiempos ([nota de prensa](https://www.emtmadrid.es/Noticias/EMT-instala-codigos-NaviLens-en-sus-paradas-para-m.aspx)).

**Nombres escritos como se escriben**

- Los volcados del CRTM y de Metro guardan los nombres EN MAYÚSCULAS: 8.397 paradas interurbanas y 229 de las 242 estaciones. Se corrigen al cargar.
- El de Metro además ha perdido las tildes agudas, y **ninguna fuente de datos las tiene**: la API en vivo del CRTM devuelve `"GRAN VIA"` igual que el GTFS. La ortografía de las 234 estaciones se repone desde una lista verificada, aceptando un nombre solo si coincide letra por letra ignorando tildes.

**Favoritos, recientes y cercanía**
- Paradas y líneas se pueden marcar como favoritas, y se guardan en el navegador (`localStorage`).
- Las **tres últimas paradas consultadas** se recuerdan y aparecen con el buscador vacío, porque quien usa esto a diario se mueve entre unas pocas paradas y tenía que buscarlas otra vez en cada visita.
- Con el buscador vacío, la lista muestra los favoritos, filtrados por el modo de transporte activo igual que una búsqueda.
- Al compartir tu ubicación aparece un grupo **Cerca de ti** con las paradas más próximas, y cada una indica a qué distancia está y cuánto se tarda andando. Es una estimación: línea recta más un 25% por el rodeo de las manzanas, y tira ligeramente alto a propósito, porque quedarse corto hace perder el autobús.

**Mapa e interfaz**
- Leaflet **autoalojado** (no desde un CDN, por privacidad) con tiles de CartoDB Voyager, que desde agosto de 2026 requieren clave.
- Paradas visibles a partir de zoom 15 y solo dentro del área en pantalla, para no dibujar miles de marcadores a la vez.
- Filtros por red: Todos / Urbano / Interurbano / Metro, y un interruptor aparte de **solo estaciones accesibles** que se cruza con ellos.
- Botón de geolocalización para centrar el mapa en tu posición.
- Panel lateral redimensionable arrastrando el divisor; el ancho elegido se recuerda entre visitas.
- **En móvil y en tableta vertical** el panel deja de ser una columna y pasa a ser una hoja que sube desde abajo, arrastrable desde la banda naranja, con el mapa a pantalla completa detrás. En tableta horizontal y en escritorio se mantiene la vista de dos paneles, que es donde tiene sentido.
- Refresco automático: cada 10 s para EMT y cada 20 s para Metro, acompasado con el ritmo al que cada API actualiza sus datos. Si un refresco falla, se avisa en el panel en vez de seguir mostrando los tiempos viejos como si fueran actuales.

**Pensado para usarse de pie en la parada**
- **Se instala en la pantalla de inicio** y **abre sin conexión**: la interfaz se guarda en el dispositivo, así que aparece al instante incluso bajo tierra. Los tiempos, eso sí, necesitan red: no se enseñan llegadas viejas sin decir de cuándo son.
- **Los refrescos se paran** cuando la pantalla se apaga o cambias de pestaña, y se reanudan al volver. Antes seguía pidiendo datos con el móvil en el bolsillo.
- **El tiempo de la próxima llegada se agranda en móvil**, que es donde se lee a un brazo de distancia y con sol de frente.
- **Si ya diste permiso de ubicación**, la aplicación abre directamente en las paradas que tienes cerca, sin volver a preguntarte.

**Accesibilidad**

Cumplir WCAG 2.1 AA es un requisito del proyecto, no una aspiración. Toda la aplicación se maneja con teclado, hay indicador de foco visible, el buscador tiene etiqueta y se respeta `prefers-reduced-motion`, que en una hoja que recorre toda la pantalla no es un detalle.

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
  precalcular_datos.py # Genera backend/data/precalculado/ desde el GTFS crudo
  precalcular_horarios.py # Genera los horarios de paso de cada línea
tests/                 # Suite de pytest del backend (44 tests, sin red)
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
pytest
```

58 tests en menos de un segundo. **Ninguno sale a la red**: solo se prueban rutas que responden desde memoria o que cortan antes de llamar a EMT o al CRTM, comprobado ejecutándolos con las conexiones salientes bloqueadas. Una caída de una API externa no puede poner la suite en rojo.

### Tests de frontend

Hay otros 43 que abren la página en Chrome y comprueban lo que aparece en pantalla: el orden de los resultados del buscador, el cambio entre las tres vistas, el aviso cuando el backend falla, los favoritos, las paradas recientes, el camino de teclado y que al salir de una estación no queden trenes en el mapa.

```bash
pytest -m navegador
```

**Van aparte a propósito.** Tardan unos 25 segundos, así que meterlos en `pytest` a secas quitaría lo que hace útil a la suite del backend: que es instantánea y se puede lanzar a cada cambio. Por eso `pytest` sin argumentos sigue ejecutando solo los 58 del backend.

Tampoco salen a la red. La página se copia a un directorio temporal y allí se le cambian dos cosas: el backend apunta a uno de mentira que sirve el propio test, y Leaflet se sustituye por un doble que implementa solo lo que `app.js` usa. Así no se prueba Leaflet, que es código de otros, sino el nuestro.

Necesitan Chrome. Si no está en la ruta habitual de macOS, se indica con `CHROME_PARA_TESTS=/ruta/a/chrome`; si no se encuentra, los tests se saltan en vez de fallar.

También se ejecutan en GitHub Actions, en un job aparte del backend para que un fallo del navegador no se confunda con un fallo de la API. Ahí el job localiza Chrome y **falla si no hay ninguno**: en CI, unos tests que se saltan solos darían verde sin haber probado nada.

Cubren la lógica pura (agrupación de llegadas, distinción entre tiempo real y horario teórico, filtrado de líneas que no son de Metro, validación de identificadores) y varios invariantes de los datos, que es donde más duelen los fallos de este proyecto: un volcado GTFS nuevo puede romperlos en silencio y no se nota hasta que una estación desaparece del mapa.

Se ejecutan también en GitHub Actions en cada push.

## Despliegue

Está desplegado en Vercel: el frontend como archivos estáticos y FastAPI como función, montada bajo `/api`. Al compartir dominio, en producción no hace falta CORS.

El repositorio está conectado, así que **cada cambio que entra en `main` se despliega solo**, y cada rama genera un preview con su propia URL. `main` está protegida: no admite pushes directos y exige que los dos jobs de tests estén en verde antes de poder mergear un PR, de modo que a producción no llega nada sin probar.

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

## Privacidad

No hay cuentas, ni base de datos, ni analítica, ni cookies. **Moom no recoge ningún dato personal.**

Al compartir tu ubicación, las coordenadas se usan solo dentro de tu navegador para ordenar las paradas por cercanía: **no se envían al servidor ni a ningún tercero**, y no se guardan. Los favoritos y el ancho del panel viven en `localStorage`, en tu equipo.

La tipografía **se sirve desde el propio dominio** y no desde Google Fonts, para que abrir el mapa no transmita la IP de cada visitante a Google. Los únicos terceros a los que el navegador pide algo son CARTO (las imágenes del mapa) y unpkg (Leaflet); están declarados en [`frontend/privacidad.html`](frontend/privacidad.html), junto con las condiciones de uso y las atribuciones.

Esa lista no se mantiene sola: `tests/test_terceros_del_frontend.py` falla si aparece un servidor ajeno que no esté declarado en esa página, o si alguien vuelve a cargar una fuente desde Google.

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
