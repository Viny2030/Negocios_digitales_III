"""schemas/stream.py — Modelos Pydantic para el control del streamer."""
from __future__ import annotations

from pydantic import BaseModel


class StatusResponse(BaseModel):
    running: bool
    pid: int | None = None
    started_at: str | None = None
    uptime_seconds: float | None = None
    return_code: int | None = None
    last_log_lines: list[str] = []


class StreamCommand(BaseModel):
    """Reservado para comandos futuros con parámetros (ej. bitrate puntual).
    Hoy start/stop/reload no necesitan body, pero se deja el modelo para no
    romper el contrato de la API cuando se agregue el primer parámetro."""
    pass


class ActionResult(BaseModel):
    ok: bool
    detail: str
