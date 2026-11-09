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
# Grafo de información: bloque de la grilla ↔ contenido que emite.
# Las franjas y prefijos son los de GRILLA en app/core/scheduler.py
# (tests/test_sitio.py comprueba que todos los bloques estén acá).
# --------------------------------------------------------------------------
BLOQUES = [
    # id, fila, nombre, franja, prefijo
    ("despierta", 0, "UMSA Despierta", "07–10 h", "umsa_despierta_"),
    ("foco", 3.5, "Foco Grado y Vocación", "10–13 h", "foco_grado_"),
    ("ext", 7, "Extensión y Comunidad", "13–16 h", "extension_"),
    ("pos", 9.5, "Espacio Posgrados y Negocios", "16–19 h", "posgrado_"),
    ("prime", 12.4, "Prime Time: Clases Abiertas", "19–22 h", "primetime_"),
    ("lounge", 13.6, "UMSA Study Lounge", "22–07 h", "studylounge_"),
]
CONTENIDOS = [
    # id, fila, bloque, texto es, texto en
    ("agenda", 0, "despierta", "Agenda, becas y convocatorias", "Agenda, grants and calls"),
    ("abogacia", 1, "foco", "Abogacía", "Law"),
    ("artes", 2, "foco", "Artes Visuales", "Visual Arts"),
    ("contador", 3, "foco", "Contador Público", "Public Accountant"),
    ("negocios", 4, "foco", "Negocios Digitales", "Digital Business"),
    ("psicologia", 5, "foco", "Psicología", "Psychology"),
    ("traductorado", 6, "foco", "Traductorado de Inglés", "English Translation"),
    ("vinculacion", 7, "ext", "Vinculación institucional", "Institutional outreach"),
    ("bioetica", 8, "pos", "Posgrado en Bioética", "Graduate: Bioethics"),
    ("derecho", 9, "pos", "Posgrado en Derecho", "Graduate: Law"),
    ("fono", 10, "pos", "Posgrado en Fonoaudiología", "Graduate: Speech Therapy"),
    ("museologia", 11, "pos", "Posgrado en Museología", "Graduate: Museology"),
    ("respaldo", 13, None, "Respaldo: loop institucional", "Fallback: institutional loop"),
]
BLOQUE_EN = {
    "UMSA Despierta": "UMSA Wakes Up",
    "Foco Grado y Vocación": "Undergraduate & Vocation",
    "Extensión y Comunidad": "Outreach & Community",
    "Espacio Posgrados y Negocios": "Graduate & Business",
    "Prime Time: Clases Abiertas": "Prime Time: Open Classes",
    "UMSA Study Lounge": "UMSA Study Lounge",
}
COLUMNAS_INFO = {"es": ["Bloque de la grilla", "Contenido que emite"], "en": ["Schedule block", "Content it streams"]}

# --------------------------------------------------------------------------
# Dibujo SVG
# --------------------------------------------------------------------------
ANCHO_NODO, ALTO_NODO = 220, 50
COLORES = {"fuente": "c-fuente", "proceso": "c-proceso", "dato": "c-dato", "publica": "c-publica", "bloque": "c-proceso", "contenido": "c-dato"}


def _pos(col: float, fila: float, x0: int, paso_x: int, y0: int, paso_y: int) -> tuple[float, float]:
    return x0 + col * paso_x, y0 + fila * paso_y


def _nodo_svg(x: float, y: float, tipo: str, titulo: str, lineas: list[str]) -> str:
    partes = [
        f'<g class="nodo {COLORES[tipo]}">',
        f'<rect x="{x:.0f}" y="{y:.0f}" width="{ANCHO_NODO}" height="{ALTO_NODO}" rx="8"/>',
        f'<text x="{x + 10:.0f}" y="{y + (21 if lineas else 30):.0f}" class="t1">{escape(titulo)}</text>',
    ]
    for i, linea in enumerate(lineas):
        partes.append(f'<text x="{x + 10:.0f}" y="{y + 39 + 14 * i:.0f}" class="t2">{escape(linea)}</text>')
    partes.append("</g>")
    return "".join(partes)


def _arista_svg(a: tuple[float, float], b: tuple[float, float]) -> str:
    (ax, ay), (bx, by) = a, b
    if bx > ax:  # hacia adelante: borde derecho → borde izquierdo
        x1, y1, x2, y2 = ax + ANCHO_NODO, ay + ALTO_NODO / 2, bx, by + ALTO_NODO / 2
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


def grafo_informacion(lang: str) -> str:
    x0, px, y0, py = 10, 420, 50, 58
    pos = {b[0]: _pos(0, b[1], x0, px, y0, py) for b in BLOQUES}
    pos.update({c[0]: _pos(1, c[1], x0, px, y0, py) for c in CONTENIDOS})
    cuerpo = [
        f'<text x="{x0 + i * px + ANCHO_NODO / 2:.0f}" y="24" class="col">{escape(t)}</text>'
        for i, t in enumerate(COLUMNAS_INFO[lang])
    ]
    for cid, _, bloque, _, _ in CONTENIDOS:
        if bloque:
            cuerpo.append(_arista_svg(pos[bloque], pos[cid]))
    cuerpo += [_arista_svg(pos["prime"], pos["respaldo"]), _arista_svg(pos["lounge"], pos["respaldo"])]
    archivo = "archivos" if lang == "es" else "files"
    for bid, _, nombre, franja, prefijo in BLOQUES:
        titulo = nombre if lang == "es" else BLOQUE_EN[nombre]
        cuerpo.append(_nodo_svg(*pos[bid], "bloque", titulo, [f"{franja} · {archivo} {prefijo}*"]))
    for cid, _, _, es, en in CONTENIDOS:
        linea = ["prueba_fondo_umsa*"] if cid == "respaldo" else []
        cuerpo.append(_nodo_svg(*pos[cid], "contenido", es if lang == "es" else en, linea))
    aria = "Grafo de información: bloques de la grilla y su contenido" if lang == "es" else "Information graph: schedule blocks and their content"
    return _svg(x0 + px + ANCHO_NODO + 10, int(y0 + 13.6 * py + ALTO_NODO + 16), aria, cuerpo)


# --------------------------------------------------------------------------
# Textos del manual
# --------------------------------------------------------------------------
def _filas_grilla(lang: str) -> str:
    filas = []
    for _, _, nombre, franja, prefijo in BLOQUES:
        titulo = nombre if lang == "es" else BLOQUE_EN[nombre]
        filas.append(f"<tr><td>{escape(franja)}</td><td>{escape(titulo)}</td><td><code>{escape(prefijo)}*</code></td></tr>")
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
        "manual": """
<h2 id="manual">Manual</h2>
<h3>Qué es</h3>
<p>Un servicio que mantiene al aire, sin interrupciones, el canal de YouTube de la UMSA (Universidad del Museo Social Argentino).
Toma clips de video ya preparados y los emite en loop con ffmpeg. La programación cambia sola según la hora argentina, siguiendo una grilla de seis bloques.</p>
<p>Los clips nuevos se pueden producir con inteligencia artificial: un modelo de lenguaje redacta el guion, Piper lo convierte en voz (corre en el propio servidor, sin costo por uso) y ffmpeg arma el video con una placa institucional de fondo.</p>

<h3>Cómo ver la transmisión</h3>
<p>Arriba está el reproductor del canal en vivo. Al lado se ve si el servicio está emitiendo y qué bloque corresponde a la hora actual. Si el reproductor dice que no hay transmisión, el canal todavía no se configuró en esta página (variable <code>YOUTUBE_CHANNEL_ID</code>) o la emisión está detenida.</p>

<h3>Grilla de programación</h3>
<table><thead><tr><th>Franja (hora argentina)</th><th>Bloque</th><th>Archivos que emite</th></tr></thead><tbody>__GRILLA__</tbody></table>
<p>Cada bloque emite los clips cuyo nombre empieza con su prefijo. Prime Time y Study Lounge todavía no tienen contenido propio: mientras tanto repiten el loop institucional (<code>prueba_fondo_umsa*</code>).</p>

<h3>Cómo funciona</h3>
<p>El <a href="#grafo-funcionamiento">grafo de funcionamiento</a> se lee de izquierda a derecha:</p>
<ul>
<li><strong>Fuentes:</strong> el operador (desde Swagger o con los scripts <code>.ps1</code>), el modelo de lenguaje (Anthropic, con OpenAI como respaldo), Piper para la voz, las placas institucionales y el reloj en hora argentina.</li>
<li><strong>Procesos:</strong> <code>POST /ai/clip</code> encadena guion, voz y video. El scheduler revisa cada minuto qué bloque corresponde y reescribe la playlist. El streamer es ffmpeg emitiendo sin recodificar, y el watchdog lo reinicia si se cae solo.</li>
<li><strong>Datos guardados:</strong> las voces en <code>media/audio</code>, los clips en <code>media/videos</code> y la lista de lo que se emite en <code>playlist.txt</code>.</li>
<li><strong>Lo que publica:</strong> la señal de YouTube Live, la API de estado y esta página.</li>
</ul>

<h3>Qué contenido hay</h3>
<p>El <a href="#grafo-informacion">grafo de información</a> une cada bloque de la grilla con el contenido que emite: las carreras de grado, los posgrados, la vinculación institucional y la agenda diaria. Las flechas hacia el respaldo marcan los bloques que todavía usan el loop institucional.</p>

<h3>Cómo cargar contenido</h3>
<ol>
<li><strong>Con IA:</strong> <code>POST /api/v1/ai/clip</code> con un tema, un <code>nombre_archivo</code> que empiece con el prefijo del bloque (por ejemplo <code>foco_grado_medicina</code>) y, si querés, una placa de <code>media/placas</code>. Genera guion, voz y video, y lo suma a la playlist.</li>
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
        "manual": """
<h2 id="manual">Manual</h2>
<h3>What it is</h3>
<p>A service that keeps the YouTube channel of UMSA (Universidad del Museo Social Argentino) on air without interruptions.
It takes prepared video clips and streams them in a loop with ffmpeg. Programming changes by itself according to Argentina time, following a six-block schedule.</p>
<p>New clips can be produced with artificial intelligence: a language model writes the script, Piper turns it into speech (it runs on the server itself, with no per-use cost) and ffmpeg builds the video over an institutional slide.</p>

<h3>How to watch</h3>
<p>The live channel player is at the top. Next to it you can see whether the service is streaming and which block matches the current time. If the player says there is no stream, the channel has not been set for this page yet (<code>YOUTUBE_CHANNEL_ID</code> variable) or streaming is stopped.</p>

<h3>Programming schedule</h3>
<table><thead><tr><th>Time slot (Argentina time)</th><th>Block</th><th>Files it streams</th></tr></thead><tbody>__GRILLA__</tbody></table>
<p>Each block streams the clips whose name starts with its prefix. Prime Time and Study Lounge have no content of their own yet: meanwhile they repeat the institutional loop (<code>prueba_fondo_umsa*</code>).</p>

<h3>How it works</h3>
<p>The <a href="#grafo-funcionamiento">how-it-works graph</a> reads from left to right:</p>
<ul>
<li><strong>Sources:</strong> the operator (from Swagger or with the <code>.ps1</code> scripts), the language model (Anthropic, with OpenAI as fallback), Piper for the voice, the institutional slides and the clock in Argentina time.</li>
<li><strong>Processes:</strong> <code>POST /ai/clip</code> chains script, voice and video. The scheduler checks every minute which block applies and rewrites the playlist. The streamer is ffmpeg streaming without re-encoding, and the watchdog restarts it if it crashes by itself.</li>
<li><strong>Stored data:</strong> voices in <code>media/audio</code>, clips in <code>media/videos</code> and the list of what is on air in <code>playlist.txt</code>.</li>
<li><strong>What it publishes:</strong> the YouTube Live signal, the status API and this page.</li>
</ul>

<h3>What content there is</h3>
<p>The <a href="#grafo-informacion">information graph</a> links each schedule block with the content it streams: undergraduate programs, graduate programs, institutional outreach and the daily agenda. Arrows to the fallback mark the blocks that still use the institutional loop.</p>

<h3>How to add content</h3>
<ol>
<li><strong>With AI:</strong> <code>POST /api/v1/ai/clip</code> with a topic, a <code>nombre_archivo</code> starting with the block prefix (for example <code>foco_grado_medicina</code>) and, optionally, a slide from <code>media/placas</code>. It generates script, voice and video, and adds it to the playlist.</li>
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
.estado { background:var(--tarjeta); border:1px solid var(--borde); border-radius:8px; padding:14px 16px; }
.estado h2 { margin:0 0 8px; font-size:1.05rem; }
.estado p { margin:6px 0; }
.punto { display:inline-block; width:10px; height:10px; border-radius:50%; background:var(--suave); margin-right:6px; }
.punto.on { background:#2e9b55; } .punto.off { background:#c2453b; }
table { border-collapse:collapse; width:100%; background:var(--tarjeta); }
th, td { border:1px solid var(--borde); padding:6px 10px; text-align:left; vertical-align:top; }
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
<div class="marco">__VIDEO__</div>
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
