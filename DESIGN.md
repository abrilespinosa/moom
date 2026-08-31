---
name: Moom
description: Transporte público de Madrid en tiempo real, legible de un vistazo y de pie en la calle.
colors:
  naranja-marquesina: "#f5a623"
  ambar-legible: "#9a5b00"
  ambar-lavado: "#fdf1dd"
  tinta: "#121212"
  tinta-suave: "#767068"
  papel: "#ffffff"
  papel-calido: "#faf9f7"
  linea-tenue: "#e6e3de"
  linea-marcada: "#ded8ce"
  estrella-apagada: "#b8b2a8"
  verde-sistema: "#34c759"
  azul-sistema: "#007aff"
  rojo-sistema: "#ff3b30"
  gris-desactivado: "#8e8e93"
typography:
  display:
    fontFamily: "Inter, -apple-system, Segoe UI, Roboto, Arial, sans-serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Inter, -apple-system, Segoe UI, Roboto, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Inter, -apple-system, Segoe UI, Roboto, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "-0.01em"
  label:
    fontFamily: "Inter, -apple-system, Segoe UI, Roboto, Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.06em"
rounded:
  sm: "12px"
  md: "16px"
  lg: "22px"
  full: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
components:
  ficha-resultado:
    backgroundColor: "{colors.papel}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.md}"
    padding: "12px 14px"
    typography: "{typography.body}"
  filtro-activo:
    backgroundColor: "{colors.papel}"
    textColor: "{colors.ambar-legible}"
    rounded: "{rounded.sm}"
    padding: "8px 10px"
  buscador:
    backgroundColor: "{colors.papel-calido}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.sm}"
    padding: "10px 14px"
    height: "44px"
  cabecera-marca:
    backgroundColor: "{colors.naranja-marquesina}"
    textColor: "{colors.tinta}"
    padding: "18px 16px"
---

# Design System: Moom

## Overview

**Creative North Star: «La marquesina limpia»**

Moom se mira de pie, con prisa, a plena luz y con una mano. El sistema visual
está construido para ese momento y no para una captura de pantalla: es
mobiliario urbano bien hecho, no una aplicación que quiere que la admires.

De ahí salen sus dos decisiones de fondo. La primera es que **el color es
señalética**: casi toda la interfaz es papel, tinta y sombra, y el color
aparece únicamente donde significa algo —la marca, lo que está activo, la línea
de Metro, el modo de transporte—. La segunda es que **la profundidad reemplaza
a la raya**: no hay un solo borde sólido separando bloques, porque una línea
gris siempre lee como una división administrativa; las cosas se separan
levantándose del fondo.

Nada decora. Si un elemento no ayuda a decidir si esperas o si echas a andar,
sobra.

**Key Characteristics:**

- Papel cálido de fondo, fichas blancas que flotan sobre él.
- Esquinas generosas y proporcionales al tamaño: nada tiene pico.
- Un único naranja de marca, y un ámbar oscuro para cuando ese naranja tiene
  que ser texto.
- Contraste y tamaño antes que refinamiento.
- El movimiento responde al dedo; nunca entretiene.

## Colors

Una paleta casi monocroma de papeles y tintas cálidas, con un solo acento y un
puñado de colores de sistema que solo aparecen cuando informan de algo.

### Primary

- **Naranja Marquesina** (`#f5a623`): la marca. Vive en la banda de cabecera
  —el único bloque de color pleno de la interfaz— y en los rellenos y aros de
  lo que está activo. **Nunca lleva texto blanco encima.**
- **Ámbar Legible** (`#9a5b00`): el mismo naranja llevado a un valor que se
  puede leer. Es el que se usa para texto de acento sobre blanco, para el aro
  de foco y para los enlaces.
- **Ámbar Lavado** (`#fdf1dd`): relleno del estado señalado y de la fila
  seleccionada. Es el naranja a volumen bajo, para teñir sin gritar.

### Neutral

- **Tinta** (`#121212`): todo el texto principal, y también lo que va encima
  del naranja de marca.
- **Tinta Suave** (`#767068`): texto secundario —subtítulos, códigos de parada,
  distancias—. Cálido a propósito, para no enfriar el papel.
- **Papel** (`#ffffff`): fichas, cabeceras de sección y superficies elevadas.
- **Papel Cálido** (`#faf9f7`): el fondo del panel. Un blanco apenas tostado,
  cuyo único trabajo es que las fichas blancas se despeguen sin necesitar un
  borde.
- **Línea Tenue** (`#e6e3de`) y **Línea Marcada** (`#ded8ce`): separadores y
  tiradores. Se usan con cuentagotas.
- **Estrella Apagada** (`#b8b2a8`): el contorno de un favorito sin marcar.

### Tertiary

Colores de sistema tomados de iOS. **No son decorativos: cada uno significa un
estado y solo aparece cuando ese estado ocurre.** Verde Sistema (`#34c759`),
Azul Sistema (`#007aff`, también el punto de «mi ubicación», azul por
convención cartográfica) y Rojo Sistema (`#ff3b30`).

### Named Rules

**La Regla de los Dos Naranjas.** El naranja de marca da 2:1 sobre blanco: es
un **relleno**, nunca un color de texto. Sobre él va tinta oscura (10:1). Para
texto naranja sobre blanco existe el Ámbar Legible (5,5:1). Ampliar el acento a
más botones y enlaces —la dirección elegida— significa ampliar *este* par, no
pintar de `#f5a623` un texto: eso rompería el compromiso de WCAG AA.

**La Regla del Color con Significado.** Los colores de línea salen del GTFS, el
azul de los distintivos de bus es el corporativo de la EMT y el verde es el del
interurbano. **No se armonizan con la paleta.** Si un color puede confundirse
con uno de estos, no se usa para decorar.

## Typography

**Display / Body Font:** Inter (con `-apple-system`, `Segoe UI`, Roboto, Arial)

**Character:** una sola familia para todo, en variante variable y **servida
desde el propio dominio**. Neutra a propósito: la personalidad la ponen el
color y la forma, no la letra. El interletrado va ligeramente cerrado
(`-0.01em`) porque a tamaños grandes el espaciado por defecto de Inter se ve
suelto.

### Hierarchy

- **Display** (600, 24px, 1.1 · **700, 34px en móvil**): el tiempo de la
  próxima llegada. Es el número más grande de la interfaz porque es el dato por
  el que se ha abierto, y crece en la hoja de móvil porque ahí se lee de pie,
  a un brazo y con sol.
- **Title** (600, 15px): nombre de parada o de línea en la ficha.
- **Body** (400, 15px, 1.45): el texto general. En móvil el buscador sube a
  16px obligatoriamente.
- **Label** (700, 11px, +0.06em, versalitas): encabezados de grupo y
  distintivos. El único sitio donde se usa mayúscula.

### Named Rules

**La Regla de los 16 Píxeles.** Ningún campo de formulario baja de 16px. Por
debajo, Safari en iOS hace zoom automático al enfocarlo y descuadra la página
entera. No es una preferencia estética: es un fallo de maquetación.

## Layout

Dos modelos, elegidos por el espacio disponible y no por el dispositivo.

**Escritorio y tableta apaisada**: rejilla de tres columnas —panel, divisor
arrastrable y mapa— donde la primera mide una variable (`--ancho-panel`, 380px
por defecto). El divisor se arrastra y el ancho se recuerda entre visitas,
acotado para que ni el panel ni el mapa queden inservibles.

**Móvil y tableta vertical** (`max-width: 768px`, o `1024px` en vertical): el
panel deja de ser columna y pasa a ser una hoja que sube desde abajo, con el
mapa a pantalla completa detrás. **Solo dos posiciones de reposo**, recogida y
desplegada: los puntos intermedios obligan a recordar dónde quedó la hoja y no
aportan nada, porque el contenido ya se desplaza por dentro.

El ritmo de espaciado es de 4 en 4 (4 / 8 / 12 / 16). Las fichas se separan 4px
entre sí y respiran 12-14px por dentro: grupos apretados, separación generosa.

### Named Rules

**La Regla del Pulgar.** En cualquier modo táctil, nada que se pulse baja de
44×44px de área sensible. Se puede agrandar el área con un pseudo-elemento
manteniendo el tamaño visible, pero no se puede reducir el objetivo.

## Elevation & Depth

**Este sistema no tiene ni un borde sólido separando bloques.** La profundidad
es toda sombra, y la sombra es **respuesta, no decoración**: las superficies
están casi planas en reposo y se levantan cuando alguien las señala o las
pulsa.

Cada sombra son **dos capas**: una corta y cerrada que define el canto del
elemento, y otra larga y muy tenue que lo despega del fondo. Juntas dan volumen
sin que se vea una línea; un borde de 1px, por claro que sea, siempre lee como
una raya.

### Shadow Vocabulary

- **Sutil** (`0 1px 2px rgba(18,18,18,.04), 0 4px 12px rgba(18,18,18,.04)`):
  estado de reposo de las fichas.
- **Media** (`0 1px 2px rgba(18,18,18,.05), 0 8px 24px rgba(18,18,18,.07)`):
  la ficha señalada, y el panel sobre el mapa.
- **Flotante** (`0 2px 6px rgba(18,18,18,.08), 0 12px 32px rgba(18,18,18,.1)`):
  lo que vive por encima del mapa, como el botón de ubicación.

### Named Rules

**La Regla del Canto Doble.** Toda sombra nueva lleva sus dos capas. Una sombra
de una sola capa se ve como un halo pegado y delata el sistema.

## Shapes

Todo lleva radio, y **el radio es proporcional al tamaño del elemento**: 22px
para el panel y los contenedores grandes, 16px para las fichas, 12px para
controles y campos, y `999px` para lo que debe leerse como píldora
—distintivos de línea, tiradores, el botón de ubicación—.

Los resultados de búsqueda son **fichas separadas**, no filas con raya
divisoria. Es la consecuencia visible de no tener bordes: la separación la hace
el hueco y la sombra.

### Named Rules

**La Regla de Ningún Pico.** Ningún elemento tiene esquina viva. Si algo parece
necesitarla, es que le falta radio, no que sea la excepción.

## Components

### Fichas de resultado

- **Forma:** esquinas de 16px, fondo papel, sombra sutil.
- **Composición:** un `<button>` que ocupa el hueco y, a su lado, la estrella
  de favorito. Son **hermanos**, nunca anidados.
- **Señalado:** la ficha se **levanta** (`translateY(-1px)`) y sube a sombra
  media, en vez de teñirse. El movimiento comunica que es pulsable sin gastar
  color, y así el naranja se reserva para lo que está activo de verdad.
- **Pulsado:** se hunde (`scale(0.985)`). La respuesta ocurre mientras el dedo
  sigue abajo, no al soltar.
- **Foco:** aro de 2px en Ámbar Legible, separado 4px para rodear la ficha
  entera.

### Buscador

- **Estilo:** fondo papel cálido, 12px de radio, sin borde, con una lupa a la
  izquierda. Altura mínima de 44px.
- **Foco:** el cursor de texto va en Ámbar Legible; el campo no cambia de forma
  al enfocarse.

### Filtros de modo

Píldoras con el icono real de esa fuente al lado del texto, **el mismo con el
que se dibuja en el mapa**, para que la correspondencia entre botón y marcador
no haya que explicarla. El activo va sobre papel con texto en Ámbar Legible; el
resto son transparentes con tinta suave.

### Distintivo de línea

Píldora de 34px con el número de la línea, en el color oficial que viene del
GTFS y con su color de texto también del GTFS. **El color se aplica en línea,
no con una clase por línea**: son 603 líneas.

### Cabecera de marca

La única superficie de color pleno de la interfaz: banda naranja con el
logotipo en blanco centrado. En móvil hace además de **tirador** de la hoja, con
una barrita de 40×4px encima.

### Aviso de conexión

Va por encima de las tres vistas, porque el fallo puede ocurrir en cualquiera.
**No borra lo que hay debajo**: unos tiempos de hace treinta segundos informan
más que un panel vacío, mientras quede claro que son viejos.

## Do's and Don'ts

### Do:

- **Do** usar el par Naranja Marquesina + Tinta cuando el acento sea relleno, y
  Ámbar Legible cuando sea texto sobre blanco.
- **Do** separar bloques con hueco y sombra.
- **Do** dar radio a todo, proporcional a su tamaño.
- **Do** dejar los colores del GTFS y los corporativos tal como llegan.
- **Do** mantener 44px de área sensible en cualquier cosa que se pulse.
- **Do** acompañar cada estado de una alternativa con movimiento reducido: el
  cambio de estado se conserva, el desplazamiento se acorta.

### Don't:

- **Don't** poner texto blanco sobre el naranja de marca. Da 2:1 y es ilegible.
- **Don't** añadir bordes sólidos de 1px para separar. Ese trabajo lo hace la
  sombra.
- **Don't** usar los colores de sistema (verde, azul, rojo) para decorar:
  significan estado.
- **Don't** teñir de naranja una ficha al señalarla. El naranja es para lo
  activo; para lo señalado está el movimiento.
- **Don't** animar `width`, `height`, `padding` ni `margin`. Transformación y
  opacidad, que las mueve el compositor.
- **Don't** poner un elemento pulsable que no sea `<button>` o `<a>`.
