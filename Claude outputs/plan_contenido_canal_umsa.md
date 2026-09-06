# Plan de Contenido — Canal de Promoción UMSA 24/7

**Proyecto:** Negocios Digitales III
**Canal:** Transmisión continua de promoción institucional, todas las carreras de la UMSA
**Pipeline técnico:** Guion (OpenAI) → Locución sintetizada (ElevenLabs) → Emisión RTMP a YouTube (FFmpeg)

---

## 1. Visión general

El canal funciona como una señal institucional ininterrumpida que acompaña el ritmo del día universitario: informa por la mañana, orienta vocacionalmente al mediodía, difunde la vida académica por la tarde, profesionaliza la oferta de posgrado al final de la tarde, transmite eventos en vivo en el prime time, y por la noche se convierte en un espacio ambiental de estudio. La inteligencia artificial no reemplaza el contenido institucional: automatiza su producción (guion, locución, resúmenes, moderación) para que la señal nunca se corte y el equipo humano pueda enfocarse en curar la información y supervisar la calidad.

Cada franja horaria tiene un objetivo de negocio distinto (informar, captar postulantes, fidelizar comunidad, generar leads de posgrado, posicionar marca académica), y por lo tanto necesita su propio tipo de guion, su propia configuración de voz y sus propios activos de video.

---

## 2. Grilla de programación

| Franja horaria | Bloque temático | Contenido principal | Aporte de la IA | Objetivo de negocio |
|---|---|---|---|---|
| 07:00–10:00 | UMSA Despierta | Agenda del día, convocatorias, becas, novedades académicas, tips de estudio | Guion generado con las noticias del día; locución sintetizada | Información y retención diaria |
| 10:00–13:00 | Foco Grado y Vocación | Presentación de carreras (Abogacía, Contador Público, Artes Visuales, Psicología, Traductorado, Negocios Digitales) | Clips automáticos de testimonios de egresados y profesores | Captación de nuevos postulantes |
| 13:00–16:00 | Extensión y Comunidad | Charlas breves, eventos culturales de la Facultad de Artes, proyectos de investigación, convenios | Resumen automático de conferencias previas con subtitulado | Posicionamiento institucional y comunidad |
| 16:00–19:00 | Espacio Posgrados y Negocios | Maestrías, doctorados y especializaciones (Derecho, Fonoaudiología, Bioética, Museología) | Segmentos de valor profesional y entrevistas sintetizadas | Generación de leads de posgrado |
| 19:00–22:00 | Prime Time: Clases Abiertas | Retransmisión de webinars destacados, debates interdisciplinarios, paneles en vivo | Moderación de chat activa por bot IA y captura de leads | Engagement en vivo y conversión |
| 22:00–07:00 | UMSA Study Lounge | Transmisión tipo Lo-Fi / Focus Beats con fondo del campus, placas rotativas de oferta académica, datos curiosos | Música ambiental sin copyright y rotador automático de placas informativas | Marca de fondo, alcance nocturno de bajo costo |

---

## 3. Detalle de producción por bloque

### 07:00–10:00 · UMSA Despierta

Objetivo: que quien prenda el canal a primera hora reciba, en minutos, todo lo que necesita saber del día universitario.

Estructura del guion (aprox. 3–5 minutos, se repite en loop actualizándose cada 1–2 horas): apertura institucional breve, agenda del día (exámenes, inscripciones, trámites), convocatorias vigentes (becas, pasantías, intercambios), una novedad académica destacada, y cierre con un tip de estudio corto.

Flujo con IA: un prompt a OpenAI recibe como entrada las novedades del día (cargadas manualmente o desde una fuente institucional) y devuelve el guion en el tono definido; ElevenLabs lo convierte a audio con una voz fija "de conductor/a matutino" (cálida, clara, ritmo ágil); FFmpeg lo emite en loop con placas gráficas de apoyo (fecha, clima, agenda en pantalla).

Voz sugerida: una sola voz estable para todo el bloque, para generar identidad de "conductor" reconocible.

### 10:00–13:00 · Foco Grado y Vocación

Objetivo: que un estudiante indeciso vea, en algún momento de la franja, la carrera que le interesa presentada con contenido real (no solo un folleto leído).

Estructura: rotación de píldoras de 2–4 minutos, una por carrera, con testimonio de egresado o docente, datos concretos (duración, campo laboral, materias destacadas) y llamado a la acción (link de inscripción / información).

Flujo con IA: el guion de cada píldora se genera a partir de una ficha de la carrera (que arma el equipo del proyecto); los testimonios en video/audio existentes se recortan y se les agrega narración de contexto sintetizada; se arma automáticamente el rotador para que en 3 horas pasen las 6 carreras listadas al menos una vez.

Voz sugerida: voz distinta a la de la mañana, más "presentadora de carreras", puede variar levemente por facultad si se quiere dar identidad propia a cada área.

### 13:00–16:00 · Extensión y Comunidad

Objetivo: mostrar que la universidad no es solo aulas — hay investigación, cultura y vínculo con el entorno.

Estructura: resumen de charlas o conferencias ya grabadas (3–6 minutos cada una), agenda cultural de la Facultad de Artes, mención de convenios o proyectos de investigación en curso.

Flujo con IA: a partir de la grabación completa de una charla, se genera un resumen ejecutivo narrado (guion condensado con los puntos clave) y se agrega subtitulado automático para accesibilidad y para quienes miran sin audio.

### 16:00–19:00 · Espacio Posgrados y Negocios

Objetivo: captar perfiles profesionales que buscan especializarse (público más adulto, ya graduado).

Estructura: presentación de programas de posgrado (maestrías, doctorados, especializaciones) con foco en salida profesional concreta, entrevistas breves a coordinadores de posgrado.

Flujo con IA: guion con tono más ejecutivo/profesional que el bloque de grado; entrevistas existentes se sintetizan en cápsulas cortas con narración de enlace entre preguntas.

Voz sugerida: tono más formal y pausado que en la franja de grado, acorde al público objetivo.

### 19:00–22:00 · Prime Time: Clases Abiertas

Objetivo: la franja de mayor audiencia esperada — contenido en vivo real, no generado.

Estructura: retransmisión de webinars, paneles o debates en vivo o pregrabados de alto valor.

Flujo con IA: acá el aporte principal no es generar contenido sino sostener el vivo — un bot modera el chat (filtra spam, responde preguntas frecuentes tipo "¿cómo me inscribo?") y registra datos de contacto de quienes lo solicitan (captura de leads) para seguimiento posterior del área de admisiones.

Nota técnica: este es el único bloque que depende de que haya webinars/paneles reales programados; conviene definir con anticipación un calendario de estos eventos en vivo, ya que no se pueden generar sintéticamente sin perder el valor de "clase abierta real".

### 22:00–07:00 · UMSA Study Lounge

Objetivo: mantener el canal activo toda la noche con bajísimo costo operativo, generando marca constante (aparece en búsquedas, sostiene métricas de canal) sin necesitar guion nuevo cada noche.

Estructura: video de fondo del campus (loop visual tranquilo), música tipo lo-fi/focus beats de fondo, placas informativas rotativas (oferta académica, datos curiosos de la universidad, frases motivacionales) que cambian cada cierto intervalo.

Flujo con IA: generación o curación de música ambiental libre de derechos, y un rotador automático de placas (imágenes o texto en pantalla) que no requiere locución ni guion nuevo — es el bloque más "automatizable" de los seis y el que menos mantenimiento diario exige.

---

## 4. Flujo de producción general (cómo se conecta con el proyecto técnico)

1. Carga de insumos: cada bloque necesita una fuente de información de entrada (noticias del día, ficha de carrera, grabación de charla, datos de posgrado). Esto lo carga el equipo, no lo inventa la IA.
2. Generación de guion: `OPENAI_API_KEY` + `OPENAI_MODEL` (gpt-4o-mini) procesan el insumo con un prompt específico por bloque y devuelven el texto a locutar.
3. Síntesis de voz: `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID` (una voz por bloque o por conductor) convierten el guion en audio con `ELEVENLABS_MODEL_ID=eleven_multilingual_v2`.
4. Armado del video: se combina audio + placas/clips/fondo según el bloque (esto queda fuera del alcance de OpenAI/ElevenLabs — es edición/automatización de video).
5. Emisión: FFmpeg (`FFMPEG_BIN`/`FFPROBE_BIN`) transmite el resultado por RTMP (`RTMP_URL` + `RTMP_STREAM_KEY`) hacia YouTube Live, en loop o en vivo según el bloque.

---

## 5. Próximos pasos sugeridos

Definir primero las voces de ElevenLabs por bloque (idealmente 2 o 3 voces distintas para no sonar todo igual: una para la mañana informativa, una para presentación de carreras, una más formal para posgrados).

Armar las 6 fichas de carrera y la ficha base de cada programa de posgrado, que van a alimentar los prompts de OpenAI del bloque de las 10 a 13h y de 16 a 19h.

Definir el calendario de webinars/paneles reales para el bloque prime time, ya que es el único que no se puede automatizar del todo.

Probar de punta a punta un solo bloque (recomendado: UMSA Despierta, por ser el más simple: guion corto + una sola voz + loop) antes de escalar a los seis bloques completos.

---

*Documento vivo — actualizar a medida que se definan voces, fichas de carrera y calendario de eventos en vivo.*
