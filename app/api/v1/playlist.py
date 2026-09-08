"""
api/v1/playlist.py — Gestión de la playlist que lee FFmpeg (demuxer concat).

La lectura/escritura del archivo playlist.txt vive en core/playlist_io.py
(compartida con core/scheduler.py, que reescribe la playlist automáticamente
según el bloque horario de la grilla de 24hs — ver
Claude outputs/plan_contenido_canal_umsa.md). Este módulo se queda solo con
los endpoints de alta/baja/reorder manual.

Ojo: si el scheduler está activo (SCHEDULER_ENABLED, default true — ver
.env.example), un cambio manual acá puede quedar pisado la próxima vez que
cambie el bloque horario. Para testing manual sostenido, desactivalo con
SCHEDULER_ENABLED=false, o usá POST /api/v1/stream/schedule/force para
controlar vos el bloque activo.

FIX 2026-09-06: `media_dir` (media/videos) y `playlist_path` (media/) NO son
la misma carpeta — ver el docstring de core/playlist_io.ruta_para_ffmpeg.
Se vio en la práctica: /ai/clip generó bien un video en media/videos/, se
agregó a la playlist, pero al llegarle el turno en el loop FFmpeg no lo
encontraba y el stream se cortaba ("EN DIRECTO" pero sin datos en YouTube).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.core.playlist_io import escribir_playlist, leer_playlist
from app.schemas.playlist import AddClipRequest, ClipItem, PlaylistResponse, ReorderRequest
from app.services.media_service import MediaValidationError, probar_clip

router = APIRouter(prefix="/playlist", tags=["playlist"])


@router.get("", response_model=PlaylistResponse)
def listar() -> PlaylistResponse:
    items = []
    for nombre in leer_playlist():
        path = settings.media_dir / nombre
        info = {}
        if path.exists():
            try:
                probado = probar_clip(path)
                info = {
                    "duration_seconds": probado["duracion_seg"],
                    "codec": probado["codec_video"],
                    "resolution": probado["resolucion"],
                }
            except MediaValidationError:
                pass  # el clip está en la playlist pero ffprobe no pudo leerlo — se lista igual, sin metadata
        items.append(ClipItem(filename=nombre, **info))
    return PlaylistResponse(items=items)


@router.post("", response_model=PlaylistResponse)
def agregar(body: AddClipRequest) -> PlaylistResponse:
    path = settings.media_dir / body.filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{body.filename} no existe en {settings.media_dir} — copialo ahí primero "
                    f"(idealmente ya normalizado, ver services/media_service.normalizar_clip).",
        )
    nombres = leer_playlist()
    if body.filename in nombres:
        raise HTTPException(status_code=409, detail=f"{body.filename} ya está en la playlist")

    posicion = body.posicion if body.posicion is not None else len(nombres)
    nombres.insert(max(0, min(posicion, len(nombres))), body.filename)
    escribir_playlist(nombres)
    return listar()


@router.put("/reorder", response_model=PlaylistResponse)
def reordenar(body: ReorderRequest) -> PlaylistResponse:
    actuales = set(leer_playlist())
    nuevos = set(body.orden)
    if actuales != nuevos:
        raise HTTPException(
            status_code=400,
            detail="El nuevo orden tiene que contener EXACTAMENTE los mismos archivos que la "
                    "playlist actual (ni de más ni de menos) — usá POST /playlist para agregar "
                    "o DELETE /playlist/{filename} para sacar, y después reordená.",
        )
    escribir_playlist(body.orden)
    return listar()


@router.delete("/{filename}", response_model=PlaylistResponse)
def eliminar(filename: str) -> PlaylistResponse:
    nombres = leer_playlist()
    if filename not in nombres:
        raise HTTPException(status_code=404, detail=f"{filename} no está en la playlist")
    nombres.remove(filename)
    escribir_playlist(nombres)
    return listar()
