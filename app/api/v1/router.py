"""api/v1/router.py — Centralizador de endpoints v1."""
from fastapi import APIRouter

from app.api.v1 import ai_generator, playlist, stream

router = APIRouter()
router.include_router(stream.router)
router.include_router(playlist.router)
router.include_router(ai_generator.router)
