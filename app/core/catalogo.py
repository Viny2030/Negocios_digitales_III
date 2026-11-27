"""
core/catalogo.py — Oferta académica de la UMSA por facultad: la ÚNICA fuente
de la lista de carreras del canal.

La usan:
  - core/scheduler.py: cada facultad tiene su franja en la grilla y su
    prefijo de archivo (todo clip "jur_*" sale en la franja de Ciencias
    Jurídicas y Sociales, etc.); el bloque nocturno rota todas.
  - scripts/cargar_carreras.py: genera con /ai/clip los clips que faltan.
  - scripts/generar_sitio.py: grafo de información y tabla del manual.

Fuente: sitio oficial, leído el 2026-11-27 —
https://www.umsa.edu.ar/carreras-de-grado/ , https://www.umsa.edu.ar/posgrados
y la página de cada facultad (URL en `Facultad.url`). Nombres y modalidades
tal como figuran ahí; los nombres en inglés son traducción propia para el
sitio /en. Duraciones y planes NO se cargan acá: el guion de cada clip se
escribe a partir de la ficha oficial de la carrera (ver cargar_carreras.py).
Si la UMSA cambia su oferta, se actualiza este archivo y nada más.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Nivel = Literal["grado", "posgrado"]


@dataclass(frozen=True)
class Facultad:
    clave: str
    nombre: str
    nombre_en: str
    prefijo: str  # prefijo de nombre de archivo de sus clips (ver core/scheduler.py)
    url: str


@dataclass(frozen=True)
class Programa:
    facultad: str  # Facultad.clave
    nivel: Nivel
    nombre: str
    nombre_en: str
    modalidad: str
    slug: str
    placa: str = "media/placas/umsa_fondo.png"

    @property
    def nombre_archivo(self) -> str:
        return f"{FACULTADES[self.facultad].prefijo}{self.nivel}_{self.slug}"


_FACULTADES = [
    Facultad("jur", "Facultad de Ciencias Jurídicas y Sociales", "School of Law and Social Sciences", "jur_",
             "https://www.umsa.edu.ar/ciencias-juridicas-sociales/"),
    Facultad("eco", "Facultad de Ciencias Económicas", "School of Economics", "eco_",
             "https://www.umsa.edu.ar/facultad-de-ciencias-economicas/"),
    Facultad("hum", "Facultad de Ciencias Humanas", "School of Human Sciences", "hum_",
             "https://www.umsa.edu.ar/facultad-de-ciencias-humanas/"),
    Facultad("len", "Facultad de Lenguas Modernas", "School of Modern Languages", "len_",
             "https://www.umsa.edu.ar/facultad-de-lenguas-modernas/"),
    Facultad("art", "Facultad de Artes", "School of Arts", "art_",
             "https://www.umsa.edu.ar/facultad-de-artes/"),
]
FACULTADES: dict[str, Facultad] = {f.clave: f for f in _FACULTADES}

_P = "media/placas/"
PROGRAMAS: list[Programa] = [
    # --- Ciencias Jurídicas y Sociales ---
    Programa("jur", "grado", "Abogacía", "Law", "presencial o virtual", "abogacia", _P + "foco_grado_abogacia.jpeg"),
    Programa("jur", "grado", "Licenciatura en Trabajo Social", "Bachelor's in Social Work", "presencial", "trabajo_social"),
    Programa("jur", "grado", "Martillero Público y Corredor de Comercio", "Public Auctioneer and Commercial Broker",
             "presencial", "martillero_corredor"),
    Programa("jur", "grado", "Licenciatura en Periodismo – Ciclo de Licenciatura",
             "Bachelor's in Journalism (degree completion)", "presencial", "periodismo_ciclo"),
    Programa("jur", "posgrado", "Doctorado en Ciencias Jurídicas", "PhD in Legal Sciences", "presencial o a distancia",
             "doctorado_ciencias_juridicas", _P + "posgrado_derecho.png"),
    Programa("jur", "posgrado", "Posdoctorado en Ciencias Jurídicas", "Postdoctorate in Legal Sciences", "a distancia",
             "posdoctorado_ciencias_juridicas"),
    Programa("jur", "posgrado", "Maestría en Información Jurídica y Técnicas Legislativas",
             "Master's in Legal Information and Legislative Drafting", "a distancia", "maestria_informacion_juridica"),
    Programa("jur", "posgrado", "Maestría en Negociaciones Colectivas del Trabajo",
             "Master's in Collective Labor Bargaining", "presencial", "maestria_negociaciones_colectivas"),
    Programa("jur", "posgrado", "Especialización en Derecho Procesal Penal", "Specialization in Criminal Procedure Law",
             "presencial", "especializacion_procesal_penal"),
    # --- Ciencias Económicas ---
    Programa("eco", "grado", "Contador Público", "Public Accountant", "presencial", "contador_publico",
             _P + "foco_grado_contador_publico.png"),
    Programa("eco", "grado", "Licenciatura en Negocios Digitales", "Bachelor's in Digital Business", "virtual",
             "negocios_digitales", _P + "foco_grado_negocios_digitales.png"),
    Programa("eco", "grado", "Licenciatura en Bioeconomía y Nanoeconomía", "Bachelor's in Bioeconomics and Nanoeconomics",
             "virtual", "bioeconomia_nanoeconomia"),
    Programa("eco", "grado", "Licenciatura en Gestión Educativa – Ciclo de Licenciatura",
             "Bachelor's in Education Management (degree completion)", "virtual", "gestion_educativa_ciclo"),
    Programa("eco", "grado", "Profesorado Universitario", "University Teaching Degree", "virtual",
             "profesorado_universitario"),
    Programa("eco", "grado", "Tecnicatura Universitaria en Seguros", "University Technical Degree in Insurance",
             "a distancia", "tecnicatura_seguros"),
    Programa("eco", "posgrado", "Maestría en Consultoría en Gestión de Organizaciones",
             "Master's in Organizational Management Consulting", "presencial", "maestria_consultoria_gestion"),
    Programa("eco", "posgrado", "Maestría en Gobierno y Gestión de la Educación",
             "Master's in Education Governance and Management", "a distancia", "maestria_gobierno_educacion"),
    # --- Ciencias Humanas ---
    Programa("hum", "grado", "Licenciatura en Fonoaudiología", "Bachelor's in Speech Therapy", "presencial",
             "fonoaudiologia"),
    Programa("hum", "grado", "Licenciatura en Psicología", "Bachelor's in Psychology", "presencial", "psicologia",
             _P + "foco_grado_psicologia.png"),
    Programa("hum", "grado", "Licenciatura en Psicomotricidad", "Bachelor's in Psychomotricity", "presencial",
             "psicomotricidad"),
    Programa("hum", "grado", "Tecnicatura en Psicomotricidad", "Technical Degree in Psychomotricity", "presencial",
             "tecnicatura_psicomotricidad"),
    Programa("hum", "posgrado", "Doctorado en Fonoaudiología", "PhD in Speech Therapy", "presencial",
             "doctorado_fonoaudiologia", _P + "posgrado_fonoaudiologia.png"),
    Programa("hum", "posgrado",
             "Maestría en abordaje de consumo de Sustancias Psicoactivas desde una perspectiva sociosanitaria",
             "Master's in Psychoactive Substance Use from a Socio-Health Perspective", "presencial",
             "maestria_sustancias_psicoactivas"),
    Programa("hum", "posgrado", "Maestría en Bioética", "Master's in Bioethics", "presencial", "maestria_bioetica",
             _P + "posgrado_bioetica.png"),
    Programa("hum", "posgrado", "Especialización en Atención Temprana en Fonoaudiología",
             "Specialization in Early Intervention in Speech Therapy", "presencial", "especializacion_atencion_temprana"),
    Programa("hum", "posgrado", "Especialización en Audiología", "Specialization in Audiology", "presencial",
             "especializacion_audiologia"),
    Programa("hum", "posgrado", "Especialización en Violencia Familiar", "Specialization in Family Violence",
             "presencial", "especializacion_violencia_familiar"),
    # --- Lenguas Modernas ---
    Programa("len", "grado", "Intérprete de Conferencias en Idioma Inglés", "English Conference Interpreter",
             "presencial", "interprete_conferencias"),
    Programa("len", "grado", "Profesorado de Educación Superior en idioma Inglés", "Higher Education English Teacher",
             "presencial", "profesorado_ingles"),
    Programa("len", "grado", "Tecnicatura en Traducción Multimedia en idioma Inglés",
             "Technical Degree in English Multimedia Translation", "presencial o virtual",
             "tecnicatura_traduccion_multimedia"),
    Programa("len", "grado", "Traductor/a Público/a en Idioma Inglés", "Sworn English Translator", "presencial o virtual",
             "traductorado_publico_ingles", _P + "foco_grado_traductorado_ingles.png"),
    # --- Artes ---
    Programa("art", "grado", "Licenciatura en Artes Visuales", "Bachelor's in Visual Arts", "presencial",
             "artes_visuales", _P + "foco_grado_artes_visuales.png"),
    Programa("art", "grado", "Licenciatura en Conservación y Restauración de Bienes Culturales",
             "Bachelor's in Conservation and Restoration of Cultural Heritage", "presencial", "conservacion_restauracion"),
    Programa("art", "grado", "Licenciatura en Curaduría e Historia de las Artes",
             "Bachelor's in Curatorship and Art History", "presencial", "curaduria_historia_artes"),
    Programa("art", "grado", "Tecnicatura Universitaria en Curaduría de las Artes",
             "University Technical Degree in Art Curatorship", "virtual", "tecnicatura_curaduria"),
    Programa("art", "posgrado", "Maestría en Museología contemporánea", "Master's in Contemporary Museology",
             "a distancia", "maestria_museologia", _P + "posgrado_museologia.jpeg"),
]

# Clips generados antes de la grilla por facultad → su nombre nuevo (ver
# scripts/cargar_carreras.py --renombrar). Así no se paga de nuevo la IA.
RENOMBRES_ANTERIORES = {
    "foco_grado_abogacia": "jur_grado_abogacia",
    "foco_grado_contador_publico": "eco_grado_contador_publico",
    "foco_grado_negocios_digitales": "eco_grado_negocios_digitales",
    "foco_grado_psicologia": "hum_grado_psicologia",
    "foco_grado_traductorado_ingles": "len_grado_traductorado_publico_ingles",
    "foco_grado_artes_visuales": "art_grado_artes_visuales",
    "posgrado_derecho": "jur_posgrado_doctorado_ciencias_juridicas",
    "posgrado_fonoaudiologia": "hum_posgrado_doctorado_fonoaudiologia",
    "posgrado_bioetica": "hum_posgrado_maestria_bioetica",
    "posgrado_museologia": "art_posgrado_maestria_museologia",
}


def programas_de(clave_facultad: str) -> list[Programa]:
    return [p for p in PROGRAMAS if p.facultad == clave_facultad]
