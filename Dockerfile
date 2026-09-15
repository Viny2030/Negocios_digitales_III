# Imagen liviana con FFmpeg — se compila acá y se sube a Docker Hub para que
# Railway solo descargue la imagen ya armada (ver la nota de "Imágenes
# ligeras vía Docker Hub" del documento de costos: evita gastar minutos de
# build de CPU dentro de Railway).
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Modelo de voz Piper horneado en la imagen, en una ruta FUERA del Volume
# de Railway (que solo cubre /srv/media/videos — ver README, sección
# "Deploy en Railway"): así el TTS funciona desde el primer arranque, sin
# el paso manual de descarga documentado para desarrollo local, que además
# se perdería en cada redeploy si viviera dentro de /srv/media. En Railway
# hay que apuntar TTS_MODELS_DIR=/srv/tts_models (ver .env.example) para
# que la app busque acá en vez de en el default local media/tts. Cambiar
# el ARG si se define otra voz en PIPER_VOICE_DEFAULT.
ARG PIPER_VOICE_BAKED=es_AR-daniela-high
RUN python -m piper.download_voices --download-dir /srv/tts_models ${PIPER_VOICE_BAKED}

COPY app ./app
# El contenido real de media/videos vive en el Volume persistente de
# Railway (montado en runtime), no en la imagen — acá solo se copia la
# playlist inicial (vacía) y la estructura de carpetas.
COPY media ./media

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Forma "shell" (no exec/JSON array) a propósito: así se expande la
# variable de entorno. Railway inyecta PORT dinámicamente; si el
# contenedor no escucha en ese puerto, el healthcheck falla y el deploy
# nunca queda "healthy". El fallback ${PORT:-8000} deja `docker run`
# local funcionando igual que antes.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
