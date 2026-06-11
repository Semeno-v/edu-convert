"""Утилиты нормализации текста и разбора учебных значений.

Модуль чистый (только stdlib), поэтому легко покрывается тестами ≥95% (ТЗ §7.5).
Главные задачи:

* нечувствительность к регистру и букве «ё» при поиске ключевых слов
  (``зачёт`` == ``зачет``);
* приведение индекса дисциплины к каноническому виду
  (``Б1_О_01`` / ``б1.о.01`` → ``Б1.О.01``);
* извлечение индекса из имени файла;
* разбор значений вида ``«108 (3)»`` → (108 часов, 3 з.е.).
"""

from __future__ import annotations

import re

# Токены-маркеры типа документа, отбрасываемые при разборе имени файла.
_DOC_MARKERS = {"ФОС", "РПД", "ФО", "РП", "FOS", "RPD"}

# Разделители внутри имён файлов и индексов.
_SEP_RE = re.compile(r"[\s_.\-—–]+")
# Голова индекса: блоки «Б1…» и факультативы «ФТД» (ФТД.01 …).
_INDEX_HEAD_RE = re.compile(r"^(?:Б\d+|ФТД)$", re.IGNORECASE)
_LETTER_CODE_RE = re.compile(r"^[А-ЯЁ]{1,2}$")
_NUMBER_RE = re.compile(r"^\d+$")

# «108 (3)», «108(3)», «1 (1)» → (целое снаружи, целое в скобках).
_HOURS_ZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*\(\s*(\d+(?:[.,]\d+)?)\s*\)")


def fold_yo(text: str) -> str:
    """Заменяет «ё»/«Ё» на «е»/«Е»."""
    return text.replace("ё", "е").replace("Ё", "Е")


def normalize_text(text: str) -> str:
    """Нормализует текст для регистро- и ё-независимого сравнения.

    Приводит к нижнему регистру, схлопывает пробелы, убирает «ё».
    """
    if text is None:
        return ""
    folded = fold_yo(str(text)).lower()
    return re.sub(r"\s+", " ", folded).strip()


def contains_keyword(haystack: str, keyword: str) -> bool:
    """True, если ``keyword`` встречается в ``haystack`` (без учёта регистра/ё)."""
    return normalize_text(keyword) in normalize_text(haystack)


def contains_any(haystack: str, keywords: list[str] | tuple[str, ...]) -> bool:
    """True, если встречается хотя бы одно из ключевых слов."""
    norm = normalize_text(haystack)
    return any(normalize_text(k) in norm for k in keywords)


def normalize_index(raw: str) -> str:
    """Приводит индекс дисциплины к каноническому виду ``Б1.О.01``.

    Любые разделители (``_``, пробел, дефис) → точка; регистр → верхний;
    лишние точки и пробелы убираются.
    """
    if not raw:
        return ""
    parts = [p for p in _SEP_RE.split(str(raw).strip()) if p]
    return ".".join(p.upper() for p in parts)


def index_from_filename(filename: str) -> str | None:
    """Извлекает индекс дисциплины из имени файла.

    Понимает форматы ``Б1_О_01_РПД_Название.docx`` и
    ``ФОС_Б1_В_ДВ_03_01_Название.docx``. Индекс — максимальная стартовая
    последовательность токенов «``Б<digits>`` + короткие буквенные коды
    (О/В/ДВ) + числа», после отбрасывания префикса-маркера типа документа.

    Возвращает канонический индекс или ``None``.
    """
    if not filename:
        return None
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", filename.strip())
    tokens = [t for t in _SEP_RE.split(stem) if t]

    i = 0
    # Пропускаем ведущие маркеры «ФОС»/«РПД».
    while i < len(tokens) and tokens[i].upper() in _DOC_MARKERS:
        i += 1
    if i >= len(tokens) or not _INDEX_HEAD_RE.match(tokens[i]):
        return None

    index_tokens = [tokens[i]]
    i += 1
    while i < len(tokens):
        tok = tokens[i]
        if _NUMBER_RE.match(tok) or _LETTER_CODE_RE.match(tok.upper()):
            index_tokens.append(tok)
            i += 1
        else:
            break
    return normalize_index(".".join(index_tokens))


def index_from_text(text: str) -> str | None:
    """Ищет индекс дисциплины в произвольном тексте (например, в строке титула)."""
    if not text:
        return None
    # Буквенные коды (О/В/ДВ) — короткие и отделены разделителем; lookahead
    # не даёт «съесть» начало следующего слова (…01 МЕТОДОЛОГИЯ → не «01.МЕ»).
    match = re.search(
        r"(?:Б\d+|ФТД)(?:[\s_.\-]+(?:\d+|[А-ЯЁ]{1,2}(?![А-Яа-яЁё])))+",
        text,
        re.IGNORECASE,
    )
    return normalize_index(match.group(0)) if match else None


def parse_hours_ze(raw: str) -> tuple[float | None, float | None]:
    """Разбирает значение вида ``«108 (3)»`` → (108.0, 3.0).

    Первое число — внешнее (часы/семестр), второе — в скобках (з.е./курс).
    Если скобок нет — второй элемент ``None``. Десятичная запятая поддерживается.
    """
    if raw is None:
        return None, None
    match = _HOURS_ZE_RE.search(str(raw))
    if match:
        return _to_number(match.group(1)), _to_number(match.group(2))
    single = to_float(raw)
    return single, None


def _to_number(value: str) -> float:
    return float(value.replace(",", "."))


def to_float(value: object) -> float | None:
    """Безопасно приводит ячейку к float (``«12.0»``, ``«12,0»`` → 12.0)."""
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else None


def to_int(value: object) -> int | None:
    """Безопасно приводит ячейку к int (``«12»``, ``«12.0»``, ``12.0`` → 12)."""
    number = to_float(value)
    return int(round(number)) if number is not None else None


def as_int(value: object, default: int = 0) -> int:
    """Как :func:`to_int`, но возвращает ``default`` вместо ``None``."""
    result = to_int(value)
    return result if result is not None else default
