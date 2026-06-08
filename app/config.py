"""Глобальные настройки EduConvert.

Все настраиваемые параметры (пути, имена тегов шаблона, правила извлечения
блоков) собраны здесь, чтобы поведение можно было менять без правки логики.
Значения можно переопределить переменными окружения с префиксом ``EDUCONVERT_``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"


class Settings(BaseSettings):
    """Конфигурация приложения."""

    model_config = SettingsConfigDict(
        env_prefix="EDUCONVERT_",
        env_file=".env",
        extra="ignore",
    )

    # --- Пути --------------------------------------------------------------- #
    temp_root: Path = Field(default_factory=lambda: Path(tempfile.gettempdir()) / "educonvert")
    rpd_template: Path = TEMPLATES_DIR / "rpd_2026_tagged.docx"
    fos_template: Path = TEMPLATES_DIR / "fos_2026_tagged.docx"

    # --- Excel -------------------------------------------------------------- #
    plan_sheet: str = "План"
    plansvod_sheet: str = "ПланСвод"

    # --- Имя листа конвертации .doc ---------------------------------------- #
    doc_format_docx: int = 16  # wdFormatDocumentDefault для Word.SaveAs2

    # --- Обязательные теги шаблонов (для валидации docxtpl) ---------------- #
    required_rpd_tags: tuple[str, ...] = (
        "index",
        "name",
        "ze",
        "hours_total",
        "hours_lectures",
        "hours_practical",
    )
    required_fos_tags: tuple[str, ...] = (
        "index",
        "name",
    )


settings = Settings()
