"""Абстрактные интерфейсы слоёв EduConvert (ТЗ §2, §4.5, §7.2).

Используются :class:`typing.Protocol` (структурная типизация): конкретные
реализации не обязаны наследоваться, достаточно совпадения сигнатур. Это
разграничивает контракт и реализацию и позволяет в будущем заменить любой слой
(например, переписать экстрактор на Go/Rust), не трогая оркестратор.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from app.core.models import (
    ContentBlocks,
    DocType,
    OldNumbers,
    SubjectData,
)


@runtime_checkable
class SourceConverter(Protocol):
    """Препроцессор устаревших форматов (``.doc`` → ``.docx``)."""

    def supports(self, path: Path) -> bool:
        """Нужна ли конвертация для данного файла."""
        ...

    def convert(self, path: Path, out_dir: Path) -> Path:
        """Конвертирует файл и возвращает путь к ``.docx``."""
        ...


@runtime_checkable
class SubjectRepository(Protocol):
    """Доступ к эталонным числовым данным дисциплины (источник истины)."""

    def get_subject(self, index: str) -> SubjectData:
        """Возвращает данные дисциплины. Бросает ``SubjectNotFoundError``."""
        ...

    def has_subject(self, index: str) -> bool:
        ...


@runtime_checkable
class NumberExtractor(Protocol):
    """Извлечение индекса и старых чисел из исходного документа (для diff)."""

    def extract_index(self, doc_path: Path) -> str | None:
        ...

    def extract_old_numbers(self, doc_path: Path) -> OldNumbers:
        ...


@runtime_checkable
class ContentExtractor(Protocol):
    """Извлечение текстовых смысловых блоков конечным автоматом."""

    def extract(self, doc_path: Path, doc_type: DocType) -> ContentBlocks:
        ...


@runtime_checkable
class DocumentGenerator(Protocol):
    """Генерация целевого документа из шаблона docxtpl."""

    def validate_template(self, template_path: Path, doc_type: DocType) -> None:
        """Проверяет наличие обязательных тегов. Бросает ``TemplateValidationError``."""
        ...

    def generate(
        self,
        template_path: Path,
        out_path: Path,
        subject: SubjectData,
        content: ContentBlocks,
        doc_type: DocType,
    ) -> Path:
        """Рендерит шаблон (числа из ``subject``, текст из ``content``)."""
        ...
