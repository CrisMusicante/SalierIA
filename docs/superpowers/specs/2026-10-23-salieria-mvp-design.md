# SalierIA — Diseño: visión por fases y alcance del MVP

Fecha: 2026-10-23 · Autor: CrisMusicante (con Claude)

## 1. Intención y el porqué

SalierIA ("Salieri") es un asistente musical conversacional, en el estilo de Jarvis, para componer y arreglar. Su dueño es compositor y arreglista. Trabaja en una Yamaha Clavinova CLP-220 conectada por MIDI/audio a una Focusrite Scarlett 4i4, y escribe en Sibelius 8.2 (Windows).

**El dolor concreto:** las alturas se meten tocando el piano por MIDI, pero los ritmos, compases, silencios, maquetación y ediciones (retrogradar, transportar, copiar/pegar, etc.) obligan a soltar el piano e ir al teclado y al ratón, y a buscar en menús escondidos durante minutos. Eso **interrumpe el flujo de inspiración**. El valor del producto está en que las manos se quedan en el piano y la voz hace el resto.

**La motivación de fondo:** ningún editor convence al 100 %. El asistente debe terminar superándolos a todos y rescatar lo mejor de cada uno:

| Editor | Rescatar | Evitar |
|---|---|---|
| Sibelius | Potencia técnica: transportar, retrogradar, cambiar instrumento/librería, mezcla in situ; resultado profesional; NotePerformer | Interfaz poco intuitiva, menús escondidos |
| MuseScore | Gratuito, intuitivo | Maquetación por debajo del estándar del conservatorio |
| LilyPond | Experimental, flexible, componer en vivo, notación no convencional, visuales | La barrera técnica |

La vara de calidad para la maquetación es **el estándar del conservatorio**.

## 2. Fases

1. **Fase 1 — MVP:** asistente de voz para **dictar estructura y ejecutar ediciones** sobre Sibelius 8.2. *(Este documento la detalla.)*
2. **Fase 2:** escuchar el instrumento, capturar el ritmo exacto desde el MIDI de la Clavinova y luego transcribir desde audio.
3. **Fase 3:** motor o editor propio que supere a los existentes. Sibelius pasa a ser una salida entre varias (MusicXML, MuseScore, LilyPond).

El orden fue acordado con el dueño. El MVP debe diseñarse para no estorbar a las fases 2 y 3 (ver §7).

## 3. MVP — Objetivos

Con las manos en el piano, el dueño le habla a Salieri y este modifica la partitura abierta en Sibelius 8.2 con exactitud, más rápido que hacerlo a mano.

### 3.1 Operaciones del MVP

Las pidió el dueño, salvo donde se indica.

**Estructura**
- Agregar y eliminar compases completos.
- Cifra de compás, armadura y tempo.
- Silencios.

**Edición de pasajes**
- Copiar y pegar en una posición exacta. *Decisión mía:* el pegado reemplaza lo que haya en el destino, como hace Sibelius normalmente.
- Transportar por intervalo.
- Retrogradar (ver la regla más abajo).
- Cambiar las duraciones de notas existentes. Ejemplo: "compases 3 a 6 en corcheas". Es la vía para dar ritmo a lo que se metió por MIDI (ver el flujo actual más abajo).

**Cómo mete hoy las notas el dueño:** nota por nota en Sibelius (step-time). Primero elige la figura y después toca las notas, y cambia de figura a mano cada vez. El MVP quiere eliminar esos cambios manuales: tocar las alturas con cualquier figura y luego dictar el ritmo.

**Regla para cambiar duraciones y para silencios:** si el resultado no cabe en el rango (por ejemplo, 16 negras pasadas a corcheas ocupan solo 2 de 4 compases, o al revés, se desbordan), el asistente **no ejecuta**. Avisa, pregunta si la orden era correcta y propone salidas: recorrer la música siguiente, rellenar con silencios o invadir lo que sigue. Aplica lo que el dueño elija. Lo mismo vale para los silencios, sean convertir notas en silencios o insertarlos: si cambian la cantidad de tiempos del rango, pregunta.

**Regla para retrogradar:** retrógrado **estricto de alturas y ritmo**.
- Las ligaduras no se trasladan. Las reescribe el dueño después, y el asistente lo menciona en la confirmación como un aviso breve, por ejemplo "las ligaduras no se copiaron".
- *Decisión mía:* los acordes se invierten como bloque, y las dinámicas y articulaciones no se trasladan y entran en el mismo aviso.

**Expresión** (por compás o rango)
- Dinámicas y reguladores.
- Ligaduras.
- Articulaciones.

**Instrumentación**
- Agregar instrumentos.
- Cambiar un instrumento por otro.

**Transversal**
- Órdenes compuestas: varias operaciones en una sola frase (§3.3).
- "Deshaz eso", que revierte la **orden completa** y no solo el último paso.
- Corrección barata: "no, era el compás 16" corrige la última orden sin repetirla entera.

### 3.2 Cómo se señala un pasaje

- **Por compás y tiempo**, con inicio y fin: "desde el segundo tiempo del compás 5 hasta el último tiempo del compás 10".
- **Por instrumento**, con el nombre que tiene en la partitura: "en el violín 1, compases 5 a 8".
- **Por pentagrama y voz** cuando el instrumento tiene varios pentagramas. Ejemplos: "piano mano derecha", "pentagrama de arriba" o "pentagrama en clave de sol", y "voz 1". El dueño quiere **precisión**: si dice solo "el piano", el asistente **pregunta** qué pentagrama y qué voz en lugar de suponer.
- *Decisión mía:* si no se nombra instrumento, la orden aplica al último mencionado, o al único si la partitura tiene uno solo, siempre que eso no sea ambiguo según la regla anterior. La confirmación hablada siempre dice el instrumento, el pentagrama, la voz y el rango que se usaron.
- Las referencias relativas ("lo que acabo de tocar", "esto") quedan fuera del MVP.

### 3.3 Ejemplo de referencia (el caso de prueba principal)

> "Salieri, el motivo que inicia en el segundo tiempo del compás 5 y termina en el último tiempo del compás 10, cópialo y pégalo en el compás 15 desde el primer tiempo, pero ahora un tono más arriba y en retrógrado."

Se descompone en: (1) seleccionar 5:2 a 10:último tiempo, (2) copiar, (3) retrogradar, (4) transportar una segunda mayor arriba, (5) pegar en 15:1.

### 3.4 Interacción por voz

- **Activación:** palabra clave **"Salieri"**, sin manos. *Decisión mía:* el fin de la frase se detecta por silencio, sin palabra de cierre. Requisito: el piano sonando no debe disparar la activación ni cortar la frase.
- **Respuesta hablada:** breve. Resume la orden y **enumera los pasos uno por uno**, sin charla. Ejemplo: *"Violín 1. Uno: seleccionar 5:2 a 10. Dos: copiar. Tres: retrogradar. Cuatro: subir un tono. Cinco: pegar en 15:1. Listo."*
- **Dos modos, elegibles en Preferencias:**
  - *Actuar y anunciar* (por defecto, decisión mía): ejecuta y narra.
  - *Anunciar y esperar*: dice los pasos y espera "sí" o una corrección.
- **En cualquiera de los dos modos, pregunta** cuando la orden es ambigua (por ejemplo "el piano" sin pentagrama) o imposible tal como se dijo (por ejemplo, duraciones que no caben). Fuera de esos casos no pregunta.
- **Tiempo de respuesta:** *decisión mía*, la meta es unos 3 s entre el fin de la frase y el resultado en la partitura.
- Idioma: español, con vocabulario musical preciso (solfeo, figuras, intervalos, "retrógrado", tiempos y compases).

### 3.5 Preferencias

Un panel de preferencias existe desde el MVP. Como mínimo debe tener:
- Modo de ejecución (§3.4).
- **Proveedor y modelo de IA con su API key.** Debe admitir Claude y los endpoints de NVIDIA (build.nvidia.com / NIM). El dueño tiene keys gratuitas de NVIDIA y no quiere atarse a Claude.
- Velocidad de la voz.
- **Entrada y salida de audio configurables:** dispositivo y canal de entrada para la voz, y dispositivo de salida para la voz de Salieri (bocinas o audífonos). En el equipo del dueño:
  - La voz entra por el **canal 1 de la Scarlett 4i4**. La PC no tiene entrada de micrófono propia, pero otras PCs podrían usar la suya.
  - El piano entra por **MIDI-USB** y su audio por los **canales 3-4** de la Scarlett.
  - La palabra clave y el reconocimiento escuchan solo el canal de voz, lo que ayuda a ignorar el piano.
- Motor de reconocimiento de voz, configurable. **La PC no tiene GPU NVIDIA**, así que el reconocimiento local corre en CPU. El constructor elige un motor local que cumpla la meta de ~3 s en CPU, y ofrece el ASR en la nube de NVIDIA (Parakeet/Riva, con las keys del dueño) como alternativa.

### 3.6 Batería de pruebas de órdenes

Un conjunto de órdenes habladas o transcritas, cada una con el resultado esperado en la partitura. El ejemplo de §3.3 es la primera. Sirve para comparar modelos y proveedores con datos y para evitar regresiones. *Idea mía, alineada con el antiobjetivo de §5.*

*Decisión mía:*
- El constructor arma la primera versión con los ejemplos de esta conversación y el dueño le agrega sus frases reales.
- La prueba automática valida la descomposición en operaciones y el estado del modelo musical en Python, sin necesidad de Sibelius.
- La verificación en la partitura real de Sibelius es manual, con un subconjunto de órdenes.

## 4. No-objetivos del MVP

- Capturar el ritmo exacto desde el MIDI de la Clavinova (fase 2). En el MVP las alturas se siguen metiendo por MIDI en Sibelius como hoy.
- Controlar Flexi-time. Se quiere como herramienta futura, pero Sibelius 8.2 no lo expone a plugins (§6).
- Transcribir desde audio (fase 2).
- Editor o motor propio y salidas a MuseScore o LilyPond (fase 3).
- Maquetación avanzada (espaciado, saltos de sistema y de página).
- Mac, otras máquinas e instaladores. Solo el PC Windows del dueño.
- Referencias relativas ("esto", "lo que acabo de tocar").

## 5. Antiobjetivos

El producto fracasa aunque técnicamente funcione si:

- **Dar la indicación o corregirla cuesta tanto tiempo como hacerlo a mano.** Una orden que necesita tres intentos para salir bien perdió.
- **Hace algo distinto de lo pedido sin que sea evidente**, o sin poder deshacerlo.
- Obliga a soltar el piano en el uso normal.

(Al dueño le preocupa menos que actúe sin preguntar, siempre que se pueda deshacer.)

## 6. Restricciones

- **Windows 11, Sibelius 8.2.0.** No hay actualización de Sibelius por ahora.
- **Lo que permite ManuScript en esta generación.** Fuente: el manual oficial de ManuScript 2018.1, el más cercano disponible a 8.2.
  - **Sí permite:** `Selection.Copy` / `PasteToPosition(stave, bar, position)`; `Transpose(degree, interval type)` sobre selección y notas; `Bar.AddNote(pos, pitch, duration, …)`, `AddTuplet`, `AddTimeSignature`, `AddKeySignature`; lectura y escritura de archivos de texto (`ReadTextFile`, `CreateTextFile`, `AppendTextFile`); `Play()` / `Stop()`.
  - **No permite:**
    - Ningún temporizador ni callback: un plugin no puede quedarse escuchando en segundo plano.
    - `Sibelius.Execute()` para ejecutar comandos de menú, que llegó en 2021.2.
    - Sibelius Connect, el control remoto, que llegó en 2024.3.
    - Control de Flexi-time.
    - Una función de retrogradar (hay que implementarla leyendo las notas y reescribiéndolas).
- **Consecuencia:** la arquitectura actual del repo, con un plugin que sondea un archivo cada 500 ms, **no puede funcionar**. Además, el `.plg` actual usa funciones que no existen en ManuScript (`SetTimerAction`, `GetEnvironmentVariable`, `SaveTextFile`, `Sibelius.Undo`). Hay que tratarlo como un borrador que nunca se probó.
- **Enfoque de integración propuesto** *(decisión mía; validar con un spike al inicio)*: cada orden se ejecuta lanzando el plugin con un atajo de teclado asignado en Sibelius. El asistente escribe la orden en un archivo, envía el atajo a la ventana de Sibelius, el plugin lee, ejecuta, escribe la respuesta y termina. Riesgos a validar:
  - El foco de la ventana.
  - Si cada ejecución del plugin queda como **un solo paso de deshacer** en Sibelius, de lo que depende "deshaz eso".
  - La latencia.
  - Que Sibelius no muestre diálogos.
- **Plan B** *(decisión mía)*:
  - Si una ejecución del plugin no queda como un solo paso de deshacer, el asistente lleva la cuenta de los pasos de cada orden y "deshaz eso" envía esa cantidad de Ctrl+Z.
  - Si el disparo por atajo resulta inviable, hay que volver con el dueño antes de cambiar de enfoque, porque la alternativa (automatizar la interfaz con pywinauto) es más frágil.
- Los proveedores de IA son intercambiables. No todos los modelos son igual de buenos con órdenes compuestas, y se elige con la batería de §3.6.

## 7. Decisiones de forma ya tomadas

- **Qué se reutiliza del repo:** Python, el pipeline voz → transcripción → IA con herramientas → Sibelius → voz, y el esquema de herramientas `docs/tools.json`. El esquema se amplía con retrogradar, copiar/pegar a posición, cambiar duraciones, ligaduras, cambiar/agregar instrumento y eliminar compases.
- **Qué se reemplaza:** la activación con F9 se cambia por la palabra clave, y el puente de archivos con sondeo por el disparo del plugin con atajo (§6).
- *Decisión mía, pensando en las fases 2 y 3:* la lógica musical (coordenadas compás:tiempo, intervalos, retrógrado, duraciones) vive en el lado de Python como un modelo propio. El plugin de Sibelius queda como un ejecutor delgado. Así, después, otro destino (MusicXML, LilyPond) puede reemplazar o acompañar a Sibelius sin rehacer el cerebro.

## 8. Lo que queda al constructor

- La librería de palabra clave, la detección de fin de frase y cómo filtrar el sonido del piano.
- El formato exacto del archivo de orden y respuesta, y cómo el asistente conoce el estado de la partitura (instrumentos, número de compases, cifra) leyéndolo de Sibelius.
- El modelo por defecto de cada proveedor, y cómo se guardan las preferencias y las keys (fuera del repo).
- La forma del panel de preferencias (bandeja del sistema, archivo o ventana).
- Cómo se reparte la orden compuesta entre la IA (descomponer) y el código (ejecutar y validar).
- Qué hacer con el código actual que no sirva (parser, plugin).
