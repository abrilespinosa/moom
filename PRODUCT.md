# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Principal: alguien en Madrid, de pie en la parada, con el móvil en una mano.**
Tiene prisa, está a la intemperie —a menudo con sol directo en la pantalla— y
está decidiendo una sola cosa: si espera o si echa a andar.

**Secundario: quien evalúa el trabajo de Abril.** Reclutadores y otras personas
que programan. El proyecto también es portafolio.

**Cuando los dos entran en conflicto, manda el viajero.** Confirmado por la
autora. Diseñar para quien está en la calle es, además, lo que hace que
funcione como portafolio; al revés no.

## Product Purpose

Ver en un mapa, en tiempo real, las tres redes de transporte público de Madrid
—autobús urbano de la EMT, autobús interurbano del CRTM y Metro— para poder
responder «¿cuánto falta para el mío?» sin abrir tres aplicaciones distintas.

El éxito es que la respuesta llegue **antes de que la persona se rinda** y abra
la aplicación oficial.

## Positioning

Las tres redes en un único mapa y un único buscador. Los canales oficiales las
tienen separadas: EMT, Metro y CRTM tienen cada uno su aplicación y su propio
sistema de identificadores de parada.

Dos cosas que no son habituales:

- **Llegadas en vivo del interurbano.** No estaba documentado que la API del
  CRTM las diera; se descubrió probándola. Además se distingue una llegada con
  corrección en tiempo real de una que solo sale del horario teórico.
- **Posición real de los trenes de Metro** sobre el mapa, no solo los tiempos.

Sin instalar nada y sin cuenta.

## Operating Context

- **La escena real es la calle**: a una mano, de pie, con prisa. En escritorio
  y tableta apaisada la interfaz es panel + mapa; en móvil y tableta vertical
  el panel es una hoja que sube desde abajo.
- **Recorrido típico**: abrir → encontrar la parada (buscador, favoritos o
  «Cerca de ti») → leer las llegadas → decidir. Desde una línea también se
  puede entrar a su recorrido y de ahí a cualquiera de sus paradas.
- **Los datos vienen de tres APIs externas con garantías distintas**: una
  autenticada y con cuota diaria (EMT), otra pública pero sin documentar
  (CRTM). La latencia del CRTM va de 0,1s a 4,5s para la misma consulta, y eso
  no se puede arreglar desde aquí.
- **Producción**: <https://moom-abril-espinosa.vercel.app>. El repositorio está
  conectado a Vercel, así que **cada cambio que entra en `main` se despliega
  solo**; `main` está protegida y exige PR con los tests en verde.

## Capabilities and Constraints

**Funciona hoy**: llegadas por parada en las tres redes; posición de autobuses
EMT y de trenes de Metro en el mapa; buscador único de paradas y líneas;
recorrido de línea por sentido; horarios de paso; favoritos, recientes y
cercanía con distancia y tiempo andando; **avisos de servicio de la EMT con su
estado**; **planos oficiales y tarifas**; y **accesibilidad por estación de
Metro**, con un interruptor que se cruza con el filtro de red.

**Restricción de datos que atraviesa todo lo anterior**: los volcados del CRTM
y de Metro escriben los nombres en mayúsculas, y el de Metro ha perdido las
tildes agudas. Ni la API en vivo del CRTM las tiene: para el andén 4_11
devuelve `"GRAN VIA"`. La ortografía correcta de las 234 estaciones se repone
desde una lista verificada contra el anexo de Wikipedia, aceptando un nombre
**solo** si coincide letra por letra ignorando tildes. Un volcado GTFS nuevo
obliga a regenerarla.

**Restricciones que el trabajo futuro debe respetar**:

- **La EMT tiene cuota diaria.** Por eso hay caché de 30s por parada. No se
  puede sondear alegremente.
- **La API del CRTM no está documentada ni tiene condiciones de uso
  publicadas.** Funciona, pero no hay garantía de estabilidad ni permiso
  explícito. Se usa con moderación a propósito.
- **Las posiciones del interurbano están congeladas** en el origen (verificado:
  cero metros en varios minutos). Por eso **no se pintan** esos autobuses en el
  mapa, aunque la API los devuelva.
- **Los volcados GTFS caducan.** El de Metro está caducado desde el 27-05-2026.
  Un volcado nuevo obliga a regenerar los datos precalculados.
- **21 líneas no tienen recorrido** en los datos abiertos (entre ellas la Línea
  3 de Metro). Se muestran igual, avisando, porque sus paradas y sus tiempos sí
  funcionan.
- **Los tiles del mapa son de CARTO y desde agosto de 2026 requieren clave.**
  La capa gratuita da **5 millones de peticiones de tile al mes** (raster y
  vector juntas) y está pensada para **uso no comercial**; pasarse no corta el
  servicio, pero abre una conversación con ellos. **La atribución a CARTO y a
  OpenStreetMap tiene que seguir visible: es literalmente el intercambio por la
  capa gratuita.** La clave va en el frontend por necesidad técnica —tiene que
  llegar al navegador— y está vinculada al dominio que se declaró al pedirla;
  no hay panel donde cambiarla, porque no hay cuenta.
  **Ojo con la forma de fallar**: sin clave, o con un nombre de parámetro
  equivocado, el servidor devuelve un 200 con un PNG válido que lleva "API KEY
  REQUIRED" impreso dentro. Ningún test ni linter lo detecta; solo se ve
  mirando el mapa.

**Vocabulario del dominio** (importa, porque los tres orígenes no coinciden):
parada / estación / **andén** (`codAnden`, el único código que entiende la API
del CRTM), línea, sentido, y **llegada en vivo frente a horario teórico**.

**Decisión abierta — persistencia.** El estado actual (sin cuentas, sin base de
datos, favoritos solo en el navegador) es **interino**, no un fin. La intención
declarada es que algún día haya sincronización entre dispositivos. Si llega ese
momento, la decisión ya tomada es **SQLite antes que PostgreSQL**. Mientras
tanto, toda la persistencia está aislada en tres funciones del frontend, que es
lo único que habría que cambiar.

## Brand Commitments

- **Moom** = **mo**vilidad + **M**adrid.
- **Abril Espinosa es la única autora.** Nada de atribuciones de coautoría en
  commits, PRs ni documentación.
- **Interfaz en español.** El código, los comentarios y la documentación
  también; solo el texto que acaba en Git o GitHub va en inglés.
- **Identidad visual con manual propio**: naranja de marca `#F5A623`, logotipo
  en `assets/logo.svg`, lenguaje visual inspirado en iOS. Los contrastes están
  medidos y documentados en las variables de `style.css`.
- **Inter, autoalojada.** No es una preferencia estética sino un compromiso con
  motivo legal: servirla desde Google Fonts transmitía la IP de cada visita a
  Google. **No revertir.**
- **Licencias**: el código es MIT; los datos **no**, y pertenecen a la EMT y al
  CRTM. La atribución a «EMT Madrid MobilityLabs» es exigida por sus
  condiciones de uso.
- **Hay una página de privacidad publicada que afirma cosas verificables**:
  que no se recoge ningún dato personal, que la ubicación nunca sale del
  dispositivo, y la lista **completa** de terceros a los que el navegador pide
  algo. Cualquier trabajo futuro que añada un tercero tiene que actualizarla;
  hay un test que lo vigila.

## Evidence on Hand

**Real y comprobable**: el despliegue en producción; datos GTFS reales (13.533
paradas, 603 líneas); tres APIs en vivo; **58 tests de backend y 43 de
navegador**; una auditoría técnica propia con nota 14/20 (agosto de 2026,
antes de arreglar la accesibilidad); y una crítica de diseño del 2026-09-02
con **22/40** en las heurísticas de Nielsen, archivada en
`.impeccable/critique/`.

**Lo que NO existe, y no se debe inventar**: no hay usuarios reales conocidos,
ni métricas de uso, ni testimonios, ni casos de estudio, ni prensa, ni precios,
ni acuerdos con la EMT o el CRTM. El proyecto nunca se ha promocionado.

## Product Principles

1. **En un conflicto, gana quien está en la parada**, no quien revisa el
   código.
2. **Un dato viejo, dicho que es viejo, informa más que un panel vacío.** Si un
   refresco falla se avisa, pero no se borra lo que hay en pantalla.
3. **Estimar por lo alto cuando el error es asimétrico.** Decir 7 minutos
   cuando son 5 hace esperar; decir 5 cuando son 7 hace perder el autobús.
4. **Nada de la persona sale de su dispositivo** mientras ella no decida lo
   contrario.
5. **No aparentar más precisión de la que da el origen.** Si las posiciones
   están congeladas, no se pintan; si una llegada es horario teórico, se dice.
6. **Nada se pone por delante del dato.** Cada función nueva es correcta por
   separado y aun así empuja hacia abajo el número por el que se abrió la
   aplicación. Medido el 2026-09-02: cinco funciones desplegadas en un día
   dejaron 333 px de cromo antes del primer resultado y la primera llegada al
   62% de la pantalla. Lo que se consulta de vez en cuando va al pie; lo que se
   consulta siempre, arriba.

## Accessibility & Inclusion

**WCAG 2.1 nivel AA es un requisito del producto**, confirmado por la autora.

**Estado real, medido el 2026-09-02.** La brecha que dejó la auditoría del
31 de agosto en 1/4 está cerrada: los resultados son botones de verdad, hay
indicador de foco visible, el buscador tiene etiqueta, hay landmarks y se
respeta `prefers-reduced-motion`. Comprobado recorriendo la página con el
teclado: **15 paradas, ciclo cerrado, foco visible en las 15**.

**Lo que sigue abierto**, de la crítica del 2026-09-02:

- Un `aria-label` explícito **sustituye** al contenido del botón, no lo
  acompaña. Se arregló componiendo la etiqueta a mano, pero el patrón es fácil
  de repetir: cualquier botón nuevo que lleve hijos con información tiene que
  llevarla también en su nombre accesible.
- Los cambios de vista no mueven el foco ni se anuncian.
- Los títulos de vista siguen siendo `<div>` en vez de encabezados reales, así
  que navegar por encabezados no funciona.
- La estrella de favorito sin marcar da **2,11:1**, por debajo del 3:1 que
  WCAG 1.4.11 exige a un gráfico con significado.

**Y una regla de contraste que costó descubrir**: Tinta Suave sobre el papel
tibio de los controles se queda en 4,54. Cualquier superficie de control más
oscura que `#f8f6f3` vuelve a incumplir AA en las etiquetas de filtro.

Además, propias de la escena de uso: **legibilidad con sol directo** y
**alcance a una mano** en móvil.
