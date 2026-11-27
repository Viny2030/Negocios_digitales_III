"""Fallback entre proveedores de LLM, traducción para subtítulos, voz oración
por oración y sin placeholders en producción."""

import json
import wave
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import ai_service
from app.services.ai_service import (
    ServicioIAError,
    generar_guion,
    generar_voz,
    sintetizar_oraciones,
    traducir_oraciones,
)

client = TestClient(app)


def _falla(*a, **k):
    raise RuntimeError("credit_balance_exhausted")


def test_si_anthropic_falla_usa_openai(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "a")
    monkeypatch.setattr(settings, "openai_api_key", "o")
    monkeypatch.setattr(ai_service, "_completar_anthropic", _falla)
    monkeypatch.setattr(ai_service, "_completar_openai", lambda s, u, m: "Guion de OpenAI")
    assert generar_guion("becas") == "Guion de OpenAI"


def test_si_fallan_todos_el_endpoint_responde_503(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "a")
    monkeypatch.setattr(ai_service, "_completar_anthropic", _falla)
    with pytest.raises(ServicioIAError, match="credit_balance_exhausted"):
        generar_guion("becas")
    r = client.post("/api/v1/ai/guion", json={"tema": "becas"})
    assert r.status_code == 503
    assert "Anthropic" in r.json()["detail"]


def test_en_desarrollo_sin_keys_devuelve_simulado():
    assert generar_guion("becas").startswith("[SIMULADO]")


def test_en_produccion_no_hay_guion_simulado_ni_voz_muda(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(ServicioIAError):
        generar_guion("becas")
    with pytest.raises(ServicioIAError):
        traducir_oraciones(["Hola."])
    with pytest.raises(ServicioIAError, match="Piper"):
        generar_voz("hola", "prueba_voz")


# --- Traducción ---------------------------------------------------------------


def test_traduccion_una_por_oracion_y_acepta_bloque_de_codigo(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "a")
    recibido = {}

    def anthropic(sistema, usuario, max_tokens):
        recibido["usuario"] = usuario
        return '```json\n["Study Law at UMSA.", "It takes five years."]\n```'

    monkeypatch.setattr(ai_service, "_completar_anthropic", anthropic)
    oraciones = ["Estudiá Abogacía en la UMSA.", "Dura cinco años."]
    assert traducir_oraciones(oraciones) == ["Study Law at UMSA.", "It takes five years."]
    assert json.loads(recibido["usuario"]) == oraciones  # tildes intactas, sin escapes


def test_traduccion_con_otra_cantidad_de_oraciones_prueba_el_siguiente(monkeypatch):
    """Sin correspondencia 1 a 1 los subtítulos quedarían desincronizados."""
    monkeypatch.setattr(settings, "anthropic_api_key", "a")
    monkeypatch.setattr(settings, "openai_api_key", "o")
    monkeypatch.setattr(ai_service, "_completar_anthropic", lambda s, u, m: '["Una sola, fusionada."]')
    monkeypatch.setattr(ai_service, "_completar_openai", lambda s, u, m: '["One.", "Two."]')
    assert traducir_oraciones(["Uno.", "Dos."]) == ["One.", "Two."]

    monkeypatch.setattr(ai_service, "_completar_openai", lambda s, u, m: "no es json")
    with pytest.raises(ServicioIAError, match="se esperaban 2"):
        traducir_oraciones(["Uno.", "Dos."])


def test_traduccion_simulada_en_desarrollo():
    assert traducir_oraciones(["Hola."]) == ["[SIMULATED EN] Hola."]


# --- Voz oración por oración ----------------------------------------------------


class _VozFalsa:
    """Imita PiperVoice: 0,1 s de audio por cada carácter."""

    def synthesize(self, texto):
        yield SimpleNamespace(
            sample_rate=1000, sample_width=2, sample_channels=1, audio_int16_bytes=b"\x00\x00" * 100 * len(texto)
        )


def test_voz_devuelve_los_tiempos_exactos_de_cada_oracion(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "tts_models_dir", tmp_path)
    (tmp_path / "voz_test.onnx").write_bytes(b"")
    monkeypatch.setattr(ai_service, "_cargar_voz", lambda modelo: _VozFalsa())

    voz = sintetizar_oraciones(["Hola.", "Chau chau."], "clip_tiempos", voice_id="voz_test")
    pausa = ai_service.PAUSA_ENTRE_ORACIONES_SEG
    assert voz.oraciones == ["Hola.", "Chau chau."]
    assert voz.tiempos[0] == pytest.approx((0.0, 0.5))
    assert voz.tiempos[1] == pytest.approx((0.5 + pausa, 0.5 + pausa + 1.0))
    with wave.open(str(voz.ruta)) as wav:
        assert wav.getnframes() / wav.getframerate() == pytest.approx(voz.tiempos[-1][1])


def test_voz_placeholder_en_desarrollo_es_silencio_con_tiempos(media_tmp):
    voz = sintetizar_oraciones(["Una oración corta.", "Otra."], "placeholder_tiempos")
    assert voz.ruta.exists()
    assert len(voz.tiempos) == 2 and voz.tiempos[1][0] > voz.tiempos[0][1]


def test_voz_sin_texto_falla_claro():
    with pytest.raises(ServicioIAError, match="No hay texto"):
        sintetizar_oraciones(["  ", ""], "vacio")
