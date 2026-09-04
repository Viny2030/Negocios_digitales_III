"""
api/v1/playlist.py — Gestión de la playlist que lee FFmpeg (demuxer concat).

El archivo de playlist usa el formato "ffconcat" que espera FFmpeg:
    file 'nombre_del_clip.mp4'
una línea por clip, en el orden de reproducción. Ver
https://ffmpeg.org/ffmpeg-formats.html#concat — no hace falta la directiva
`ffconcat version 1.0` para el uso básico que necesitamos acá.

Todas las funciones reescriben el archivo completo de forma atómica
(escriben a un .tmp y hacen os.replace) para que un fallo a mitad de
escritura no deje al streamer leyendo una playlist corrupta la próxima
vez que arranque.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas.playlist import AddClipRequest, ClipItem, PlaylistResponse, ReorderRequest
from app.services.media_service import MediaValidationError, probar_clip

router = APIRouter(prefix="/playlist", tags=["playlist"])


def _leer_playlist() -> list[str]:
    if not settings.playlist_path.exists():
        return []
    lineas = settings.playlist_path.read_text(encoding="utf-8").splitlines()
    nombres = []
    for linea in lineas:
        linea = linea.strip()
        if linea.startswith("file "):
            # quita "file " y las comillas simples que rodean el nombre
            nombres.append(linea[len("file "):].strip().strip("'"))
    return nombres


def _escribir_playlist(nombres: list[str]) -> None:
    contenido = "\n".join(f"file '{n}'" for n in nombres) + ("\n" if nombres else "")
    tmp = settings.playlist_path.with_suffix(".tmp")
    tmp.write_text(contenido, encoding="utf-8")
    os.replace(tmp, settings.playlist_path)  # atómico en el mismo filesystem


@router.get("", response_model=PlaylistResponse)
def listar() -> PlaylistResponse:
    items = []
    for nombre in _leer_playlist():
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
    nombres = _leer_playlist()
    if body.filename in nombres:
        raise HTTPException(status_code=409, detail=f"{body.filename} ya está en la playlist")

    posicion = body.posicion if body.posicion is not None else len(nombres)
    nombres.insert(max(0, min(posicion, len(nombres))), body.filename)
    _escribir_playlist(nombres)
    return listar()


@router.put("/reorder", response_model=PlaylistResponse)
def reordenar(body: ReorderRequest) -> PlaylistResponse:
    actuales = set(_leer_playlist())
    nuevos = set(body.orden)
    if actuales != nuevos:
        raise HTTPException(
            status_code=400,
            detail="El nuevo orden tiene que contener EXACTAMENTE los mismos archivos que la "
                    "playlist actual (ni de más ni de menos) — usá POST /playlist para agregar "
                    "o DELETE /playlist/{filename} para sacar, y después reordená.",
        )
    _escribir_playlist(body.orden)
    return listar()


@router.delete("/{filename}", response_model=PlaylistResponse)
def eliminar(filename: str) -> PlaylistResponse:
    nombres = _leer_playlist()
    if filename not in nombres:
        raise HTTPException(status_code=404, detail=f"{filename} no está en la playlist")
    nombres.remove(filename)
    _escribir_playlist(nombres)
    return listar()
