"""schemas/playlist.py — Modelos Pydantic para la gestión de la playlist."""
from __future__ import annotations

from pydantic import BaseModel


class ClipItem(BaseModel):
    filename: str
    duration_seconds: float | None = None
    codec: str | None = None
    resolution: str | None = None


class PlaylistResponse(BaseModel):
    items: list[ClipItem]


class AddClipRequest(BaseModel):
    # El archivo ya tiene que estar en settings.media_dir (subido por otra vía,
    # ej. rsync/SFTP al Volume de Railway, o copiado a mano en desarrollo).
    # No se maneja upload HTTP acá a propósito: los clips pesan cientos de MB
    # y un upload por API atado al mismo proceso que sostiene el streaming
    # 24/7 es un riesgo de estabilidad que no vale la pena para este alcance.
    filename: str
    posicion: int | None = None  # None = al final


class ReorderRequest(BaseModel):
    orden: list[str]  # lista completa de filenames en el nuevo orden deseado
