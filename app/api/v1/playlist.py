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

FIX 2026-09-06: `media_dir` (media/videos) y `playlist_path` (media/) NO son
la misma carpeta. El demuxer concat de FFmpeg resuelve los nombres de
archivo relativos de la playlist contra la carpeta DEL PROPIO
playlist.txt (media/), no contra `media_dir` — así que escribir el nombre
"pelado" (ej. "clip.mp4") rompe apenas ese clip no esté también copiado a
mano en media/ (justo lo que pasaba con clip_prueba.mp4, por eso "andaba").
Se vio en la práctica: /ai/clip generó bien un video en media/videos/, se
agregó a la playlist, pero al llegarle el turno en el loop FFmpeg no lo
encontraba y el stream se cortaba ("EN DIRECTO" pero sin datos en
YouTube). `_escribir_playlist()` ahora calcula la ruta relativa real desde
la carpeta de la playlist hacia `media_dir` para cada entrada; `filename`
sigue siendo, de cara a la API (`AddClipRequest`, `ClipItem`, etc.), el
nombre pelado del archivo dentro de `media_dir` — `_leer_playlist()` lo
recupera con `Path(...).name` sin importar qué ruta haya quedado escrita
en el .txt.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas.playlist import AddClipRequest, ClipItem, PlaylistResponse, ReorderRequest
from app.services.media_service import MediaValidationError, probar_clip

router = APIRouter(prefix="/playlist", tags=["playlist"])


def _ruta_para_ffmpeg(nombre: str) -> str:
    """Convierte un nombre de archivo (relativo a media_dir) en la ruta que
    hay que escribir en playlist.txt para que el demuxer concat lo
    encuentre — relativa a la carpeta DEL PROPIO playlist.txt, no a
    media_dir (ver docstring del módulo)."""
    absoluta = (settings.media_dir / nombre).resolve()
    carpeta_playlist = settings.playlist_path.resolve().parent
    try:
        relativa = os.path.relpath(absoluta, carpeta_playlist)
    except ValueError:
        # Windows: media_dir y la playlist están en unidades distintas —
        # no se puede expresar como ruta relativa, usamos la absoluta.
        return absoluta.as_posix()
    return Path(relativa).as_posix()


def _leer_playlist() -> list[str]:
    if not settings.playlist_path.exists():
        return []
    lineas = settings.playlist_path.read_text(encoding="utf-8").splitlines()
    nombres = []
    for linea in lineas:
        linea = linea.strip()
        if linea.startswith("file "):
            # quita "file " y las comillas simples que rodean la ruta, y se
            # queda solo con el nombre de archivo (el identificador que usa
            # el resto de la API) sin importar qué ruta haya quedado escrita
            ruta = linea[len("file "):].strip().strip("'")
            nombres.append(Path(ruta).name)
    return nombres


def _escribir_playlist(nombres: list[str]) -> None:
    contenido = "\n".join(f"file '{_ruta_para_ffmpeg(n)}'" for n in nombres) + ("\n" if nombres else "")
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
