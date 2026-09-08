"""api/v1/stream.py — Control del stream: start, stop, status, reload, y el
selector automático de bloque horario (ver core/scheduler.py)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.scheduler import bloque_actual, scheduler
from app.core.streamer import streamer
from app.schemas.stream import ActionResult, ScheduleStatus, StatusResponse

router = APIRouter(prefix="/stream", tags=["stream"])


@router.get("/status", response_model=StatusResponse)
def status() -> StatusResponse:
    return StatusResponse(**streamer.status())


@router.post("/start", response_model=ActionResult)
def start() -> ActionResult:
    try:
        streamer.start()
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return ActionResult(ok=True, detail="Streamer arrancado")


@router.post("/stop", response_model=ActionResult)
def stop() -> ActionResult:
    streamer.stop()
    return ActionResult(ok=True, detail="Streamer detenido")


@router.post("/reload", response_model=ActionResult)
def reload() -> ActionResult:
    """Reinicia ffmpeg para que relea la playlist. Corta la señal un par de
    segundos — ver la limitación documentada en core/streamer.py."""
    try:
        streamer.reload()
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return ActionResult(ok=True, detail="Streamer reiniciado — playlist releída")


@router.get("/schedule", response_model=ScheduleStatus)
def schedule_status() -> ScheduleStatus:
    """Estado del selector automático de bloque horario: qué bloque aplicó
    la última vez (`bloque_actual`) vs. qué bloque correspondería ya mismo
    según la hora real (`bloque_calculado_ahora`) — si difieren, el scheduler
    los va a sincronizar en el próximo chequeo (cada 60s como máximo)."""
    estado = scheduler.estado()
    return ScheduleStatus(
        corriendo=estado["corriendo"],
        bloque_actual=estado["bloque_actual"],
        bloque_calculado_ahora=bloque_actual().nombre,
    )


@router.post("/schedule/force", response_model=ActionResult)
def schedule_force(hora: int | None = None) -> ActionResult:
    """Fuerza ya mismo un recálculo de la playlist según el bloque horario,
    sin esperar al próximo chequeo del scheduler. Pasá `hora` (0-23) para
    simular esa hora en vez de la hora real del sistema — pensado para poder
    probar los 6 bloques de la grilla uno detrás del otro en un rato, en vez
    de esperar 24hs reales."""
    if hora is not None and not (0 <= hora <= 23):
        raise HTTPException(status_code=400, detail="hora tiene que estar entre 0 y 23")
    detail = scheduler.forzar(hora)
    return ActionResult(ok=True, detail=detail)
