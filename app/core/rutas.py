"""
core/rutas.py — Validación de nombres de archivo y rutas que llegan por la API.

Los endpoints arman rutas en disco a partir de lo que manda el cliente
(`nombre_archivo`, `filename`, `voice_id`, `imagen_fondo`). Sin validar, un
valor como "../../app/main" escribía o leía FUERA de las carpetas de medios
(se probó: POST /ai/voz con nombre_archivo="../../x" dejaba el wav en la raíz
del proyecto, y POST /playlist con "../../app/main.py" lo metía en la
playlist que lee ffmpeg). `imagen_fondo` además se le pasa a ffmpeg, que
acepta URLs: el servidor terminaba descargando lo que le pidieran.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

from pydantic import AfterValidator

from app.config import settings

_NOMBRE_SEGURO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,150}$")


def validar_nombre(valor: str) -> str:
    """Solo un nombre de archivo simple: letras, números, '.', '_' y '-', sin
    carpetas, sin '..' y sin empezar con un punto."""
    if not _NOMBRE_SEGURO.match(valor) or ".." in valor:
        raise ValueError(
            f"Nombre de archivo inválido: {valor!r}. Usá solo letras, números, '.', '_' y '-' (sin carpetas ni '..')."
        )
    return valor


NombreArchivo = Annotated[str, AfterValidator(validar_nombre)]


def resolver_imagen_fondo(valor: str) -> Path:
    """Devuelve la ruta de una imagen de fondo SOLO si es un archivo existente
    dentro de `settings.media_root` (ej. "media/placas/umsa_fondo.png").
    Lanza ValueError para URLs, rutas fuera de media/ o archivos inexistentes."""
    if "://" in valor or valor.startswith(("http:", "https:", "rtmp:", "file:")):
        raise ValueError("imagen_fondo tiene que ser un archivo dentro de media/, no una URL")
    raiz = settings.media_root.resolve()
    ruta = Path(valor)
    ruta = (ruta if ruta.is_absolute() else Path.cwd() / ruta).resolve()
    if not ruta.is_relative_to(raiz):
        raise ValueError(f"imagen_fondo tiene que estar dentro de {settings.media_root}/ (ej. media/placas/...)")
    if not ruta.is_file():
        raise ValueError(f"imagen_fondo no existe: {valor}")
    return ruta
