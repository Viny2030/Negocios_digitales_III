"""
main.py — Punto de entrada FastAPI: lifespan y registro de routers.

AUTOSTART (ver .env.example): si está en true, arranca el streamer solo al
levantar el proceso — pensado para producción en Railway, donde este
mismo servicio FastAPI ES el worker de emisión 24/7 (no un cron aparte:
tiene que quedar corriendo siempre, a diferencia de `ingesta_diaria` en el
otro proyecto). En local conviene dejarlo en false y arrancar a mano con
POST /api/v1/stream/start para no transmitir por accidente mientras
desarrollás.

SCHEDULER_ENABLED (ver .env.example, default true): arranca el selector
automático de bloque horario (core/scheduler.py) al levantar el proceso,
independientemente de AUTOSTART — el scheduler solo mantiene playlist.txt
sincronizada con la hora actual y llama a streamer.reload() si el streamer
ya está corriendo; no arranca la emisión por sí solo. Desactivalo en
desarrollo (SCHEDULER_ENABLED=false) si querés armar la playlist a mano vía
POST /api/v1/playlist sin que el scheduler te la pise en el próximo cambio
de bloque.

WATCHDOG_ENABLED (ver .env.example, default true): arranca el watchdog
(core/watchdog.py) que reinicia el streamer solo si se cae inesperadamente
mientras se suponía que tenía que seguir transmitiendo — necesario para que
la emisión sea de verdad PERMANENTE y no dependa de que alguien note un
corte y llame a POST /stream/start a mano.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as router_v1
from app.config import settings
from app.core.scheduler import scheduler
from app.core.streamer import streamer
from app.core.watchdog import watchdog

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # En producción (automático dentro de Railway) la app NO arranca sin
    # ADMIN_TOKEN: sin él, cualquiera con la URL pública puede cortar la
    # emisión o gastar el crédito de IA llamando a /ai/clip en loop.
    if settings.es_produccion and not settings.admin_token:
        raise RuntimeError(
            "APP_ENV=production y ADMIN_TOKEN vacío: la app no arranca. Configurá ADMIN_TOKEN "
            "en las variables del servicio en Railway (ver README, 'Proteger la API')."
        )
    if not settings.admin_token:
        logger.warning("ADMIN_TOKEN vacío: los endpoints de control quedan abiertos (aceptable solo en local).")

    if settings.scheduler_enabled:
        scheduler.start()
    if settings.watchdog_enabled:
        watchdog.start()
    if settings.autostart:
        try:
            logger.info("AUTOSTART=true — arrancando el streamer al levantar el servicio")
            streamer.start()
        except RuntimeError as e:
            logger.error(f"No se pudo autostart-ear el streamer: {e}")
    yield
    logger.info("Apagando servicio — deteniendo el streamer, el scheduler y el watchdog si estaban corriendo")
    watchdog.stop()
    scheduler.stop()
    streamer.stop()


app = FastAPI(
    title="UMSA Vivo & Conectada — Stream Engine",
    description="Control del streaming 24/7 (FFmpeg/RTMP), playlist, generación de contenido con IA y grilla horaria automática.",
    lifespan=lifespan,
)
app.include_router(router_v1, prefix="/api/v1")


@app.get("/")
def raiz() -> dict:
    return {"servicio": "umsa-stream-engine", "docs": "/docs"}
