"""
web.py — Página pública del canal: video en vivo, manual y grafos, en
español (/) e inglés (/en).

Los HTML se generan con scripts/generar_sitio.py (no editarlos a mano). Traen
el marcador __VIDEO__, que acá se reemplaza por el reproductor de YouTube del
canal configurado en YOUTUBE_CHANNEL_ID, o por un aviso si no hay canal. El ID
se valida contra el formato de YouTube (UC + 22 caracteres) antes de meterlo
en el HTML, para que una variable mal cargada no pueda inyectar nada.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.config import settings

router = APIRouter(include_in_schema=False)

_ESTATICOS = Path(__file__).parent / "static"
_CANAL_VALIDO = re.compile(r"^UC[A-Za-z0-9_-]{22}$")

_AVISOS = {
    "es": "Todavía no hay un canal de YouTube configurado para esta página (variable YOUTUBE_CHANNEL_ID).",
    "en": "No YouTube channel has been set for this page yet (YOUTUBE_CHANNEL_ID variable).",
}
_TITULOS = {"es": "Transmisión en vivo del canal UMSA", "en": "UMSA channel live stream"}


@lru_cache(maxsize=2)
def _plantilla(lang: str) -> str:
    return (_ESTATICOS / f"sitio_{lang}.html").read_text(encoding="utf-8")


def reproductor(lang: str, canal: str) -> str:
    if not _CANAL_VALIDO.match(canal or ""):
        return f'<div class="aviso">{_AVISOS[lang]}</div>'
    return (
        f'<iframe src="https://www.youtube-nocookie.com/embed/live_stream?channel={canal}" '
        f'title="{_TITULOS[lang]}" loading="lazy" referrerpolicy="strict-origin-when-cross-origin" '
        'allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>'
    )


def _pagina(lang: str) -> HTMLResponse:
    html = _plantilla(lang).replace("__VIDEO__", reproductor(lang, settings.youtube_channel_id))
    return HTMLResponse(html)


@router.get("/", response_class=HTMLResponse)
def sitio_es() -> HTMLResponse:
    return _pagina("es")


@router.get("/en", response_class=HTMLResponse)
def sitio_en() -> HTMLResponse:
    return _pagina("en")
