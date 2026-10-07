"""Fallback entre proveedores de guion y sin placeholders en producción."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import ai_service
from app.services.ai_service import ServicioIAError, generar_guion, generar_voz

client = TestClient(app)


def _falla(*a, **k):
    raise RuntimeError("credit_balance_exhausted")


def test_si_anthropic_falla_usa_openai(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "a")
    monkeypatch.setattr(settings, "openai_api_key", "o")
    monkeypatch.setattr(ai_service, "_generar_guion_anthropic", _falla)
    monkeypatch.setattr(ai_service, "_generar_guion_openai", lambda t, c: "Guion de OpenAI")
    assert generar_guion("becas") == "Guion de OpenAI"


def test_si_fallan_todos_el_endpoint_responde_503(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "a")
    monkeypatch.setattr(ai_service, "_generar_guion_anthropic", _falla)
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
    with pytest.raises(ServicioIAError, match="Piper"):
        generar_voz("hola", "prueba_voz")
