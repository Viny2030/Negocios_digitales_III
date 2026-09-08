"""
core/playlist_io.py — Lectura/escritura del archivo playlist.txt que lee
FFmpeg (demuxer concat), compartida entre api/v1/playlist.py (altas/bajas
manuales vía API) y core/scheduler.py (reescritura automática por bloque
horario). Antes esta lógica vivía duplicada/privada dentro de
api/v1/playlist.py — se extrajo acá para que ambos lugares construyan la
playlist exactamente de la misma manera y no se repita (ni se desincronice)
la lógica de rutas relativas.

El archivo de playlist usa el formato "ffconcat" que espera FFmpeg:
    file 'nombre_del_clip.mp4'
una línea por clip, en el orden de reproducción. Ver
https://ffmpeg.org/ffmpeg-formats.html#concat

FIX 2026-09-06 (heredado de api/v1/playlist.py): `media_dir` (media/videos) y
`playlist_path` (media/) NO son la misma carpeta. El demuxer concat de FFmpeg
resuelve los nombres de archivo relativos de la playlist contra la carpeta
DEL PROPIO playlist.txt (media/), no contra `media_dir` — así que hay que
calcular la ruta relativa real desde la carpeta de la playlist hacia
`media_dir` para cada entrada. Se vio en la práctica el 8/9: clip_prueba.mp4
quedó físicamente en media/ (no en media/videos/) mientras la playlist ya
asumía que vivía en media/videos/ — ffmpeg tiraba "Impossible to open" y el
stream se cortaba a los pocos segundos de arrancar.

Todas las funciones que escriben reescriben el archivo completo de forma
atómica (escriben a un .tmp y hacen os.replace) para que un fallo a mitad de
escritura no deje al streamer leyendo una playlist corrupta la próxima vez
que arranque.
"""
from __future__ import annotations

import os
from pathlib import Path

from app.config import settings


def ruta_para_ffmpeg(nombre: str) -> str:
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


def leer_playlist() -> list[str]:
    """Devuelve los nombres de archivo (sin ruta, tal como los conoce el
    resto de la API) actualmente en la playlist, en orden."""
    if not settings.playlist_path.exists():
        return []
    lineas = settings.playlist_path.read_text(encoding="utf-8").splitlines()
    nombres = []
    for linea in lineas:
        linea = linea.strip()
        if linea.startswith("file "):
            # quita "file " y las comillas simples, y se queda solo con el
            # nombre de archivo sin importar qué ruta haya quedado escrita.
            ruta = linea[len("file "):].strip().strip("'")
            nombres.append(Path(ruta).name)
    return nombres


def escribir_playlist(nombres: list[str]) -> None:
    """Reescribe playlist.txt completo, de forma atómica, con los nombres
    dados (en ese orden)."""
    contenido = "\n".join(f"file '{ruta_para_ffmpeg(n)}'" for n in nombres) + ("\n" if nombres else "")
    tmp = settings.playlist_path.with_suffix(".tmp")
    tmp.write_text(contenido, encoding="utf-8")
    os.replace(tmp, settings.playlist_path)  # atómico en el mismo filesystem
