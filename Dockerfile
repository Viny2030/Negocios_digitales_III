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

COPY app ./app
# El contenido real de media/videos vive en el Volume persistente de
# Railway (montado en runtime), no en la imagen — acá solo se copia la
# playlist inicial (vacía) y la estructura de carpetas.
COPY media ./media

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
