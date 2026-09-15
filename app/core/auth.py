"""
core/auth.py — Protección simple por token compartido (X-Admin-Token) para
los endpoints que controlan el stream en vivo (arrancar/parar, tocar la
playlist) y los que consumen créditos pagos de IA (Anthropic/OpenAI) — sin
esto, la URL pública de Railway queda abierta para que cualquiera corte la
transmisión o gaste la cuota de IA llamando a /ai/clip en loop.

Mismo patrón que app/api/deps.py::verify_admin_token del otro proyecto
(Negocios_digitales_II): si `settings.admin_token` no está seteado
(default, uso local), no exige nada — no rompe el flujo de desarrollo ni
las pruebas por Swagger/PowerShell mientras no se configure. En Railway,
configurar ADMIN_TOKEN es en la práctica OBLIGATORIO (ver README).
"""
from __future__ import annotations

from fastapi import Header, HTTPException

from app.config import settings


async def verificar_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    if settings.admin_token and x_admin_token != settings.admin_token:
        raise HTTPException(
            status_code=401,
            detail="Token de administrador inválido o faltante — mandá el header 'X-Admin-Token'.",
        )
