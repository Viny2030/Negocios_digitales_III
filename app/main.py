"""
main.py — Punto de entrada FastAPI: lifespan y registro de routers.

AUTOSTART (ver .env.example): si está en true, arranca el streamer solo al
levantar el proceso — pensado para producción en Railway, donde este
mismo servicio FastAPI ES el worker de emisión 24/7 (no un cron aparte:
tiene que quedar corriendo siempre, a diferencia de `ingesta_diaria` en el
otro proyecto). En local conviene dejarlo en false y arrancar a mano con
POST /api/v1/stream/start para no transmitir por accidente mientras
desarrollás.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as router_v1
from app.config import settings
from app.core.streamer import streamer

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.autostart:
        try:
            logger.info("AUTOSTART=true — arrancando el streamer al levantar el servicio")
            streamer.start()
        except RuntimeError as e:
            logger.error(f"No se pudo autostart-ear el streamer: {e}")
    yield
    logger.info("Apagando servicio — deteniendo el streamer si estaba corriendo")
    streamer.stop()


app = FastAPI(
    title="UMSA Vivo & Conectada — Stream Engine",
    description="Control del streaming 24/7 (FFmpeg/RTMP), playlist y generación de contenido con IA.",
    lifespan=lifespan,
)
app.include_router(router_v1, prefix="/api/v1")


@app.get("/")
def raiz() -> dict:
    return {"servicio": "umsa-stream-engine", "docs": "/docs"}
