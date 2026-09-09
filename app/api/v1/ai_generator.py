"""
api/v1/ai_generator.py — Disparo de generación de guiones y voces con IA.

/guion y /voz devuelven texto/audio sueltos, para revisar o aprobar antes
de armar el clip final. /clip encadena las tres cosas (guion → voz →
video) y opcionalmente lo suma directo a la playlist — es el paso que en
la versión inicial del scaffold quedaba marcado como "fuera de alcance",
ya cubierto ahora por services/media_service.armar_clip_narrado.

Pendiente real para más adelante (no cubierto todavía): subtítulos
automáticos y placas dinámicas con datos (fecha, clima, agenda en
pantalla) — hoy el fondo es una imagen fija o un color sólido.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.v1.playlist import agregar
from app.config import settings
from app.schemas.playlist import AddClipRequest
from app.services.ai_service import generar_guion, generar_voz
from app.services.media_service import MediaValidationError, armar_clip_narrado

router = APIRouter(prefix="/ai", tags=["ai"])


class GuionRequest(BaseModel):
    tema: str
    contexto: str | None = None


class GuionResponse(BaseModel):
    guion: str


class VozRequest(BaseModel):
    texto: str
    nombre_archivo: str  # sin extensión — se guarda como <nombre_archivo>.wav
    voice_id: str | None = None  # nombre de un modelo Piper ya descargado; pisa PIPER_VOICE_DEFAULT del .env para esta llamada puntual


class VozResponse(BaseModel):
    ruta_audio: str


class ClipRequest(BaseModel):
    tema: str
    contexto: str | None = None
    nombre_archivo: str  # sin extensión — nombre base para el .mp3 y el .mp4 resultantes
    voice_id: str | None = None  # modelo de voz Piper para este bloque (ver plan de contenido)
    imagen_fondo: str | None = None  # ruta a una placa/fondo institucional ya subida al servidor
    color_fondo: str = "black"  # se usa solo si no se pasa imagen_fondo
    agregar_a_playlist: bool = True


class ClipResponse(BaseModel):
    guion: str
    ruta_audio: str
    ruta_video: str
    en_playlist: bool


@router.post("/guion", response_model=GuionResponse)
def crear_guion(body: GuionRequest) -> GuionResponse:
    return GuionResponse(guion=generar_guion(body.tema, body.contexto))


@router.post("/voz", response_model=VozResponse)
def crear_voz(body: VozRequest) -> VozResponse:
    ruta = generar_voz(body.texto, body.nombre_archivo, voice_id=body.voice_id)
    return VozResponse(ruta_audio=str(ruta))


@router.post("/clip", response_model=ClipResponse)
def crear_clip(body: ClipRequest) -> ClipResponse:
    """Genera el guion, lo sintetiza a voz, arma el clip de video (audio +
    fondo) y —salvo que se indique lo contrario— lo agrega al final de la
    playlist que lee el streamer. Pensado para probar un bloque de la
    grilla de punta a punta (ej. tema="Convocatoria a becas 2027" para el
    bloque "UMSA Despierta") con una sola llamada."""
    guion = generar_guion(body.tema, body.contexto)
    ruta_audio = generar_voz(guion, body.nombre_archivo, voice_id=body.voice_id)

    ruta_video = settings.media_dir / f"{body.nombre_archivo}.mp4"
    imagen = Path(body.imagen_fondo) if body.imagen_fondo else None
    try:
        armar_clip_narrado(ruta_audio, ruta_video, imagen_fondo=imagen, color_fondo=body.color_fondo)
    except MediaValidationError as e:
        raise HTTPException(status_code=500, detail=str(e))

    en_playlist = False
    if body.agregar_a_playlist:
        try:
            agregar(AddClipRequest(filename=ruta_video.name))
            en_playlist = True
        except HTTPException as e:
            if e.status_code == 409:  # ya estaba en la playlist — no es un error acá
                en_playlist = True
            else:
                raise

    return ClipResponse(
        guion=guion,
        ruta_audio=str(ruta_audio),
        ruta_video=str(ruta_video),
        en_playlist=en_playlist,
    )
