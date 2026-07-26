"""Точка входа: FastAPI с примонтированным Flet-приложением (ТЗ §6).

Flet-приложение обслуживается по корневому маршруту ``/`` через
``flet.fastapi.app`` (асинхронный ASGI), к нему добавлен служебный эндпоинт
``/health``. Запуск::

    uvicorn app.main:app --reload          # веб-режим (FastAPI + Flet)
    python -m app.ui.main_view             # настольный режим

Конвертация выполняется в асинхронном оркестраторе с изоляцией блокирующих
вызовов в пуле потоков, поэтому event loop FastAPI/Flet не блокируется.
"""

from __future__ import annotations

import flet.fastapi as flet_fastapi

from app import __version__
from app.config import settings
from app.ui.main_view import main as flet_main

# FastAPI-приложение со встроенным Flet UI по маршруту «/».
app = flet_fastapi.app(flet_main)


@app.get("/health")
async def health() -> dict[str, object]:
    """Проверка работоспособности и наличия размеченных шаблонов."""
    return {
        "status": "ok",
        "version": __version__,
        "rpd_template_exists": settings.rpd_template.exists(),
        "fos_template_exists": settings.fos_template.exists(),
    }


# Flet регистрирует catch-all маршрут на «/», поэтому поднимаем служебные
# эндпоинты в начало списка маршрутов, чтобы они матчились раньше.
def _prioritize(*paths: str) -> None:
    priority = [r for r in app.router.routes if getattr(r, "path", None) in paths]
    for route in priority:
        app.router.routes.remove(route)
    app.router.routes[:0] = priority


_prioritize("/health")
