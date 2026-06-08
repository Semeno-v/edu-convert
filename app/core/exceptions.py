"""Кастомные исключения предметной области EduConvert.

Все ошибки наследуются от :class:`EduConvertError`, чтобы оркестратор мог
перехватывать «свои» ошибки отдельно от непредвиденных и изолировать сбой
обработки одного файла от остальных (ТЗ §7.1).
"""

from __future__ import annotations


class EduConvertError(Exception):
    """Базовое исключение комплекса."""


class SubjectNotFoundError(EduConvertError):
    """Индекс дисциплины не найден в эталонной Базе (Excel).

    Обработка такого файла прекращается, в отчёт пишется строка со статусом
    «Ошибка» (ТЗ §4 Этап 2.2, §8).
    """

    def __init__(self, index: str) -> None:
        self.index = index
        super().__init__(f"Дисциплина с индексом '{index}' не найдена в Базе данных")


class IndexExtractionError(EduConvertError):
    """Не удалось определить индекс дисциплины ни из имени файла, ни из документа."""


class TemplateValidationError(EduConvertError):
    """В целевом шаблоне отсутствуют обязательные теги docxtpl."""

    def __init__(self, missing_tags: list[str], template: str) -> None:
        self.missing_tags = missing_tags
        self.template = template
        joined = ", ".join(missing_tags)
        super().__init__(
            f"В шаблоне '{template}' отсутствуют обязательные теги: {joined}"
        )


class DocConversionError(EduConvertError):
    """Ошибка конвертации устаревшего .doc в .docx."""


class DocumentParseError(EduConvertError):
    """Не удалось прочитать или разобрать исходный документ Word."""


class ExcelParseError(EduConvertError):
    """Не удалось разобрать структуру эталонной Базы (Excel)."""
