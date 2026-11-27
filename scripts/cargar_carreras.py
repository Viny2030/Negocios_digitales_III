"""
scripts/cargar_carreras.py — Clips de todas las carreras de la UMSA (core/catalogo.py).

    python scripts/cargar_carreras.py                 # estado: qué carreras tienen clip y subtítulos
    python scripts/cargar_carreras.py --renombrar     # pasa los clips viejos (foco_grado_*, posgrado_*) al nombre nuevo
    python scripts/cargar_carreras.py --contexto      # busca la ficha oficial de las que faltan y muestra qué se usaría (sin IA)
    python scripts/cargar_carreras.py --generar [--limite N] [--api http://127.0.0.1:8000] [--sin-ia]
                                                      # genera con POST /api/v1/ai/clip las que faltan
    python scripts/cargar_carreras.py --validar-guiones

Guiones escritos a mano: si existe contenido/guiones/<nombre_archivo>.json
({"fuente": url, "guion": "...", "guion_en": [una traducción por oración]}),
--generar lo usa tal cual y NO llama al LLM (no gasta crédito de API). Sin
ese archivo, el guion lo escribe el LLM (GASTA crédito); --sin-ia saltea esas.

El guion de cada carrera se escribe a partir del texto de su ficha en
umsa.edu.ar (se busca el link en el listado oficial de grado o de posgrado):
el LLM no inventa duraciones ni planes, los toma de ahí. Conviene mirar la
salida de --contexto antes de --generar.

--generar usa la API (el servidor tiene que estar corriendo) y manda
X-Admin-Token si la variable de entorno ADMIN_TOKEN está seteada. Reemplaza a
cargar_bloques.ps1 y compañía, que usaban los nombres de la grilla anterior.
"""
from __future__ import annotations

import json
import os
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.core.catalogo import FACULTADES, PROGRAMAS, RENOMBRES_ANTERIORES, Programa  # noqa: E402
from app.services.subtitulos import dividir_oraciones, ruta_subtitulos  # noqa: E402

GUIONES = Path(__file__).resolve().parent.parent / "contenido" / "guiones"

LISTADOS = {
    "grado": "https://www.umsa.edu.ar/carreras-de-grado/",
    "posgrado": "https://www.umsa.edu.ar/posgrados/",
}
MAX_CONTEXTO = 3500  # caracteres de la ficha que se le pasan al LLM
CLIENTE = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "umsa-stream-engine/1.0"})


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().replace("–", " ").replace("-", " ").split())


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._texto: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href, self._texto = dict(attrs).get("href"), []

    def handle_data(self, data):
        if self._href is not None:
            self._texto.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            self.links.append((" ".join("".join(self._texto).split()), self._href))
            self._href = None


class _Texto(HTMLParser):
    _OMITIR = {"script", "style", "nav", "header", "footer", "noscript", "svg"}

    def __init__(self):
        super().__init__()
        self.partes: list[str] = []
        self._omitiendo = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._OMITIR:
            self._omitiendo += 1

    def handle_endtag(self, tag):
        if tag in self._OMITIR and self._omitiendo:
            self._omitiendo -= 1

    def handle_data(self, data):
        if not self._omitiendo and data.strip():
            self.partes.append(" ".join(data.split()))


_cache_listados: dict[str, list[tuple[str, str]]] = {}


def url_ficha(programa: Programa) -> str | None:
    """Link a la ficha de la carrera en el listado oficial de su nivel."""
    if programa.nivel not in _cache_listados:
        p = _Links()
        p.feed(CLIENTE.get(LISTADOS[programa.nivel]).text)
        _cache_listados[programa.nivel] = p.links
    buscado = _normalizar(programa.nombre)
    candidatos = [(t, h) for t, h in _cache_listados[programa.nivel] if t and ("/carrera" in h or "/posgrado" in h)]
    for texto, href in candidatos:
        if _normalizar(texto) == buscado:
            return urljoin(LISTADOS[programa.nivel], href)
    for texto, href in candidatos:  # ej. el link dice solo "Abogacía" o agrega la modalidad
        t = _normalizar(texto)
        if t and (buscado in t or t in buscado) and len(t) > 6:
            return urljoin(LISTADOS[programa.nivel], href)
    return None


def contexto_de(programa: Programa) -> tuple[str | None, str]:
    url = url_ficha(programa)
    if url is None:
        return None, ""
    p = _Texto()
    p.feed(CLIENTE.get(url).text)
    texto = " ".join(p.partes)
    # La ficha empieza con el menú del sitio aunque se omita <nav>: se arranca
    # desde la primera aparición del nombre de la carrera, si está.
    i = _normalizar(texto).find(_normalizar(programa.nombre).split(" ")[-1])
    return url, texto[max(0, i - 200) if i > 0 else 0 :][:MAX_CONTEXTO]


def tiene_clip(p: Programa) -> bool:
    return (settings.media_dir / f"{p.nombre_archivo}.mp4").exists()


def estado() -> None:
    for clave, f in FACULTADES.items():
        print(f"\n{f.nombre} ({f.prefijo}*)")
        for p in (x for x in PROGRAMAS if x.facultad == clave):
            subs = "+".join(i for i in ("es", "en") if ruta_subtitulos(p.nombre_archivo, i).exists()) or "sin subtítulos"
            print(f"  {'OK ' if tiene_clip(p) else '-- '} {p.nivel:8} {p.nombre}  [{subs}]")
    faltan = sum(not tiene_clip(p) for p in PROGRAMAS)
    print(f"\n{len(PROGRAMAS) - faltan}/{len(PROGRAMAS)} carreras con clip. Faltan {faltan}.")


def renombrar() -> None:
    for viejo, nuevo in RENOMBRES_ANTERIORES.items():
        origen, destino = settings.media_dir / f"{viejo}.mp4", settings.media_dir / f"{nuevo}.mp4"
        if not origen.exists():
            continue
        if destino.exists():
            print(f"  salteado {viejo}: ya existe {destino.name}")
            continue
        origen.rename(destino)
        for idioma in ("es", "en"):
            srt = ruta_subtitulos(viejo, idioma)
            if srt.exists():
                srt.rename(ruta_subtitulos(nuevo, idioma))
        print(f"  {origen.name} -> {destino.name}")


def guion_escrito(p: Programa) -> dict | None:
    """Guion ya escrito y revisado en contenido/guiones/<nombre_archivo>.json
    ({"guion": "...", "guion_en": [...]}): se usa en vez de pedírselo al LLM."""
    ruta = GUIONES / f"{p.nombre_archivo}.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def validar_guiones() -> int:
    """Cada guion_en tiene que tener una entrada por oración del guion (así
    hereda sus tiempos en los subtítulos)."""
    errores = 0
    for p in PROGRAMAS:
        g = guion_escrito(p)
        if g is None:
            continue
        n_es, n_en = len(dividir_oraciones(g["guion"])), len(g["guion_en"])
        palabras = len(g["guion"].split())
        estado = "OK " if n_es == n_en else "MAL"
        errores += n_es != n_en
        print(f"  {estado} {p.nombre_archivo}: {n_es} oraciones es / {n_en} en, {palabras} palabras")
    return 1 if errores else 0


def generar(api: str, limite: int | None, mostrar_solo: bool, sin_ia: bool = False) -> int:
    faltantes = [p for p in PROGRAMAS if not tiene_clip(p)][:limite]
    headers = {"X-Admin-Token": os.environ["ADMIN_TOKEN"]} if os.environ.get("ADMIN_TOKEN") else {}
    errores = 0
    for p in faltantes:
        escrito = guion_escrito(p)
        if escrito is None and sin_ia:
            print(f"\n== {p.nombre_archivo}: sin guion escrito en {GUIONES.name}/ — se saltea (--sin-ia)")
            continue
        url, contexto = (escrito.get("fuente"), "guion escrito") if escrito else contexto_de(p)
        print(f"\n== {p.nombre_archivo}  ({p.nombre})\n   ficha: {url or 'NO ENCONTRADA'}")
        if not contexto:
            print("   sin ficha: se saltea (no se genera un guion sin datos oficiales)")
            errores += 1
            continue
        if mostrar_solo:
            print(f"   contexto ({len(contexto)} car.): {contexto[:300]}…")
            continue
        facultad = FACULTADES[p.facultad].nombre
        cuerpo = {
            "tema": f"{p.nombre} — {facultad}, UMSA ({p.nivel}, modalidad {p.modalidad})",
            "contexto": f"Datos oficiales de la ficha de la carrera ({url}). Usá solo estos datos:\n{contexto}",
            "nombre_archivo": p.nombre_archivo,
            "imagen_fondo": p.placa,
            "rotulo": p.nombre,
            "rotulo_secundario": f"{facultad} · {p.nivel.capitalize()} · {p.modalidad}",
            "agregar_a_playlist": False,  # la playlist la arma el scheduler según la franja de cada facultad
        }
        if escrito:
            cuerpo.update(guion=escrito["guion"], guion_en=escrito["guion_en"])
        try:
            r = CLIENTE.post(f"{api}/api/v1/ai/clip", json=cuerpo, headers=headers, timeout=600)
            r.raise_for_status()
            print(f"   OK -> {r.json()['ruta_video']}")
        except httpx.HTTPError as e:
            errores += 1
            print(f"   ERROR: {getattr(getattr(e, 'response', None), 'text', e)}")
    return 1 if errores else 0


def main() -> int:
    args = sys.argv[1:]
    if "--renombrar" in args:
        renombrar()
        return 0
    if "--validar-guiones" in args:
        return validar_guiones()
    if "--contexto" in args or "--generar" in args:
        limite = int(args[args.index("--limite") + 1]) if "--limite" in args else None
        api = args[args.index("--api") + 1] if "--api" in args else "http://127.0.0.1:8000"
        return generar(api, limite, mostrar_solo="--generar" not in args, sin_ia="--sin-ia" in args)
    estado()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
