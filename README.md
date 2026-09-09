# UMSA Vivo & Conectada — Stream Engine

Servicio FastAPI que controla la emisión 24/7 en YouTube Live (vía FFmpeg
+ RTMP), la playlist de clips, y la generación de contenido (guiones +
voz) con IA — scaffold inicial a partir del documento de arquitectura del
proyecto.

## Instalación y uso local

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
cp .env.example .env         # completar RTMP_STREAM_KEY como mínimo para poder transmitir
```

También hace falta `ffmpeg`/`ffprobe` instalados y en el PATH (en Windows,
por ejemplo, con `winget install ffmpeg` o descargando el build oficial).

```bash
uvicorn app.main:app --reload
```

Docs interactivas (Swagger) en `http://127.0.0.1:8000/docs`.

### Probar el streamer sin transmitir de verdad

Con `AUTOSTART=false` (default) el streamer no arranca solo. Para probarlo
sin gastar cuota de YouTube, se puede apuntar `RTMP_URL`/`RTMP_STREAM_KEY`
a un servidor RTMP local (ej. `mediamtx`) en vez de a YouTube.

## Cómo cargar clips a la playlist

1. Copiar el archivo de video a `media/videos/`.
2. **Normalizarlo primero** si no viene ya en el perfil fijo (1080p30,
   H.264/AAC — ver `app/services/media_service.py` y por qué esto importa
   para que `-c copy` funcione sin cortes):
   ```python
   from pathlib import Path
   from app.services.media_service import normalizar_clip
   normalizar_clip(Path("media/videos/original.mp4"), Path("media/videos/original_norm.mp4"))
   ```
3. Agregarlo a la playlist: `POST /api/v1/playlist` con
   `{"filename": "original_norm.mp4"}`.
4. Si el streamer ya está corriendo, `POST /api/v1/playlist/reload` para
   que tome el cambio (corta la señal un par de segundos, ver limitación
   documentada en `core/streamer.py`).

## Generar guion + voz con IA

```
POST /api/v1/ai/guion   {"tema": "Convocatoria a becas 2027", "contexto": "Inscripción hasta el 30/09"}
POST /api/v1/ai/voz     {"texto": "...", "nombre_archivo": "becas_2027", "voice_id": null}
```

Guion: sin `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` configuradas, devuelve un
texto placeholder marcado `[SIMULADO]` para poder probar el resto del
flujo sin tener las cuentas dadas de alta todavía.

Voz: se genera con [Piper](https://github.com/OHF-Voice/piper1-gpl) — TTS
neuronal que corre 100% local, sin API key ni cuota (así no se corta la
carga de un bloque entero a mitad de camino si se agota un plan pago, como
pasó con ElevenLabs — ver el FIX 2026-09-09 en `services/ai_service.py`).
Hace falta instalar el paquete y descargar el modelo de voz una sola vez:

```bash
pip install piper-tts   # ya está en requirements.txt
mkdir media\tts         # o el TTS_MODELS_DIR que hayas configurado
```

Descargar `es_AR-daniela-high.onnx` y `es_AR-daniela-high.onnx.json` (voz
en español rioplatense, acorde al tono del canal — ver `PROMPT_SISTEMA` en
`ai_service.py`) a `media/tts/`, desde
[huggingface.co/rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main/es/es_AR/daniela/high)
(o con `py -m piper.download_voices es_AR-daniela-high`, que los descarga
al directorio actual — moverlos después a `media/tts/`).

Sin el modelo descargado, `POST /api/v1/ai/voz` (y por lo tanto también
`/ai/clip`) devuelve igual un wav de silencio como placeholder, para poder
probar el resto del flujo sin tener el modelo bajado todavía. `voice_id`
es opcional: si no se pasa, usa `PIPER_VOICE_DEFAULT` del `.env` — sirve
para asignarle una voz distinta a cada bloque de la grilla de
programación (con su propio modelo descargado) sin tocar el `.env` cada
vez.

## Armar un clip completo (guion + voz + video) y sumarlo a la playlist

```
POST /api/v1/ai/clip
{
  "tema": "Convocatoria a becas 2027",
  "contexto": "Inscripción hasta el 30/09",
  "nombre_archivo": "becas_2027",
  "voice_id": null,
  "imagen_fondo": null,
  "color_fondo": "black",
  "agregar_a_playlist": true
}
```

Encadena `/guion` → `/voz` → armado del clip de video (audio narrado +
fondo) → alta en la playlist, todo en una sola llamada. Pensado para
probar un bloque de la grilla de punta a punta (ej. "UMSA Despierta")
antes de escalar a los seis bloques.

`imagen_fondo` es la ruta (en el servidor) a una placa o fondo
institucional ya preparado; si no se pasa, el clip se arma con un fondo
de color sólido (`color_fondo`, por defecto negro) — útil para probar el
pipeline antes de tener las placas gráficas definitivas. Si el clip ya
estaba en la playlist, `en_playlist` da `true` igual (no es un error).

Si el streamer ya está corriendo, después de agregar un clip hace falta
`POST /api/v1/stream/reload` para que lo tome (corta la señal un par de
segundos, ver limitación documentada en `core/streamer.py`).

**Todavía pendiente** (no cubierto por `/clip`): subtítulos automáticos y
placas dinámicas con datos en tiempo real (fecha, clima, agenda en
pantalla) — hoy el fondo es estático (imagen fija o color).

## Deploy en Railway

1. Compilar la imagen con el `Dockerfile` y subirla a Docker Hub (ver nota
   de costos: así Railway no gasta minutos de build).
2. Servicio en Railway apuntando a esa imagen, con un Volume montado en
   `/srv/media/videos` (persistente entre deploys — ahí van los clips
   reales, no en la imagen).
3. Variables de entorno: todas las de `.env.example`, con
   `AUTOSTART=true`.
4. A diferencia de un cron: este servicio tiene que quedar **siempre
   corriendo** (no es un job que termina), porque es el propio proceso
   FastAPI + ffmpeg el que sostiene la emisión 24/7.

## Decisiones técnicas a tener en cuenta

- **`-c copy` en el streamer** (ver `core/streamer.py`): consumo mínimo de
  CPU, pero exige que todos los clips compartan el mismo perfil técnico —
  por eso existe `normalizar_clip()`.
- **`reload()` no es un hot-swap real**: el demuxer concat de FFmpeg lee
  la playlist una sola vez al arrancar; reload = reiniciar el proceso.
- **Sin upload HTTP de clips**: los archivos de video pesan cientos de MB;
  subirlos por la misma API que sostiene el stream 24/7 es un riesgo de
  estabilidad innecesario para este alcance. Se copian directo a
  `media/videos/` (o al Volume de Railway) por otra vía (SFTP, `rsync`,
  panel de Railway).
