"""
api/v1/ai_generator.py — Disparo de generación de guiones y voces con IA.

Alcance actual: texto (LLM) y audio (TTS) sueltos, para revisar/aprobar
antes de convertirlos en clip de video. Armar el clip final (audio +
placa/fondo animado + subtítulos, como pide la grilla del documento para
bloques como "UMSA Despierta") es un paso más de edición con FFmpeg que
no está en el alcance de este scaffold inicial — queda como siguiente
paso natural una vez que se valide que los guiones/voces salen bien.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.ai_service import generar_guion, generar_voz

router = APIRouter(prefix="/ai", tags=["ai"])


class GuionRequest(BaseModel):
    tema: str
    contexto: str | None = None


class GuionResponse(BaseModel):
    guion: str


class VozRequest(BaseModel):
    texto: str
    nombre_archivo: str  # sin extensión — se guarda como <nombre_archivo>.mp3


class VozResponse(BaseModel):
    ruta_audio: str


@router.post("/guion", response_model=GuionResponse)
def crear_guion(body: GuionRequest) -> GuionResponse:
    return GuionResponse(guion=generar_guion(body.tema, body.contexto))


@router.post("/voz", response_model=VozResponse)
def crear_voz(body: VozRequest) -> VozResponse:
    ruta = generar_voz(body.texto, body.nombre_archivo)
    return VozResponse(ruta_audio=str(ruta))
