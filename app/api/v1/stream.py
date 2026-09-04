"""api/v1/stream.py — Control del stream: start, stop, status, reload."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.streamer import streamer
from app.schemas.stream import ActionResult, StatusResponse

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
