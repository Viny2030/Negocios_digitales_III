"""
services/media_service.py — Validación y normalización de clips con
FFprobe/FFmpeg.

Por qué existe esto (ver también core/streamer.py): el streamer transmite
con `-c copy` (sin recodificar) para que el consumo de CPU en Railway sea
mínimo — es la base de la estimación de costos del documento del
proyecto. Pero el demuxer concat de FFmpeg con stream copy solo funciona
de forma confiable si TODOS los clips comparten el mismo perfil técnico
(códec de video/audio, resolución, fps, sample rate). Si se agrega un
clip con un perfil distinto tal cual viene (ej. un webinar exportado en
otro formato), lo más probable es que el stream se corte o el audio se
desincronice apenas le toque el turno en el loop.

`normalizar_clip()` resuelve esto UNA vez, al ingestar el clip (no en cada
arranque del streamer): lo recodifica al perfil fijo definido acá abajo.
Sí consume CPU en ese momento puntual — pero es un costo de ingesta, no
de la emisión 24/7 continua, que es la que hay que mantener barata.
"""
from __future__ import annotations

import json
import logging
import subprocess
import textwrap
from pathlib import Path

from app.config import settings

logger = logging.getLogger("media_service")

# Perfil técnico fijo al que se normaliza todo clip antes de sumarlo a la
# playlist. 1080p30 coincide con lo que ya asume el documento de costos
# ("1080p30 para contenido institucional y diapositivas").
#
# FIX 2026-09-09: el filtro de escala era "scale=1920:1080" a secas, que
# estira la imagen para llenar el cuadro sin respetar el aspect ratio
# original. No se notaba porque el único fondo que existía hasta ahora
# (umsa_fondo.png) ya venía en 16:9. Al sumar como fondo una captura real
# de cada página de umsa.edu.ar (ver services/ai_service.py y
# api/v1/ai_generator.py) aparecieron imágenes verticales o casi cuadradas
# (ej. la nota de "vinculación institucional" o la placa de Bioética) que
# con el filtro viejo salían deformadas. Ahora se escala respetando el
# aspect ratio original (force_original_aspect_ratio=decrease) y se
# rellena el resto del cuadro 1920x1080 con barras negras (pad) en vez de
# estirar — mismo resultado que antes para un fondo que ya es 16:9.
#
# FIX 2026-11-27: YouTube avisaba "la tasa de bits es inferior a la
# recomendada". Una placa fija con la configuración por defecto de libx264
# pesaba 0,05-0,3 Mbps (YouTube pide ~4-10 Mbps CBR para 1080p30) y además
# ponía un keyframe cada 8,3 s (YouTube: cada 2 s, nunca más de 4, GOP
# cerrado). Como el streamer emite con -c copy, esto se resuelve acá, al
# generar cada clip: bitrate constante (nal-hrd=cbr rellena con "filler" lo
# que una imagen fija no necesita) y keyframe fijo cada 2 s. Los clips viejos
# hay que recodificarlos: scripts/renormalizar_clips.py (no gasta IA).
def _perfil_video(escalar: bool = True) -> list[str]:
    """`escalar=False` cuando el que llama arma su propio filtro de video
    (armar_clip_narrado ya entrega 1920x1080): -vf y -filter_complex no se
    pueden combinar sobre la misma salida."""
    kbps = settings.video_bitrate_kbps
    escala = (
        ["-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black"]
        if escalar
        else []
    )
    return [
        "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-r", "30",
        *escala,
        "-b:v", f"{kbps}k", "-minrate", f"{kbps}k", "-maxrate", f"{kbps}k", "-bufsize", f"{2 * kbps}k",
        "-x264-params", "nal-hrd=cbr",
        "-g", "60", "-keyint_min", "60", "-sc_threshold", "0", "-flags", "+cgop",  # keyframe cada 2 s a 30 fps, GOP cerrado
    ]
# FIX 2026-09-04: sin "-pix_fmt yuv420p" explícito, libx264 puede terminar
# heredando el espacio de color del origen (ej. rgb24 o 4:4:4) y el perfil
# "high" rechaza eso de entrada ("high profile doesn't support 4:4:4") —
# se vio en la práctica probando con un clip sintético (ffmpeg testsrc).
# Con clips reales (casi siempre ya en yuv420p) el bug no se nota, pero
# conviene forzarlo igual: es también el formato más compatible para
# ingesta RTMP en general.
PERFIL_AUDIO = ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]

# Ida y vuelta del acercamiento sobre la placa (ver armar_clip_narrado).
CICLO_ZOOM_SEG = 40


class MediaValidationError(Exception):
    pass


def probar_clip(path: Path) -> dict:
    """Corre ffprobe y devuelve duración, códec de video/audio y resolución.
    Lanza MediaValidationError si el archivo no es un media válido."""
    comando = [
        settings.ffprobe_bin, "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    ]
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise MediaValidationError(f"ffprobe falló para {path.name}: {resultado.stderr.strip()}")

    data = json.loads(resultado.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if video is None:
        raise MediaValidationError(f"{path.name} no tiene stream de video")

    return {
        "duracion_seg": float(data.get("format", {}).get("duration", 0.0)),
        "codec_video": video.get("codec_name"),
        "codec_audio": audio.get("codec_name") if audio else None,
        "resolucion": f"{video.get('width')}x{video.get('height')}",
    }


_FUENTES_CANDIDATAS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # imagen Docker (fonts-dejavu-core)
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _fuente_rotulos() -> str | None:
    if settings.fuente_rotulos:
        return settings.fuente_rotulos if Path(settings.fuente_rotulos).exists() else None
    return next((f for f in _FUENTES_CANDIDATAS if Path(f).exists()), None)


def _ruta_filtro(ruta: Path | str) -> str:
    """Ruta escapada para una opción de filtro de ffmpeg: barras normales y
    el ':' de la unidad de Windows escapado (si no, ffmpeg lo toma como
    separador de opciones)."""
    return "'" + str(ruta).replace("\\", "/").replace(":", "\\:") + "'"


def _duracion_audio(ruta: Path) -> float:
    r = subprocess.run(
        [settings.ffprobe_bin, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError as e:
        raise MediaValidationError(f"No se pudo medir la duración de {ruta.name}: {r.stderr.strip()}") from e


def _componer_placa(imagen: Path, destino: Path) -> None:
    """Placa 1920x1080 en un solo cuadro: la imagen entera, centrada, sobre una
    copia ampliada y desenfocada de sí misma (en vez de barras negras cuando
    la placa es vertical o cuadrada). Se calcula UNA vez por clip: hacerlo en
    cada cuadro triplicaba el tiempo de codificación."""
    filtro = (
        "[0:v]split[a][b];"
        "[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=25:5,setsar=1[fondo];"
        "[b]scale=1920:1080:force_original_aspect_ratio=decrease,setsar=1[frente];"
        "[fondo][frente]overlay=(W-w)/2:(H-h)/2"
    )
    r = subprocess.run(
        [settings.ffmpeg_bin, "-v", "error", "-y", "-i", str(imagen), "-filter_complex", filtro,
         "-frames:v", "1", str(destino)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise MediaValidationError(f"ffmpeg no pudo componer la placa {imagen.name}: {r.stderr[-500:]}")


def _filtro_rotulo(rotulo: str, rotulo_secundario: str | None, carpeta: Path, base: str) -> tuple[str, list[Path]]:
    """Franja inferior semitransparente con el nombre (en 1 o 2 líneas) y una
    línea secundaria (ej. la facultad). Los textos van por `textfile` y no
    inline: así no hay que escapar ':' ni comillas ni '%' de nombres reales."""
    fuente = _fuente_rotulos()
    if fuente is None:
        logger.warning("No hay fuente para el rótulo (FUENTE_ROTULOS o fonts-dejavu): el clip sale sin rótulo.")
        return "", []
    lineas = textwrap.wrap(rotulo, 58) or [rotulo]  # ~58 caracteres entran en 1760 px a 52 pt
    alto_titulo = 62  # 52 pt + line_spacing 10
    alto_franja = 36 + alto_titulo * len(lineas) + (64 if rotulo_secundario else 0)
    archivos = [carpeta / f".{base}.rotulo.txt"]
    # newline="\n": en Windows write_text escribe \r\n y ffmpeg dibuja el \r como un salto de línea extra.
    archivos[0].write_text("\n".join(lineas), encoding="utf-8", newline="\n")
    partes = [
        f"drawbox=x=0:y=ih-{alto_franja}:w=iw:h={alto_franja}:color=black@0.6:t=fill",
        f"drawtext=fontfile={_ruta_filtro(fuente)}:textfile={_ruta_filtro(archivos[0])}:expansion=none"
        f":fontcolor=white:fontsize=52:line_spacing=10:x=80:y=h-{alto_franja - 28}",
    ]
    if rotulo_secundario:
        archivos.append(carpeta / f".{base}.rotulo2.txt")
        archivos[1].write_text(rotulo_secundario, encoding="utf-8", newline="\n")
        partes.append(
            f"drawtext=fontfile={_ruta_filtro(fuente)}:textfile={_ruta_filtro(archivos[1])}:expansion=none"
            f":fontcolor=white@0.85:fontsize=34:x=80:y=h-54"
        )
    return ",".join(partes), archivos


def armar_clip_narrado(
    audio_path: Path,
    destino: Path,
    imagen_fondo: Path | None = None,
    color_fondo: str = "black",
    rotulo: str | None = None,
    rotulo_secundario: str | None = None,
) -> Path:
    """Arma un clip de video a partir de un audio narrado (ver
    services/ai_service.generar_voz) y un fondo fijo: una imagen (placa
    institucional) si se pasa `imagen_fondo`, o un color sólido generado
    con el filtro `lavfi` si todavía no hay una placa/fondo real para ese
    contenido.

    Este era el paso que quedaba pendiente en el scaffold inicial (ver el
    docstring anterior de api/v1/ai_generator.py): conecta guion + voz con
    la playlist real, para poder probar un bloque de la grilla de punta a
    punta (ej. "UMSA Despierta") sin depender de que ya exista el video
    institucional definitivo — cuando haya placas/fondos reales, basta con
    pasar `imagen_fondo` en vez de dejarlo en None.

    Codifica directo al PERFIL_VIDEO/PERFIL_AUDIO fijo del proyecto — no
    hace falta pasar el resultado por normalizar_clip() después, ya sale
    compatible con el `-c copy` del streamer apenas se agrega a la
    playlist.

    CAMBIO 2026-11-27 ("los clips son fijos"): la placa ya no queda quieta.
    Tiene un acercamiento lento de ida y vuelta (hasta 8 %, ciclo de
    CICLO_ZOOM_SEG), fondo desenfocado en vez de barras negras y, si se pasa
    `rotulo`, una franja inferior con el nombre de la carrera y la facultad.
    La duración se fija a la del audio (`-t`): con `-shortest` y una imagen en
    loop quedaban ~2 s de video mudo al final de cada clip.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    duracion = _duracion_audio(audio_path)
    temporales: list[Path] = []

    if imagen_fondo is not None:
        placa = destino.parent / f".{destino.stem}.placa.png"
        _componer_placa(imagen_fondo, placa)
        temporales.append(placa)
        entrada_video = ["-loop", "1", "-framerate", "30", "-i", str(placa)]
        # Zoom suave 1 → 1,08 → 1 cada CICLO_ZOOM_SEG; ancho par para libx264.
        ciclo = CICLO_ZOOM_SEG * 30
        filtro = (
            f"scale=w='trunc(1920*(1+0.04*(1-cos(2*PI*n/{ciclo})))/2)*2':h=-2:eval=frame:flags=bicubic,"
            "crop=1920:1080"
        )
    else:
        entrada_video = ["-f", "lavfi", "-i", f"color=c={color_fondo}:s=1920x1080:r=30"]
        filtro = "null"

    if rotulo:
        filtro_rotulo, archivos = _filtro_rotulo(rotulo, rotulo_secundario, destino.parent, destino.stem)
        temporales += archivos
        if filtro_rotulo:
            filtro += "," + filtro_rotulo

    comando = [
        settings.ffmpeg_bin, "-y",
        *entrada_video,
        "-i", str(audio_path),
        "-filter_complex", f"[0:v]{filtro},setsar=1[v]",
        "-map", "[v]", "-map", "1:a",
        *_perfil_video(escalar=False), *PERFIL_AUDIO,
        "-t", f"{duracion:.3f}",
        str(destino),
    ]
    logger.info(
        f"Armando clip narrado {destino.name} ({duracion:.1f} s, "
        f"fondo={'imagen ' + imagen_fondo.name if imagen_fondo else color_fondo})"
    )
    try:
        resultado = subprocess.run(comando, capture_output=True, text=True)
    finally:
        for t in temporales:
            t.unlink(missing_ok=True)
    if resultado.returncode != 0:
        raise MediaValidationError(f"ffmpeg no pudo armar el clip {destino.name}: {resultado.stderr[-800:]}")
    return destino


def normalizar_clip(origen: Path, destino: Path) -> Path:
    """Recodifica `origen` al perfil técnico fijo y lo guarda en `destino`.
    Idempotente: si `destino` ya existe, no vuelve a recodificar."""
    if destino.exists():
        logger.info(f"{destino.name} ya estaba normalizado — se reusa")
        return destino

    destino.parent.mkdir(parents=True, exist_ok=True)
    comando = [
        settings.ffmpeg_bin, "-y", "-i", str(origen),
        *_perfil_video(), *PERFIL_AUDIO,
        str(destino),
    ]
    logger.info(f"Normalizando {origen.name} → {destino.name}")
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise MediaValidationError(f"ffmpeg no pudo normalizar {origen.name}: {resultado.stderr[-800:]}")
    return destino
