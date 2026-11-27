"""
services/subtitulos.py — Subtítulos SRT de los clips narrados (español e inglés).

Los tiempos NO se estiman: ai_service.sintetizar_oraciones() genera la voz
oración por oración y devuelve cuándo empieza y termina cada una en el wav
final. Acá solo se convierten esos tiempos + los textos (el guion original en
español, o su traducción al inglés, una por oración y en el mismo orden) en un
archivo .srt.

Los .srt se guardan en settings.subtitulos_dir (por default
media/videos/subtitulos): una subcarpeta del Volume de Railway, así persisten
entre deploys junto a los clips. El scheduler solo toma archivos de video de
media/videos (ver core/scheduler.py), nunca entra a esta subcarpeta.

Reglas de legibilidad (convención habitual de subtitulado): como máximo 2
líneas de 42 caracteres por subtítulo. Una oración más larga se parte en
varios subtítulos seguidos, repartiendo su tiempo según la cantidad de
caracteres de cada parte.
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

from app.config import settings

ANCHO_LINEA = 42
MAX_LINEAS = 2

# Corta después de . ! ? o … seguidos de espacio. No corta "1.500" ni "30/09"
# (no hay espacio después del punto).
_FIN_DE_ORACION = re.compile(r"(?<=[.!?…])\s+")


def dividir_oraciones(texto: str) -> list[str]:
    """Separa un guion en oraciones. Los saltos de línea también separan (un
    título o una línea suelta del guion queda como su propia oración)."""
    oraciones: list[str] = []
    for linea in texto.splitlines():
        linea = " ".join(linea.split())
        oraciones.extend(o for o in _FIN_DE_ORACION.split(linea) if o)
    return oraciones


def _tiempo_srt(segundos: float) -> str:
    ms = round(max(segundos, 0.0) * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def partir_en_subtitulos(texto: str, inicio: float, fin: float) -> list[tuple[float, float, str]]:
    """Parte una oración en subtítulos de hasta MAX_LINEAS líneas de
    ANCHO_LINEA caracteres, repartiendo [inicio, fin] según la cantidad de
    caracteres de cada parte."""
    lineas = textwrap.wrap(texto, ANCHO_LINEA) or [texto]
    partes = ["\n".join(lineas[i : i + MAX_LINEAS]) for i in range(0, len(lineas), MAX_LINEAS)]
    total = sum(len(p) for p in partes)
    resultado, t = [], inicio
    for i, parte in enumerate(partes):
        t_fin = fin if i == len(partes) - 1 else t + (fin - inicio) * len(parte) / total
        resultado.append((t, t_fin, parte))
        t = t_fin
    return resultado


def generar_srt(textos: list[str], tiempos: list[tuple[float, float]]) -> str:
    """`textos[i]` se muestra entre `tiempos[i][0]` y `tiempos[i][1]` (segundos)."""
    if len(textos) != len(tiempos):
        raise ValueError(f"{len(textos)} textos para {len(tiempos)} tiempos: tienen que coincidir uno a uno")
    bloques = []
    for texto, (inicio, fin) in zip(textos, tiempos, strict=True):
        for ini, f, parte in partir_en_subtitulos(texto, inicio, fin):
            bloques.append(f"{len(bloques) + 1}\n{_tiempo_srt(ini)} --> {_tiempo_srt(f)}\n{parte}\n")
    return "\n".join(bloques)


def ruta_subtitulos(nombre_archivo: str, idioma: str) -> Path:
    return settings.subtitulos_dir / f"{nombre_archivo}.{idioma}.srt"


def guardar_srt(nombre_archivo: str, idioma: str, contenido: str) -> Path:
    destino = ruta_subtitulos(nombre_archivo, idioma)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8", newline="\n")
    return destino
