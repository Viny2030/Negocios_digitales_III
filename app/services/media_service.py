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
PERFIL_VIDEO = ["-c:v", "libx264", "-profile:v", "high", "-r", "30", "-vf", "scale=1920:1080"]
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
