"""
scripts/generar_sitio.py — Genera la página pública del canal en español e inglés:
video en vivo, manual y los dos grafos (funcionamiento e información).

    python scripts/generar_sitio.py

Escribe app/static/sitio_es.html y app/static/sitio_en.html. Los dos idiomas
comparten la posición de los nodos y las conexiones (solo cambian los textos),
así un grafo no se desarma al traducirlo. Todos los nodos llevan su nombre.

El video no se escribe acá: la página trae el marcador __VIDEO__, que
app/web.py reemplaza al servir según YOUTUBE_CHANNEL_ID (ver .env.example).
Después de cambiar este archivo, volver a correrlo y commitear los dos HTML:
tests/test_sitio.py falla si quedaron desactualizados.
"""
from __future__ import annotations

import sys
import textwrap
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "app" / "static"

# --------------------------------------------------------------------------
# Grafo de funcionamiento: fuentes → procesos → datos guardados → lo que publica.
# (id, columna, fila, tipo)
# --------------------------------------------------------------------------
NODOS_FUNC = [
    ("op", 0, 0, "fuente"),
    ("llm", 0, 1, "fuente"),
    ("piper", 0, 2, "fuente"),
    ("placas", 0, 3, "fuente"),
    ("reloj", 0, 4, "fuente"),
    ("clip", 1, 1, "proceso"),
    ("sched", 1, 3, "proceso"),
    ("stream", 1, 4.5, "proceso"),
    ("wd", 1, 5.6, "proceso"),
    ("audio", 2, 0.4, "dato"),
    ("videos", 2, 1.6, "dato"),
    ("playlist", 2, 3, "dato"),
    ("yt", 3, 3.6, "publica"),
    ("api", 3, 4.8, "publica"),
    ("web", 3, 6, "publica"),
]
ARISTAS_FUNC = [
    ("op", "clip"), ("llm", "clip"), ("piper", "clip"), ("placas", "clip"),
    ("clip", "audio"), ("clip", "videos"), ("clip", "playlist"),
    ("reloj", "sched"), ("videos", "sched"), ("sched", "playlist"),
    ("playlist", "stream"), ("wd", "stream"),
    ("stream", "yt"), ("stream", "api"), ("yt", "web"), ("api", "web"),
]
TEXTOS_FUNC = {
    "es": {
        "op": ("Operador", ["Swagger o scripts .ps1"]),
        "llm": ("Anthropic u OpenAI", ["redactan el guion"]),
        "piper": ("Piper", ["voz sintetizada local"]),
        "placas": ("Placas institucionales", ["media/placas"]),
        "reloj": ("Reloj", ["hora argentina"]),
        "clip": ("POST /ai/clip", ["guion → voz → video"]),
        "sched": ("Scheduler de bloques", ["revisa cada 60 s"]),
        "stream": ("Streamer ffmpeg", ["emite sin recodificar"]),
        "wd": ("Watchdog", ["revisa cada 15 s"]),
        "audio": ("media/audio", ["voces .wav"]),
        "videos": ("media/videos", ["clips .mp4"]),
        "playlist": ("playlist.txt", ["lo que se emite ahora"]),
        "yt": ("YouTube Live", ["señal RTMP 24/7"]),
        "api": ("API de estado", ["/api/v1/stream/…"]),
        "web": ("Esta página", ["video, manual y grafos"]),
    },
    "en": {
        "op": ("Operator", ["Swagger or .ps1 scripts"]),
        "llm": ("Anthropic or OpenAI", ["write the script"]),
        "piper": ("Piper", ["local synthesized voice"]),
        "placas": ("Institutional slides", ["media/placas"]),
        "reloj": ("Clock", ["Argentina time"]),
        "clip": ("POST /ai/clip", ["script → voice → video"]),
        "sched": ("Block scheduler", ["checks every 60 s"]),
        "stream": ("ffmpeg streamer", ["streams without re-encoding"]),
        "wd": ("Watchdog", ["checks every 15 s"]),
        "audio": ("media/audio", [".wav voices"]),
        "videos": ("media/videos", [".mp4 clips"]),
        "playlist": ("playlist.txt", ["what is on air now"]),
        "yt": ("YouTube Live", ["24/7 RTMP signal"]),
        "api": ("Status API", ["/api/v1/stream/…"]),
        "web": ("This page", ["video, manual and graphs"]),
    },
}
COLUMNAS_FUNC = {
    "es": ["Fuentes", "Procesos", "Datos guardados", "Lo que publica"],
    "en": ["Sources", "Processes", "Stored data", "What it publishes"],
}

# --------------------------------------------------------------------------
# Grafo de información: bloque de la grilla ↔ carreras que emite. Sale de
# GRILLA (app/core/scheduler.py) y del catálogo (app/core/catalogo.py): no
# hay una tercera copia de la oferta académica que se pueda desactualizar.
# --------------------------------------------------------------------------
sys.path.insert(0, str(RAIZ))
from app.core.catalogo import FACULTADES, PROGRAMAS  # noqa: E402
from app.core.scheduler import GRILLA  # noqa: E402

_NOMBRES_EN_OTROS = {
    "UMSA Despierta": "UMSA Wakes Up",
    "Prime Time: Clases Abiertas": "Prime Time: Open Classes",
    "UMSA Nocturno": "UMSA Night",
}
BLOQUE_EN = {
    b.nombre: (FACULTADES[b.facultad].nombre_en if b.facultad else _NOMBRES_EN_OTROS[b.nombre]) for b in GRILLA
}
# id, nombre, franja, prefijos, facultad
BLOQUES = [
    (f"b{i}", b.nombre, f"{b.hora_inicio:02d}–{b.hora_fin:02d} h", b.prefijos, b.facultad) for i, b in enumerate(GRILLA)
]
MODALIDAD_EN = {
    "presencial": "in person",
    "virtual": "online",
    "a distancia": "distance learning",
    "presencial o virtual": "in person or online",
    "presencial o a distancia": "in person or distance learning",
}
# id, bloque, texto es, texto en, detalle es, detalle en
CONTENIDOS = [
    ("agenda", "b0", "Agenda, becas y convocatorias", "Agenda, grants and calls", "umsa_despierta_*", "umsa_despierta_*"),
    *[
        (p.nombre_archivo, next(b[0] for b in BLOQUES if b[4] == p.facultad), p.nombre, p.nombre_en,
         f"{p.nivel.capitalize()} · {p.modalidad}",
         f"{'Undergraduate' if p.nivel == 'grado' else 'Graduate'} · {MODALIDAD_EN[p.modalidad]}")
        for p in PROGRAMAS
    ],
    ("rotacion", None, "Rotación de todas las carreras", "Rotation of all programs",
     "de 22 a 7 h y en los bloques sin clips propios", "22–07 h and blocks without their own clips"),
]
COLUMNAS_INFO = {"es": ["Bloque de la grilla", "Carreras que emite"], "en": ["Schedule block", "Programs it streams"]}

# --------------------------------------------------------------------------
# Dibujo SVG
# --------------------------------------------------------------------------
ANCHO_NODO, ALTO_NODO = 220, 50
COLORES = {"fuente": "c-fuente", "proceso": "c-proceso", "dato": "c-dato", "publica": "c-publica", "bloque": "c-proceso", "contenido": "c-dato"}


def _pos(col: float, fila: float, x0: int, paso_x: int, y0: int, paso_y: int) -> tuple[float, float]:
    return x0 + col * paso_x, y0 + fila * paso_y


def _nodo_svg(
    x: float, y: float, tipo: str, titulo: str | list[str], lineas: list[str], ancho: int = ANCHO_NODO, alto: int = ALTO_NODO
) -> str:
    """`titulo` puede venir ya partido en varias líneas (nombres de carrera largos)."""
    titulos = [titulo] if isinstance(titulo, str) else titulo
    partes = [
        f'<g class="nodo {COLORES[tipo]}">',
        f'<rect x="{x:.0f}" y="{y:.0f}" width="{ancho}" height="{alto}" rx="8"/>',
    ]
    if len(titulos) == 1 and alto == ALTO_NODO:  # caja estándar: misma disposición que siempre
        partes.append(f'<text x="{x + 10:.0f}" y="{y + (21 if lineas else 30):.0f}" class="t1">{escape(titulos[0])}</text>')
        y_lineas = y + 39
    else:
        for i, t in enumerate(titulos):
            partes.append(f'<text x="{x + 10:.0f}" y="{y + 19 + 17 * i:.0f}" class="t1">{escape(t)}</text>')
        y_lineas = y + 19 + 17 * len(titulos) + 2
    for i, linea in enumerate(lineas):
        partes.append(f'<text x="{x + 10:.0f}" y="{y_lineas + 14 * i:.0f}" class="t2">{escape(linea)}</text>')
    partes.append("</g>")
    return "".join(partes)


def _arista_svg(a: tuple[float, float], b: tuple[float, float], alto_a: float = ALTO_NODO, alto_b: float = ALTO_NODO) -> str:
    (ax, ay), (bx, by) = a, b
    if bx > ax:  # hacia adelante: borde derecho → borde izquierdo
        x1, y1, x2, y2 = ax + ANCHO_NODO, ay + alto_a / 2, bx, by + alto_b / 2
        c = (x2 - x1) / 2
        d = f"M{x1:.0f},{y1:.0f} C{x1 + c:.0f},{y1:.0f} {x2 - c:.0f},{y2:.0f} {x2 - 4:.0f},{y2:.0f}"
    elif bx < ax:  # hacia atrás: borde izquierdo → borde derecho
        x1, y1, x2, y2 = ax, ay + ALTO_NODO / 2, bx + ANCHO_NODO, by + ALTO_NODO / 2
        c = max(40, (x1 - x2) / 2)
        d = f"M{x1:.0f},{y1:.0f} C{x1 - c:.0f},{y1:.0f} {x2 + c:.0f},{y2:.0f} {x2 + 4:.0f},{y2:.0f}"
    else:  # misma columna: abajo → arriba o al revés
        x1 = x2 = ax + ANCHO_NODO / 2
        y1, y2 = (ay, by + ALTO_NODO + 4) if by < ay else (ay + ALTO_NODO, by - 4)
        d = f"M{x1:.0f},{y1:.0f} L{x2:.0f},{y2:.0f}"
    return f'<path d="{d}" class="arista" marker-end="url(#flecha)"/>'


def _svg(ancho: int, alto: int, aria: str, cuerpo: list[str]) -> str:
    defs = (
        '<defs><marker id="flecha" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="punta"/></marker></defs>'
    )
    return (
        f'<svg viewBox="0 0 {ancho} {alto}" style="max-width:{ancho}px" role="img" aria-label="{escape(aria)}">{defs}' + "".join(cuerpo) + "</svg>"
    )


def grafo_funcionamiento(lang: str) -> str:
    x0, px, y0, py = 10, 260, 50, 74
    pos = {n: _pos(c, f, x0, px, y0, py) for n, c, f, _ in NODOS_FUNC}
    cuerpo = [
        f'<text x="{x0 + i * px + ANCHO_NODO / 2:.0f}" y="24" class="col">{escape(t)}</text>'
        for i, t in enumerate(COLUMNAS_FUNC[lang])
    ]
    cuerpo += [_arista_svg(pos[a], pos[b]) for a, b in ARISTAS_FUNC]
    for n, _, _, tipo in NODOS_FUNC:
        titulo, lineas = TEXTOS_FUNC[lang][n]
        cuerpo.append(_nodo_svg(*pos[n], tipo, titulo, lineas))
    aria = "Grafo de funcionamiento del canal" if lang == "es" else "How the channel works graph"
    return _svg(x0 + 3 * px + ANCHO_NODO + 10, int(y0 + 6 * py + ALTO_NODO + 16), aria, cuerpo)


ANCHO_CONTENIDO, CARACTERES_LINEA = 470, 58  # caja de carrera: nombres largos en hasta 2-3 líneas


def _lineas_titulo(contenido: tuple, lang: str) -> list[str]:
    return textwrap.wrap(contenido[2] if lang == "es" else contenido[3], CARACTERES_LINEA)


def _layout_informacion() -> tuple[dict, dict, float]:
    """Posición y alto de cada caja. Se calcula con el MÁS LARGO de los dos
    idiomas, para que español e inglés compartan exactamente el mismo dibujo."""
    x0, x1, y0, sep = 10, 330, 50, 8
    pos, alto, y = {}, {}, y0
    bloque_anterior = None
    for c in CONTENIDOS:
        if c[1] != bloque_anterior:
            y += 14 if bloque_anterior is not None else 0  # aire entre facultades
            bloque_anterior = c[1]
        n = max(len(_lineas_titulo(c, "es")), len(_lineas_titulo(c, "en")))
        alto[c[0]] = 19 + 17 * n + 14
        pos[c[0]] = (x1, y)
        y += alto[c[0]] + sep
    # Cada bloque se centra frente a sus carreras; los que no tienen carreras
    # propias (Prime Time, Nocturno) van frente a la rotación.
    for bid, *_ in BLOQUES:
        hijos = [c[0] for c in CONTENIDOS if c[1] == bid] or ["rotacion"]
        arriba, abajo = pos[hijos[0]][1], pos[hijos[-1]][1] + alto[hijos[-1]]
        pos[bid] = (x0, (arriba + abajo) / 2 - ALTO_NODO / 2)
        alto[bid] = ALTO_NODO
    # Prime Time y Nocturno comparten la caja de la rotación: se separan.
    vacios = [b[0] for b in BLOQUES if not any(c[1] == b[0] for c in CONTENIDOS)]
    for i, bid in enumerate(vacios):
        pos[bid] = (x0, pos[bid][1] + (i - (len(vacios) - 1) / 2) * (ALTO_NODO + 10))
    return pos, alto, max(pos[k][1] + alto[k] for k in pos)  # ninguna caja queda cortada abajo


def grafo_informacion(lang: str) -> str:
    pos, alto, y_fin = _layout_informacion()
    x0, x1 = 10, 330
    cuerpo = [
        f'<text x="{x0 + ANCHO_NODO / 2:.0f}" y="24" class="col">{escape(COLUMNAS_INFO[lang][0])}</text>',
        f'<text x="{x1 + ANCHO_CONTENIDO / 2:.0f}" y="24" class="col">{escape(COLUMNAS_INFO[lang][1])}</text>',
    ]
    for c in CONTENIDOS:
        if c[1]:
            cuerpo.append(_arista_svg(pos[c[1]], pos[c[0]], alto[c[1]], alto[c[0]]))
    for bid, *_ in BLOQUES:
        if not any(c[1] == bid for c in CONTENIDOS):
            cuerpo.append(_arista_svg(pos[bid], pos["rotacion"], alto[bid], alto["rotacion"]))
    archivo = "archivos" if lang == "es" else "files"
    for bid, nombre, franja, prefijos, _ in BLOQUES:
        titulo = nombre if lang == "es" else BLOQUE_EN[nombre]
        detalle = f"{franja} · {archivo} {prefijos[0]}*" if len(prefijos) == 1 else franja
        cuerpo.append(_nodo_svg(*pos[bid], "bloque", titulo, [detalle]))
    for c in CONTENIDOS:
        detalle = c[4] if lang == "es" else c[5]
        cuerpo.append(
            _nodo_svg(*pos[c[0]], "contenido", _lineas_titulo(c, lang), [detalle], ancho=ANCHO_CONTENIDO, alto=alto[c[0]])
        )
    aria = (
        "Grafo de información: bloques de la grilla y las carreras que emite cada uno"
        if lang == "es"
        else "Information graph: schedule blocks and the programs each one streams"
    )
    return _svg(x1 + ANCHO_CONTENIDO + 10, int(y_fin + 10), aria, cuerpo)


# --------------------------------------------------------------------------
# Textos del manual
# --------------------------------------------------------------------------
def _filas_grilla(lang: str) -> str:
    filas = []
    for _, nombre, franja, prefijos, _ in BLOQUES:
        titulo = nombre if lang == "es" else BLOQUE_EN[nombre]
        archivos = " ".join(f"<code>{escape(p)}*</code>" for p in prefijos)
        filas.append(f"<tr><td>{escape(franja)}</td><td>{escape(titulo)}</td><td>{archivos}</td></tr>")
    return "".join(filas)


TEXTOS = {
    "es": {
        "titulo": "UMSA Vivo & Conectada",
        "subtitulo": "Canal institucional de la UMSA que transmite las 24 horas en YouTube Live.",
        "nav": [("video", "Video en vivo"), ("manual", "Manual"), ("grafos", "Grafos")],
        "otro_idioma": ("/en", "English"),
        "estado_titulo": "Estado de la emisión",
        "estado_cargando": "Consultando…",
        "estado_al_aire": "Al aire",
        "estado_detenida": "Detenida",
        "estado_error": "No se pudo consultar el estado.",
        "bloque_actual": "Bloque según la hora",
        "subs_vacio": "Acá aparecen los subtítulos de lo que se está emitiendo.",
        "manual": """
<h2 id="manual">Manual</h2>
<h3>Qué es</h3>
<p>Un servicio que mantiene al aire, sin interrupciones, el canal de YouTube de la UMSA (Universidad del Museo Social Argentino).
Toma clips de video ya preparados y los emite en loop con ffmpeg. La programación cambia sola según la hora argentina, siguiendo una grilla de seis bloques.</p>
<p>Los clips nuevos se pueden producir con inteligencia artificial: un modelo de lenguaje redacta el guion, Piper lo convierte en voz (corre en el propio servidor, sin costo por uso) y ffmpeg arma el video con una placa institucional de fondo.</p>

<h3>Cómo ver la transmisión</h3>
<p>Arriba está el reproductor del canal en vivo. Al lado se ve si el servicio está emitiendo y qué bloque corresponde a la hora actual. Si el reproductor dice que no hay transmisión, el canal todavía no se configuró en esta página (variable <code>YOUTUBE_CHANNEL_ID</code>) o la emisión está detenida.</p>
<p>Debajo del reproductor aparecen los subtítulos de lo que se está emitiendo (en inglés en la <a href="/en">versión en inglés</a> de esta página). Se calculan en el servidor a partir del guion de cada clip, así que pueden adelantarse o atrasarse unos segundos respecto del video de YouTube. Los videos propios, cargados sin pasar por la IA, no tienen subtítulos.</p>

<h3>Grilla de programación</h3>
<table><thead><tr><th>Franja (hora argentina)</th><th>Bloque</th><th>Archivos que emite</th></tr></thead><tbody>__GRILLA__</tbody></table>
<p>Durante el día, cada una de las cinco facultades tiene su franja con todas sus carreras de grado y posgrado. De 22 a 7 se rotan todas las carreras de la universidad. Cada bloque emite los clips cuyo nombre empieza con su prefijo. Prime Time todavía no tiene contenido propio: mientras tanto, como cualquier bloque vacío, emite la rotación de todas las carreras.</p>

<h3>Cómo funciona</h3>
<p>El <a href="#grafo-funcionamiento">grafo de funcionamiento</a> se lee de izquierda a derecha:</p>
<ul>
<li><strong>Fuentes:</strong> el operador (desde Swagger o con los scripts <code>.ps1</code>), el modelo de lenguaje (Anthropic, con OpenAI como respaldo), Piper para la voz, las placas institucionales y el reloj en hora argentina.</li>
<li><strong>Procesos:</strong> <code>POST /ai/clip</code> encadena guion, voz y video. El scheduler revisa cada minuto qué bloque corresponde y reescribe la playlist. El streamer es ffmpeg emitiendo sin recodificar, y el watchdog lo reinicia si se cae solo.</li>
<li><strong>Datos guardados:</strong> las voces en <code>media/audio</code>, los clips en <code>media/videos</code> y la lista de lo que se emite en <code>playlist.txt</code>.</li>
<li><strong>Lo que publica:</strong> la señal de YouTube Live, la API de estado y esta página.</li>
</ul>

<h3>Qué contenido hay</h3>
<p>El <a href="#grafo-informacion">grafo de información</a> une cada bloque de la grilla con las carreras que emite, facultad por facultad, con su nivel (grado o posgrado) y su modalidad según el sitio oficial de la UMSA. Las flechas hacia la rotación marcan los bloques que emiten todas las carreras.</p>

<h3>Cómo cargar contenido</h3>
<ol>
<li><strong>Con IA:</strong> <code>python scripts/cargar_carreras.py</code> genera los clips de las carreras que todavía no tienen video, a partir de la ficha oficial de cada una. Para un clip suelto: <code>POST /api/v1/ai/clip</code> con un tema, un <code>nombre_archivo</code> que empiece con el prefijo de la facultad (por ejemplo <code>hum_grado_psicologia</code>) y, si querés, una placa de <code>media/placas</code>.</li>
<li><strong>Un video propio:</strong> copiarlo a <code>media/videos</code> con el prefijo del bloque, ya normalizado a 1080p30 H.264/AAC. El scheduler lo toma en el próximo cambio de bloque.</li>
</ol>
<p>La documentación técnica de cada endpoint está en <a href="/docs">/docs</a>.</p>

<h3>Protección</h3>
<p>Ver esta página, el estado y la playlist es público. Arrancar o parar la emisión, tocar la playlist y generar contenido con IA exige el encabezado <code>X-Admin-Token</code>. En producción la app no arranca sin ese token, y sin modelo de lenguaje o de voz responde un error en vez de mandar al aire un guion simulado o un clip mudo.</p>

<h3>Limitaciones conocidas</h3>
<ul>
<li>Cambiar de bloque reinicia ffmpeg: la señal se corta un par de segundos.</li>
<li>Si un bloque queda sin clips y sin respaldo, la emisión se detiene y no vuelve sola al bloque siguiente: hay que arrancarla a mano.</li>
<li>El modo producción se detecta solo dentro de Railway; en otro hosting hay que fijar <code>APP_ENV=production</code>.</li>
<li>Todavía no hay subtítulos automáticos ni placas con datos en tiempo real.</li>
</ul>
""",
        "grafos": """
<h2 id="grafos">Grafos</h2>
<h3 id="grafo-funcionamiento">Grafo de funcionamiento</h3>
<p>Cómo trabaja el canal: de dónde sale el contenido, qué procesos lo mueven, dónde se guarda y qué publica.</p>
<div class="grafo">__GRAFO_FUNC__</div>
<h3 id="grafo-informacion">Grafo de información</h3>
<p>Qué emite cada bloque de la grilla.</p>
<div class="grafo">__GRAFO_INFO__</div>
<p class="leyenda"><span class="c-fuente">■</span> fuente <span class="c-proceso">■</span> proceso o bloque <span class="c-dato">■</span> dato o contenido <span class="c-publica">■</span> lo que publica</p>
""",
        "pie": "Servicio FastAPI + ffmpeg · API técnica en /docs",
    },
    "en": {
        "titulo": "UMSA Live & Connected",
        "subtitulo": "UMSA institutional channel streaming 24 hours a day on YouTube Live.",
        "nav": [("video", "Live video"), ("manual", "Manual"), ("grafos", "Graphs")],
        "otro_idioma": ("/", "Español"),
        "estado_titulo": "Stream status",
        "estado_cargando": "Checking…",
        "estado_al_aire": "On air",
        "estado_detenida": "Stopped",
        "estado_error": "Could not check the status.",
        "bloque_actual": "Block for the current time",
        "subs_vacio": "English subtitles of what is on air appear here.",
        "manual": """
<h2 id="manual">Manual</h2>
<h3>What it is</h3>
<p>A service that keeps the YouTube channel of UMSA (Universidad del Museo Social Argentino) on air without interruptions.
It takes prepared video clips and streams them in a loop with ffmpeg. Programming changes by itself according to Argentina time, following a six-block schedule.</p>
<p>New clips can be produced with artificial intelligence: a language model writes the script, Piper turns it into speech (it runs on the server itself, with no per-use cost) and ffmpeg builds the video over an institutional slide.</p>

<h3>How to watch</h3>
<p>The live channel player is at the top. Next to it you can see whether the service is streaming and which block matches the current time. If the player says there is no stream, the channel has not been set for this page yet (<code>YOUTUBE_CHANNEL_ID</code> variable) or streaming is stopped.</p>
<p>Below the player you can read English subtitles of what is on air. The stream itself is narrated in Spanish; the subtitles are translated from the script of each clip and computed on the server, so they may run a few seconds ahead of or behind the YouTube video. Videos uploaded without going through the AI pipeline have no subtitles.</p>

<h3>Programming schedule</h3>
<table><thead><tr><th>Time slot (Argentina time)</th><th>Block</th><th>Files it streams</th></tr></thead><tbody>__GRILLA__</tbody></table>
<p>During the day, each of the five schools has its own time slot with all its undergraduate and graduate programs. From 22 to 7, all of the university's programs rotate. Each block streams the clips whose name starts with its prefix. Prime Time has no content of its own yet: meanwhile, like any empty block, it streams the rotation of all programs.</p>

<h3>How it works</h3>
<p>The <a href="#grafo-funcionamiento">how-it-works graph</a> reads from left to right:</p>
<ul>
<li><strong>Sources:</strong> the operator (from Swagger or with the <code>.ps1</code> scripts), the language model (Anthropic, with OpenAI as fallback), Piper for the voice, the institutional slides and the clock in Argentina time.</li>
<li><strong>Processes:</strong> <code>POST /ai/clip</code> chains script, voice and video. The scheduler checks every minute which block applies and rewrites the playlist. The streamer is ffmpeg streaming without re-encoding, and the watchdog restarts it if it crashes by itself.</li>
<li><strong>Stored data:</strong> voices in <code>media/audio</code>, clips in <code>media/videos</code> and the list of what is on air in <code>playlist.txt</code>.</li>
<li><strong>What it publishes:</strong> the YouTube Live signal, the status API and this page.</li>
</ul>

<h3>What content there is</h3>
<p>The <a href="#grafo-informacion">information graph</a> links each schedule block with the programs it streams, school by school, with their level (undergraduate or graduate) and format as listed on the official UMSA website. Arrows to the rotation mark the blocks that stream all programs.</p>

<h3>How to add content</h3>
<ol>
<li><strong>With AI:</strong> <code>python scripts/cargar_carreras.py</code> generates the clips for programs that have no video yet, from each program's official page. For a single clip: <code>POST /api/v1/ai/clip</code> with a topic, a <code>nombre_archivo</code> starting with the school prefix (for example <code>hum_grado_psicologia</code>) and, optionally, a slide from <code>media/placas</code>.</li>
<li><strong>Your own video:</strong> copy it to <code>media/videos</code> with the block prefix, already normalized to 1080p30 H.264/AAC. The scheduler picks it up at the next block change.</li>
</ol>
<p>Technical documentation for each endpoint is at <a href="/docs">/docs</a>.</p>

<h3>Protection</h3>
<p>This page, the status and the playlist are public. Starting or stopping the stream, changing the playlist and generating AI content require the <code>X-Admin-Token</code> header. In production the app does not start without that token, and without a language or voice model it returns an error instead of airing a simulated script or a silent clip.</p>

<h3>Known limitations</h3>
<ul>
<li>Changing blocks restarts ffmpeg: the signal drops for a couple of seconds.</li>
<li>If a block has no clips and no fallback, streaming stops and does not come back by itself on the next block: it has to be started by hand.</li>
<li>Production mode is detected only inside Railway; on other hosting set <code>APP_ENV=production</code>.</li>
<li>There are no automatic subtitles or live-data slides yet.</li>
</ul>
""",
        "grafos": """
<h2 id="grafos">Graphs</h2>
<h3 id="grafo-funcionamiento">How-it-works graph</h3>
<p>How the channel works: where content comes from, which processes move it, where it is stored and what it publishes.</p>
<div class="grafo">__GRAFO_FUNC__</div>
<h3 id="grafo-informacion">Information graph</h3>
<p>What each schedule block streams.</p>
<div class="grafo">__GRAFO_INFO__</div>
<p class="leyenda"><span class="c-fuente">■</span> source <span class="c-proceso">■</span> process or block <span class="c-dato">■</span> data or content <span class="c-publica">■</span> what it publishes</p>
""",
        "pie": "FastAPI + ffmpeg service · technical API at /docs",
    },
}

CSS = """
:root { --fondo:#f7f7f5; --texto:#1d1d1b; --suave:#5c5c58; --borde:#d9d8d2; --tarjeta:#ffffff; --acento:#1f4e8c;
  --fuente:#e6eefb; --fuente-b:#4a74b8; --proceso:#fdf0dc; --proceso-b:#c58a2b; --dato:#e5f4ea; --dato-b:#3f8f5a;
  --publica:#f6e3ec; --publica-b:#a54a76; --arista:#8b8a84; }
@media (prefers-color-scheme: dark) { :root { --fondo:#141413; --texto:#ecebe6; --suave:#a9a8a1; --borde:#3a3a37; --tarjeta:#1e1e1c;
  --acento:#8fb4ee; --fuente:#1c2a42; --fuente-b:#7c9fd8; --proceso:#3a2d17; --proceso-b:#d9a64f; --dato:#18321f; --dato-b:#6cc08a;
  --publica:#3a1d2b; --publica-b:#d784ab; --arista:#7d7c76; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--fondo); color:var(--texto); font:16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
header, main, footer { max-width:1100px; margin:0 auto; padding:0 16px; }
header { padding-top:24px; }
h1 { margin:0 0 4px; font-size:1.7rem; }
.sub { margin:0; color:var(--suave); }
nav { display:flex; flex-wrap:wrap; gap:8px 18px; margin:16px 0 8px; padding-bottom:10px; border-bottom:1px solid var(--borde); }
nav a { color:var(--acento); text-decoration:none; font-weight:600; }
nav a.idioma { margin-left:auto; }
a { color:var(--acento); }
h2 { margin-top:40px; font-size:1.35rem; }
h3 { margin-top:28px; font-size:1.08rem; }
code { font-size:.9em; background:var(--tarjeta); border:1px solid var(--borde); border-radius:4px; padding:0 4px; }
.vivo { display:grid; grid-template-columns:minmax(0,2fr) minmax(0,1fr); gap:16px; margin-top:16px; }
@media (max-width: 760px) { .vivo { grid-template-columns:1fr; } }
.marco { position:relative; aspect-ratio:16/9; background:#000; border-radius:8px; overflow:hidden; }
.marco iframe { position:absolute; inset:0; width:100%; height:100%; border:0; }
.aviso { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; padding:24px; text-align:center; color:#ddd; }
.subtitulo { min-height:3.4em; margin:8px 0 0; padding:8px 12px; background:var(--tarjeta); border:1px solid var(--borde);
  border-radius:8px; text-align:center; white-space:pre-line; font-size:1.05rem; }
.subtitulo.vacio { color:var(--suave); font-size:.92rem; }
.estado { background:var(--tarjeta); border:1px solid var(--borde); border-radius:8px; padding:14px 16px; }
.estado h2 { margin:0 0 8px; font-size:1.05rem; }
.estado p { margin:6px 0; }
.punto { display:inline-block; width:10px; height:10px; border-radius:50%; background:var(--suave); margin-right:6px; }
.punto.on { background:#2e9b55; } .punto.off { background:#c2453b; }
table { border-collapse:collapse; width:100%; background:var(--tarjeta); }
th, td { border:1px solid var(--borde); padding:6px 10px; text-align:left; vertical-align:top; overflow-wrap:anywhere; }
.grafo { overflow-x:auto; background:var(--tarjeta); border:1px solid var(--borde); border-radius:8px; padding:8px; }
.grafo svg { display:block; width:100%; min-width:640px; height:auto; margin:0 auto; }
.nodo rect { stroke-width:1.5; }
.c-fuente rect { fill:var(--fuente); stroke:var(--fuente-b); } .c-proceso rect { fill:var(--proceso); stroke:var(--proceso-b); }
.c-dato rect { fill:var(--dato); stroke:var(--dato-b); } .c-publica rect { fill:var(--publica); stroke:var(--publica-b); }
.leyenda .c-fuente { color:var(--fuente-b); } .leyenda .c-proceso { color:var(--proceso-b); }
.leyenda .c-dato { color:var(--dato-b); } .leyenda .c-publica { color:var(--publica-b); }
.leyenda span { margin-left:10px; }
.t1 { font:600 14px system-ui, sans-serif; fill:var(--texto); } .t2 { font:12px system-ui, sans-serif; fill:var(--suave); }
.col { font:600 13px system-ui, sans-serif; fill:var(--suave); text-anchor:middle; }
.arista { fill:none; stroke:var(--arista); stroke-width:1.4; } .punta { fill:var(--arista); }
footer { margin-top:48px; padding-bottom:32px; color:var(--suave); font-size:.9rem; }
"""

# Sin comillas simples en los textos que van dentro del JS: los textos se
# insertan con json (comillas dobles) y se muestran con textContent.
JS = """
(function () {
  var T = __TEXTOS_JS__;
  var estado = document.getElementById("estado-emision");
  var bloque = document.getElementById("estado-bloque");
  function poner(el, clase, texto) {
    el.textContent = "";
    if (clase) { var p = document.createElement("span"); p.className = "punto " + clase; el.appendChild(p); }
    el.appendChild(document.createTextNode(texto));
  }
  function actualizar() {
    fetch("/api/v1/stream/status").then(function (r) { return r.json(); }).then(function (s) {
      poner(estado, s.running ? "on" : "off", s.running ? T.al_aire : T.detenida);
    }).catch(function () { poner(estado, "", T.error); });
    fetch("/api/v1/stream/schedule").then(function (r) { return r.json(); }).then(function (s) {
      var nombre = s.bloque_calculado_ahora;
      poner(bloque, "", T.bloques[nombre] || nombre);
    }).catch(function () { poner(bloque, "", "—"); });
  }
  actualizar();
  setInterval(actualizar, 30000);

  // Subtítulos: el servidor manda los de los próximos ~20 s con tiempos
  // relativos a su respuesta; acá se pintan con el reloj local y se vuelven
  // a pedir cada 10 s (ver core/al_aire.py).
  var sub = document.getElementById("subtitulo");
  var cues = [];
  function pedirSubs() {
    fetch("/api/v1/stream/subtitulos?idioma=" + T.idioma).then(function (r) { return r.json(); }).then(function (s) {
      var base = Date.now() / 1000;
      cues = (s.cues || []).map(function (c) { return { a: base + c.desde, b: base + c.hasta, t: c.texto }; });
    }).catch(function () { cues = []; });
  }
  function pintarSubs() {
    var ahora = Date.now() / 1000, texto = "";
    for (var i = 0; i < cues.length; i++) {
      if (cues[i].a <= ahora && ahora < cues[i].b) { texto = cues[i].t; break; }
    }
    if (texto) { sub.textContent = texto; sub.className = "subtitulo"; }
    else if (!cues.length) { sub.textContent = T.subs_vacio; sub.className = "subtitulo vacio"; }
    else { sub.textContent = ""; sub.className = "subtitulo"; }  // pausa entre oraciones: sin parpadeo del aviso
  }
  pedirSubs();
  setInterval(pedirSubs, 10000);
  setInterval(pintarSubs, 250);
})();
"""


def render(lang: str) -> str:
    import json

    t = TEXTOS[lang]
    nav = "".join(f'<a href="#{ancla}">{escape(texto)}</a>' for ancla, texto in t["nav"])
    href, idioma = t["otro_idioma"]
    nav += f'<a class="idioma" href="{href}" hreflang="{"en" if lang == "es" else "es"}">{escape(idioma)}</a>'
    manual = t["manual"].replace("__GRILLA__", _filas_grilla(lang))
    grafos = t["grafos"].replace("__GRAFO_FUNC__", grafo_funcionamiento(lang)).replace("__GRAFO_INFO__", grafo_informacion(lang))
    textos_js = json.dumps(
        {
            "al_aire": t["estado_al_aire"],
            "detenida": t["estado_detenida"],
            "error": t["estado_error"],
            "idioma": lang,
            "subs_vacio": t["subs_vacio"],
            "bloques": {n: (n if lang == "es" else BLOQUE_EN[n]) for n in BLOQUE_EN},
        },
        ensure_ascii=False,
    )
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(t["titulo"])}</title>
<meta name="description" content="{escape(t["subtitulo"])}">
<link rel="alternate" hreflang="es" href="/">
<link rel="alternate" hreflang="en" href="/en">
<style>{CSS}</style>
</head>
<body>
<header>
<h1>{escape(t["titulo"])}</h1>
<p class="sub">{escape(t["subtitulo"])}</p>
<nav>{nav}</nav>
</header>
<main>
<section id="video" class="vivo">
<div>
<div class="marco">__VIDEO__</div>
<p id="subtitulo" class="subtitulo vacio" lang="{lang}">{escape(t["subs_vacio"])}</p>
</div>
<aside class="estado" aria-live="polite">
<h2>{escape(t["estado_titulo"])}</h2>
<p id="estado-emision">{escape(t["estado_cargando"])}</p>
<p><strong>{escape(t["bloque_actual"])}:</strong> <span id="estado-bloque">—</span></p>
</aside>
</section>
{manual}
{grafos}
</main>
<footer>{escape(t["pie"])}</footer>
<script>{JS.replace("__TEXTOS_JS__", textos_js)}</script>
</body>
</html>
"""


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    for lang in ("es", "en"):
        destino = SALIDA / f"sitio_{lang}.html"
        destino.write_text(render(lang), encoding="utf-8", newline="\n")
        print(f"escrito {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
