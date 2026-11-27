"""
scripts/renormalizar_clips.py — Recodifica los clips de media/videos al perfil
fijo actual (bitrate CBR y keyframe cada 2 s, ver services/media_service.py)
sin volver a generar guion ni voz: no gasta crédito de IA.

    python scripts/renormalizar_clips.py            # solo muestra qué haría
    python scripts/renormalizar_clips.py --aplicar  # recodifica los que no cumplen

Toma la carpeta de MEDIA_DIR (.env), así que sirve igual en local o dentro
del contenedor de Railway. Cada clip se escribe primero a un archivo temporal y
recién al final reemplaza al original: si ffmpeg falla, el original queda intacto.
Si el streamer está emitiendo, hacer POST /api/v1/stream/reload después.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.core.scheduler import EXTENSIONES_VIDEO  # noqa: E402
from app.services.media_service import PERFIL_AUDIO, _perfil_video  # noqa: E402


def _medir(ruta: Path) -> tuple[float, float]:
    """(bitrate de video en kbps, mayor distancia entre keyframes en s)."""
    br = subprocess.run(
        [settings.ffprobe_bin, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=bit_rate",
         "-of", "csv=p=0", str(ruta)],
        capture_output=True, text=True,
    ).stdout.strip()
    claves = subprocess.run(
        [settings.ffprobe_bin, "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey",
         "-show_entries", "frame=pts_time", "-of", "csv=p=0", str(ruta)],
        capture_output=True, text=True,
    ).stdout.split()
    tiempos = [float(t.strip(",")) for t in claves if t.strip(",")]
    gop = max((b - a for a, b in zip(tiempos, tiempos[1:], strict=False)), default=0.0)
    return (int(br) / 1000 if br.isdigit() else 0.0), gop


def main() -> int:
    aplicar = "--aplicar" in sys.argv
    objetivo = settings.video_bitrate_kbps
    clips = sorted(p for p in settings.media_dir.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES_VIDEO)
    pendientes = 0
    for clip in clips:
        kbps, gop = _medir(clip)
        ok = kbps >= 0.8 * objetivo and 0 < gop <= 4.0
        print(f"{'OK      ' if ok else 'RECODIF.'} {clip.name}: {kbps:.0f} kbps, keyframe cada {gop:.1f} s")
        if ok:
            continue
        pendientes += 1
        if not aplicar:
            continue
        tmp = clip.with_name(clip.stem + ".renorm.tmp.mp4")
        r = subprocess.run(
            [settings.ffmpeg_bin, "-v", "error", "-y", "-i", str(clip), *_perfil_video(), *PERFIL_AUDIO, str(tmp)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            tmp.unlink(missing_ok=True)
            print(f"   ERROR: {r.stderr[-400:]}")
            continue
        os.replace(tmp, clip)
        kbps, gop = _medir(clip)
        print(f"   -> {kbps:.0f} kbps, keyframe cada {gop:.1f} s")
    if pendientes and not aplicar:
        print(f"\n{pendientes} clip(s) por recodificar. Correr con --aplicar para hacerlo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
