"""
core/al_aire.py — Qué subtítulo corresponde a lo que se está emitiendo ahora.

ffmpeg emite la playlist en loop (`-stream_loop -1`) a velocidad real (`-re`),
así que la posición actual sale de: cuándo arrancó el proceso, qué clips leyó
al arrancar (streamer.emision_actual()) y cuánto dura cada uno (ffprobe,
cacheado). Con esa posición se buscan los subtítulos del clip en curso
(los .srt que genera /ai/clip, ver services/subtitulos.py).

No se devuelve un único texto sino los subtítulos de los próximos
VENTANA_SEG segundos con tiempos RELATIVOS a "ahora": el navegador los pinta
solo con su reloj y consulta de nuevo cada ~10 s, en vez de pedir cada medio
segundo (cientos de espectadores × 2 pedidos/s no tiene sentido).

Precisión: es una estimación. Se le resta settings.subtitulos_demora_seg
porque el espectador ve YouTube con demora; hay que calibrar ese valor con la
transmisión real. Un reinicio de ffmpeg (cambio de bloque, watchdog) arranca
la cuenta de cero automáticamente, porque started_at cambia.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.core.streamer import streamer
from app.services.media_service import MediaValidationError, probar_clip
from app.services.subtitulos import ruta_subtitulos

VENTANA_SEG = 20.0

_TIEMPO = re.compile(r"(\d+):(\d\d):(\d\d),(\d{3})")


def _a_segundos(texto: str) -> float:
    h, m, s, ms = (int(x) for x in _TIEMPO.fullmatch(texto.strip()).groups())
    return h * 3600 + m * 60 + s + ms / 1000


def parsear_srt(contenido: str) -> list[tuple[float, float, str]]:
    cues = []
    for bloque in re.split(r"\n\s*\n", contenido.strip()):
        lineas = bloque.strip().splitlines()
        if len(lineas) < 3 or "-->" not in lineas[1]:
            continue
        try:
            desde, hasta = (_a_segundos(x) for x in lineas[1].split("-->"))
        except (AttributeError, ValueError):
            continue  # bloque roto: se saltea, no tumba los demás
        cues.append((desde, hasta, "\n".join(lineas[2:])))
    return cues


@lru_cache(maxsize=512)
def _duracion_cacheada(ruta: str, mtime: float) -> float | None:
    try:
        return probar_clip(Path(ruta))["duracion_seg"] or None
    except MediaValidationError:
        return None


def duracion(nombre_clip: str) -> float | None:
    ruta = settings.media_dir / nombre_clip
    if not ruta.exists():
        return None
    return _duracion_cacheada(str(ruta), ruta.stat().st_mtime)  # mtime en la clave: un clip regenerado se vuelve a medir


@lru_cache(maxsize=512)
def _cues_cacheados(ruta: str, mtime: float) -> tuple[tuple[float, float, str], ...]:
    return tuple(parsear_srt(Path(ruta).read_text(encoding="utf-8")))


def cues(nombre_clip: str, idioma: str) -> tuple[tuple[float, float, str], ...]:
    ruta = ruta_subtitulos(Path(nombre_clip).stem, idioma)
    if not ruta.exists():
        return ()  # clip sin subtítulos (ej. un video propio): simplemente no se muestra nada
    return _cues_cacheados(str(ruta), ruta.stat().st_mtime)


def subtitulos_al_aire(idioma: str, ahora: datetime | None = None, ventana: float = VENTANA_SEG) -> dict:
    emision = streamer.emision_actual()
    if emision is None:
        return {"al_aire": False, "clip": None, "cues": []}
    clips, inicio = emision
    duraciones = [duracion(c) for c in clips]
    if not clips or any(d is None for d in duraciones):
        return {"al_aire": True, "clip": None, "cues": []}  # sin poder medir un clip no hay posición confiable

    total = sum(duraciones)
    ahora = ahora or datetime.now(UTC)
    t = (ahora - inicio).total_seconds() - settings.subtitulos_demora_seg
    if t >= 0:
        pos, rel = t % total, 0.0  # posición dentro de la vuelta actual del loop
    else:
        pos, rel = 0.0, -t  # el espectador todavía no ve el arranque: el primer clip empieza dentro de -t s

    i = 0
    while pos >= duraciones[i] and i < len(clips) - 1:  # el tope evita salirse por redondeo de floats
        pos -= duraciones[i]
        i += 1
    clip_actual = clips[i] if t >= 0 else None
    rel -= pos  # momento (relativo a ahora) en que empezó el clip i

    resultado = []
    while rel < ventana:
        for desde, hasta, texto in cues(clips[i], idioma):
            a, b = rel + desde, rel + hasta
            if b > 0 and a < ventana:
                resultado.append({"desde": round(a, 3), "hasta": round(b, 3), "texto": texto})
        rel += duraciones[i]
        i = (i + 1) % len(clips)
    return {"al_aire": True, "clip": clip_actual, "cues": resultado}
