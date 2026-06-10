"""Pydantic-схемы EduConvert.

Это единственный разрешённый способ передачи данных между слоями
(парсер → оркестратор → генератор), см. ТЗ §7.2. Модели делятся на три группы:

* **Числовые данные** (источник истины — Excel): :class:`SubjectData`,
  :class:`SemesterHours`, :class:`ControlForm`.
* **Текстовый контент** (источник — старый Word): сериализуемое промежуточное
  представление (IR) :class:`RichRun` → :class:`RichParagraph` →
  :class:`RichTable` → :class:`ContentElement` → :class:`ContentBlock` →
  :class:`ContentBlocks`. IR не зависит от python-docx, поэтому слои можно
  переписать на Go/Rust без изменения контракта.
* **Отчётность**: :class:`OldNumbers`, :class:`DiffRecord`, :class:`FileResult`,
  :class:`RunReport`.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
#  Числовые данные (источник истины — Excel «План»)
# --------------------------------------------------------------------------- #


class ControlKind(str, Enum):
    """Форма промежуточной аттестации."""

    EXAM = "Экзамен"
    CREDIT = "Зачет"
    GRADED_CREDIT = "Зачет с оценкой"


class ControlForm(BaseModel):
    """Форма промежуточной аттестации в конкретном семестре."""

    kind: ControlKind
    semester: int


class SemesterHours(BaseModel):
    """Часы дисциплины в одном семестре (блок учебного плана)."""

    semester: int
    ze: float = 0
    lectures: int = 0
    lab: int = 0
    practical: int = 0
    project: int = 0
    srs: int = 0
    control: int = 0


class CompetencyIndicator(BaseModel):
    """Индикатор достижения компетенции (код + текст из Базы)."""

    code: str
    text: str = ""


class CompetencyGroup(BaseModel):
    """Компетенция с её индикаторами (код + текст из листа «Компетенции» Базы)."""

    code: str
    text: str = ""
    indicators: tuple[CompetencyIndicator, ...] = ()


class SubjectData(BaseModel):
    """Эталонные данные дисциплины из Базы. **Все числа берутся отсюда.**"""

    model_config = ConfigDict(frozen=True)

    index: str
    name: str

    ze: float
    hours_total: int
    hours_contact: int = 0
    hours_aud: int = 0
    hours_lectures: int = 0
    hours_practical: int = 0
    hours_lab: int = 0
    hours_project: int = 0
    hours_srs: int = 0
    hours_control: int = 0

    control_forms: tuple[ControlForm, ...] = ()
    per_semester: tuple[SemesterHours, ...] = ()
    department: str | None = None
    department_name: str | None = None
    competence_codes: tuple[str, ...] = ()
    competencies: tuple[CompetencyGroup, ...] = ()

    @property
    def competence_parents(self) -> tuple[str, ...]:
        """Родительские коды компетенций (ПК-1, ПК-2…) — для §8."""
        seen: list[str] = []
        for code in self.competence_codes:
            parent = code.split("-И-")[0]
            if parent not in seen:
                seen.append(parent)
        return tuple(seen)

    @property
    def semesters(self) -> tuple[int, ...]:
        """Список семестров изучения (по формам контроля)."""
        return tuple(sorted({cf.semester for cf in self.control_forms}))

    @property
    def control_summary(self) -> str:
        """Человекочитаемая сводка форм контроля, напр. «Экзамен (4)»."""
        return ", ".join(f"{cf.kind.value} ({cf.semester})" for cf in self.control_forms)


# --------------------------------------------------------------------------- #
#  Текстовый контент (источник — старый Word). Сериализуемый IR.
# --------------------------------------------------------------------------- #


class RichRun(BaseModel):
    """Фрагмент текста с инлайн-форматированием (один «run» в терминах OOXML)."""

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False


class RichParagraph(BaseModel):
    """Абзац: последовательность форматированных фрагментов + стиль/уровень списка."""

    runs: list[RichRun] = Field(default_factory=list)
    style: str | None = None
    list_level: int | None = None

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)


class RichTableCell(BaseModel):
    """Ячейка: для объединений хранится размах (colspan/rowspan) у ячейки-истока,
    а накрытые позиции помечаются ``merged`` (текст не дублируется)."""

    paragraphs: list[RichParagraph] = Field(default_factory=list)
    colspan: int = 1
    rowspan: int = 1
    merged: bool = False


class RichTableRow(BaseModel):
    cells: list[RichTableCell] = Field(default_factory=list)


class RichTable(BaseModel):
    rows: list[RichTableRow] = Field(default_factory=list)


class ElementKind(str, Enum):
    PARAGRAPH = "paragraph"
    TABLE = "table"


class ContentElement(BaseModel):
    """Элемент потока документа — абзац или таблица (одно из двух заполнено)."""

    kind: ElementKind
    paragraph: RichParagraph | None = None
    table: RichTable | None = None


class ContentBlock(BaseModel):
    """Именованный смысловой блок, извлечённый конечным автоматом."""

    key: str
    title: str
    elements: list[ContentElement] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return len(self.elements) == 0


class ContentBlocks(BaseModel):
    """Все извлечённые из старого документа блоки (ключ → блок)."""

    index: str | None = None
    title_line: str | None = None
    direction: str | None = None
    profile: str | None = None
    form_study: str | None = None
    blocks: dict[str, ContentBlock] = Field(default_factory=dict)

    def get(self, key: str) -> ContentBlock | None:
        return self.blocks.get(key)


# --------------------------------------------------------------------------- #
#  Отчётность / расхождения
# --------------------------------------------------------------------------- #


class OldNumbers(BaseModel):
    """Числа, извлечённые из таблицы старого документа (только для diff)."""

    ze: float | None = None
    hours_total: int | None = None
    hours_lectures: int | None = None
    hours_practical: int | None = None
    hours_lab: int | None = None
    hours_project: int | None = None
    hours_srs: int | None = None
    semester: int | None = None
    control_raw: str | None = None


class DiffRecord(BaseModel):
    """Одно расхождение: поле, старое значение (Word) и новое (Excel)."""

    field: str
    old_value: str
    new_value: str


class FileStatus(str, Enum):
    SUCCESS = "Успешно"
    DISCREPANCY = "Расхождение"
    ERROR = "Ошибка"


class DocType(str, Enum):
    RPD = "РПД"
    FOS = "ФОС"
    UNKNOWN = "Неизвестно"


class FileResult(BaseModel):
    """Результат обработки одного исходного файла (строка отчёта)."""

    filename: str
    index: str | None = None
    doc_type: DocType = DocType.UNKNOWN
    status: FileStatus = FileStatus.SUCCESS
    message: str = ""
    diffs: list[DiffRecord] = Field(default_factory=list)
    output_name: str | None = None


class RunReport(BaseModel):
    """Сводный отчёт обо всём прогоне."""

    results: list[FileResult] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.results if r.status == FileStatus.SUCCESS)

    @property
    def with_discrepancies(self) -> int:
        return sum(1 for r in self.results if r.status == FileStatus.DISCREPANCY)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == FileStatus.ERROR)
