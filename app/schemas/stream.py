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


class ScheduleStatus(BaseModel):
    """Estado del selector automático de bloque horario — ver core/scheduler.py."""
    corriendo: bool
    bloque_actual: str | None = None
    bloque_calculado_ahora: str


class Subtitulo(BaseModel):
    desde: float  # segundos relativos al momento de la respuesta (puede ser negativo: ya empezó)
    hasta: float
    texto: str


class SubtitulosAlAire(BaseModel):
    """Subtítulos de lo que se emite en los próximos segundos — ver core/al_aire.py."""
    al_aire: bool
    clip: str | None = None
    cues: list[Subtitulo] = []


class WatchdogStatus(BaseModel):
    """Estado del watchdog que reinicia el streamer si se cae solo — ver core/watchdog.py."""
    corriendo: bool
    reintentos_recientes: int
    agotado: bool
