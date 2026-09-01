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
recorrido de línea por sentido; favoritos; distancia y tiempo andando a las
paradas cercanas.

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
paradas, 603 líneas); tres APIs en vivo; 50 tests de backend y 25 de navegador;
y una auditoría técnica propia con nota 14/20 (agosto de 2026, antes de
arreglar la accesibilidad).

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

## Accessibility & Inclusion

**WCAG 2.1 nivel AA es un requisito del producto**, confirmado por la autora.

**Hoy no se cumple.** La auditoría del 2026-08-31 dejó esta dimensión en 1/4:
con teclado no se puede seleccionar una parada (los resultados son `<li>` con
`click`), no hay indicador de foco visible, el buscador no tiene etiqueta, no
hay soporte de `prefers-reduced-motion` y no hay landmarks. Cerrar esa brecha
es trabajo comprometido, no opcional.

Además, propias de la escena de uso: **legibilidad con sol directo** y
**alcance a una mano** en móvil.
