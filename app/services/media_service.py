"""
services/media_service.py — Validación y normalización de clips con
FFprobe/FFmpeg.

Por qué existe esto (ver también core/streamer.py): el streamer transmite
con `-c copy` (sin recodificar) para que el consumo de CPU en Railway sea
mínimo — es la base de la estimación de costos del documento del
proyecto. Pero el demuxer concat de FFmpeg con stream copy solo funciona
de forma confiable si TODOS los clips comparten el mismo perfil técnico
(códec de video/audio, resolución, fps, sample rate). Si se agrega un
clip con un perfil distinto tal cual viene (ej. un webinar exportado en
otro formato), lo más probable es que el stream se corte o el audio se
desincronice apenas le toque el turno en el loop.

`normalizar_clip()` resuelve esto UNA vez, al ingestar el clip (no en cada
arranque del streamer): lo recodifica al perfil fijo definido acá abajo.
Sí consume CPU en ese momento puntual — pero es un costo de ingesta, no
de la emisión 24/7 continua, que es la que hay que mantener barata.
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from app.config import settings

logger = logging.getLogger("media_service")

# Perfil técnico fijo al que se normaliza todo clip antes de sumarlo a la
# playlist. 1080p30 coincide con lo que ya asume el documento de costos
# ("1080p30 para contenido institucional y diapositivas").
PERFIL_VIDEO = [
    "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
    "-r", "30", "-vf", "scale=1920:1080",
]
# FIX 2026-09-04: sin "-pix_fmt yuv420p" explícito, libx264 puede terminar
# heredando el espacio de color del origen (ej. rgb24 o 4:4:4) y el perfil
# "high" rechaza eso de entrada ("high profile doesn't support 4:4:4") —
# se vio en la práctica probando con un clip sintético (ffmpeg testsrc).
# Con clips reales (casi siempre ya en yuv420p) el bug no se nota, pero
# conviene forzarlo igual: es también el formato más compatible para
# ingesta RTMP en general.
PERFIL_AUDIO = ["-c:a", "aac", "-ar", "44100", "-ac", "2"]


class MediaValidationError(Exception):
    pass


def probar_clip(path: Path) -> dict:
    """Corre ffprobe y devuelve duración, códec de video/audio y resolución.
    Lanza MediaValidationError si el archivo no es un media válido."""
    comando = [
        settings.ffprobe_bin, "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    ]
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise MediaValidationError(f"ffprobe falló para {path.name}: {resultado.stderr.strip()}")

    data = json.loads(resultado.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if video is None:
        raise MediaValidationError(f"{path.name} no tiene stream de video")

    return {
        "duracion_seg": float(data.get("format", {}).get("duration", 0.0)),
        "codec_video": video.get("codec_name"),
        "codec_audio": audio.get("codec_name") if audio else None,
        "resolucion": f"{video.get('width')}x{video.get('height')}",
    }


def armar_clip_narrado(
    audio_path: Path,
    destino: Path,
    imagen_fondo: Path | None = None,
    color_fondo: str = "black",
) -> Path:
    """Arma un clip de video a partir de un audio narrado (ver
    services/ai_service.generar_voz) y un fondo fijo: una imagen (placa
    institucional) si se pasa `imagen_fondo`, o un color sólido generado
    con el filtro `lavfi` si todavía no hay una placa/fondo real para ese
    contenido.

    Este era el paso que quedaba pendiente en el scaffold inicial (ver el
    docstring anterior de api/v1/ai_generator.py): conecta guion + voz con
    la playlist real, para poder probar un bloque de la grilla de punta a
    punta (ej. "UMSA Despierta") sin depender de que ya exista el video
    institucional definitivo — cuando haya placas/fondos reales, basta con
    pasar `imagen_fondo` en vez de dejarlo en None.

    Codifica directo al PERFIL_VIDEO/PERFIL_AUDIO fijo del proyecto — no
    hace falta pasar el resultado por normalizar_clip() después, ya sale
    compatible con el `-c copy` del streamer apenas se agrega a la
    playlist.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)

    if imagen_fondo is not None:
        entrada_video = ["-loop", "1", "-i", str(imagen_fondo)]
    else:
        entrada_video = ["-f", "lavfi", "-i", f"color=c={color_fondo}:s=1920x1080:r=30"]

    comando = [
        settings.ffmpeg_bin, "-y",
        *entrada_video,
        "-i", str(audio_path),
        *PERFIL_VIDEO, *PERFIL_AUDIO,
        "-shortest",  # corta cuando termina el audio (la imagen/color son "infinitos")
        str(destino),
    ]
    logger.info(
        f"Armando clip narrado {destino.name} "
        f"(fondo={'imagen ' + imagen_fondo.name if imagen_fondo else color_fondo})"
    )
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise MediaValidationError(f"ffmpeg no pudo armar el clip {destino.name}: {resultado.stderr[-800:]}")
    return destino


def normalizar_clip(origen: Path, destino: Path) -> Path:
    """Recodifica `origen` al perfil técnico fijo y lo guarda en `destino`.
    Idempotente: si `destino` ya existe, no vuelve a recodificar."""
    if destino.exists():
        logger.info(f"{destino.name} ya estaba normalizado — se reusa")
        return destino

    destino.parent.mkdir(parents=True, exist_ok=True)
    comando = [
        settings.ffmpeg_bin, "-y", "-i", str(origen),
        *PERFIL_VIDEO, *PERFIL_AUDIO,
        str(destino),
    ]
    logger.info(f"Normalizando {origen.name} → {destino.name}")
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise MediaValidationError(f"ffmpeg no pudo normalizar {origen.name}: {resultado.stderr[-800:]}")
    return destino
