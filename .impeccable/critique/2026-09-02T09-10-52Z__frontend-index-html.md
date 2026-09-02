---
target: frontend/index.html
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 3
timestamp: 2026-09-02T09-10-52Z
slug: frontend-index-html
---
Método: dual-agent (A: revisión de diseño · B: detector + evidencia de navegador, aislados).

## Design Health Score

| # | Heurística | Score | Problema principal |
|---|---|---|---|
| 1 | Visibility of System Status | 2 | Sin indicador de frescura; nada indica carga mientras el CRTM tarda hasta 4,5 s |
| 2 | Match System / Real World | 3 | «comprueba que el backend está arrancado» es lenguaje de desarrollo, en producción |
| 3 | User Control and Freedom | 2 | «Volver» muerto al reentrar en la vista actual; sin historial, el gesto atrás sale de la app |
| 4 | Consistency and Standards | 2 | #f2f2f2 fuera de paleta en 4 superficies; buscador 40px contra 44 comprometidos; 📍 emoji |
| 5 | Error Prevention | 2 | Excelente en datos; la interfaz invita al atasco dejando el botón visible en su propia vista |
| 6 | Recognition Rather Than Recall | 3 | Iconos de red coherentes; «Cerca de ti» solo tras un emoji sin etiqueta |
| 7 | Flexibility and Efficiency | 2 | No hay URL de parada; filtros excluyentes: «accesible + urbano» imposible |
| 8 | Aesthetic and Minimalist Design | 1 | 6 elementos antes de la primera llegada; 62% del alto útil es cromo |
| 9 | Error Recovery | 2 | El aviso que no borra está bien juzgado; los alert() nativos rompen el sistema |
| 10 | Help and Documentation | 3 | Planos y tarifas con peso y vigencia; cero orientación inicial |
| Total | | 22/40 | Acceptable, parte baja |

## Especificidad

El producto está diseñado para sí mismo; lo construido hoy no, y se ha puesto delante. Autoría real:
Regla de los Dos Naranjas, rodeo 1,25 declarado como juicio, no pintar interurbanos por posiciones
congeladas, «Ya terminada» como estado, peso en MB antes del enlace. Pero la bandeja de 5 píldoras,
los dos botones grises con chevron y el campo gris son las 4 superficies más intercambiables del
producto, y ocupan el 100% de lo visible al abrir en móvil.

Detector: 14 hallazgos (no degradado tras instalar htmlparser2/css-select/css-tree/domutils).
3 falsos positivos (broken-image recibe src por JS; flat-type-hierarchy no ve el 26px inyectado,
real 2,36:1; nested-cards es el propio #panel). 1 desviación aceptada (Inter, compromiso legal).
5 derivas reales de radio (26px hoja, 14px bandeja, 11px chip, 6px code). 5 casos de DESIGN.md
obsoleto, incluido --gris-superficie #f2f2f2, token declarado que falta en el documento.

## Lo que funciona

1. El principio del dato viejo implementado de verdad: el aviso no vacía el panel; siguesMirando()
   protege los tres pollers.
2. «Ya terminada» como estado de aviso, con badge propio y contador que la excluye.
3. Teclado: 15 paradas, ciclo cerrado, foco visible en las 15. Cero errores de consola y cero
   peticiones fallidas.

## Problemas prioritarios

P0 — Lo que importa quedó debajo del pliegue.
333,5 px antes del primer resultado en escritorio (37,9% del panel). En móvil con hoja recogida
quedan 58,4 px: la primera ficha sale cortada. En llegadas, la primera llegada en el 62% de la
pantalla, detrás de dos botones ajenos a esa parada. → distill, luego layout

P1 — «Volver» se queda muerto (verificado en código).
mostrarVista() no oculta los dos botones; el handler escribe vistaAntesDeIncidencias sin comprobar
si ya estás en esa vista. Sin historial, la única salida es recargar. → harden

P1 — Sam no oye la mitad de lo construido para él.
El aria-label explícito de crearBotonDeResultado() sustituye al contenido: la píldora de
accesibilidad (con su .solo-lector) y la distancia andando son inaudibles. Los chips no llevan
aria-pressed. Las cinco vistas se intercambian sin mover el foco. → harden

P1 — El campo de búsqueda no parece el control principal.
Buscador y botón de planos comparten relleno, radio y ancho; el primario mide 40px y el secundario
44, incumpliendo la Regla del Pulgar propia. --texto-suave sobre #f2f2f2 da 4,37 (falla AA por
0,13) en las etiquetas de filtro inactivas; placeholder 2,91. → colorize

P2 — Copia que le habla a quien programa.
«Comprueba que el backend está arrancado» en producción; dos alert() nativos; «00:45» ambiguo
entre 45 segundos y las 00:45. → clarify

## Banderas rojas por persona

Sam (lector de pantalla): aria-label silencia distintivo de accesibilidad y distancia; 5 chips sin
aria-pressed; cambios de vista sin mover foco; títulos en <div>; 7 paradas de tabulación antes del
buscador; estrella sin marcar 2,11:1 contra el 3:1 de WCAG 1.4.11.

Casey (móvil a una mano): buscador por debajo del pliegue en reposo; botón de ubicación es un 📍
emoji pelado y única puerta a «Cerca de ti»; buscador de 40px; «Interurbano» trunca a 390px;
alert() imposible de descartar con el pulgar.

Marta (trayecto de siempre): no existe URL de parada, así que no puede marcarla ni añadirla a la
pantalla de inicio; su favorito sigue estando debajo de toda la cabecera; sin indicador de frescura;
paga «Planos y tarifas» dos veces al día para siempre.

## Observaciones menores

- «Próximas llegadas» duplicado como subtítulo y como título de sección.
- Tres redacciones del mismo contador; si los 4 avisos son programados, el ámbar exagera el presente.
- titular() salta las palabras que no están enteras en mayúsculas: «Puerta del Sol/sevilla -
  Estacion de Chamartin» sobrevive con caja mezclada y sin tildes.
- El 📍 emoji contradice el criterio del propio botón de avisos.

## Preguntas

1. Si gana el viajero, ¿por qué un botón sobre planos en papel va por encima del tiempo del autobús?
2. «Accesibles» siempre significa Metro: ¿por qué es un quinto modo excluyente y no un interruptor
   que componga? ¿Qué concluye alguien en silla buscando una parada de bus accesible?
3. El principio 2 exige decir cuándo un dato es viejo. Hoy entraron dos vistas y el indicador de
   frescura sigue sin existir. ¿Cuál de las tres necesitaba la persona de la parada?
