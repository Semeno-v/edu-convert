"""Извлечение эталонных числовых данных из Базы (Excel, лист «План»).

Лист «План» — это многострочная шапка + четыре 10-колоночных блока семестров.
Чтобы не зависеть от жёстких индексов ячеек (ТЗ §3.1, §4 Этап 2.3), колонки
определяются **по ключевым словам шапки**:

* идентификация/итоги (строка-шапка): Индекс, Наименование, з.е.(Факт),
  По плану (всего ак.ч.), Конт.раб., СР, Контроль;
* формы контроля кодируются позиционно: «Экзамен»/«Зачет»/«Зачет с оц.» хранят
  *номер семестра*;
* Лек/Лаб/Пр/ПО повторяются в каждом блоке семестра — суммируются по всем блокам;
* семестр блока берётся из строки «Семестр N».

Реализация :class:`~app.core.interfaces.SubjectRepository`.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from app.core.exceptions import ExcelParseError, SubjectNotFoundError
from app.core.models import (
    ControlForm,
    ControlKind,
    SemesterHours,
    SubjectData,
)
from app.core.normalizer import as_int, normalize_index, normalize_text, to_float


def _cell_to_str(value: object) -> str:
    """Приводит ячейку к строке, аккуратно обрабатывая float-целые (108.0 → «108»)."""
    if value is None:
        return ""
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value).strip()


def _read_grid(path: Path, sheet: str) -> list[list[str]]:
    """Читает лист как сетку строк через polars + fastexcel (без авто-шапки)."""
    try:
        df = pl.read_excel(
            path,
            sheet_name=sheet,
            engine="calamine",
            has_header=False,
            read_options={"header_row": None},
        )
    except Exception as exc:  # noqa: BLE001 — оборачиваем в доменную ошибку
        raise ExcelParseError(f"Не удалось прочитать лист '{sheet}': {exc}") from exc
    return [[_cell_to_str(v) for v in row] for row in df.iter_rows()]


class ExcelSubjectRepository:
    """Репозиторий дисциплин поверх листа «План» учебного плана."""

    def __init__(self, path: str | Path, sheet: str = "План") -> None:
        self.path = Path(path)
        self.sheet = sheet
        self._subjects: dict[str, SubjectData] = {}
        self._load()

    # ------------------------------------------------------------------ #
    #  Публичный интерфейс (SubjectRepository)
    # ------------------------------------------------------------------ #
    def get_subject(self, index: str) -> SubjectData:
        key = normalize_index(index)
        subject = self._subjects.get(key)
        if subject is None:
            raise SubjectNotFoundError(index)
        return subject

    def has_subject(self, index: str) -> bool:
        return normalize_index(index) in self._subjects

    @property
    def count(self) -> int:
        return len(self._subjects)

    # ------------------------------------------------------------------ #
    #  Разбор листа
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        grid = _read_grid(self.path, self.sheet)
        header_row, header = self._find_header(grid)
        cols = self._map_base_columns(header)
        sem_starts = self._semester_starts(grid, header_row, header)
        repeated = self._repeated_columns(header)

        for r in range(header_row + 1, len(grid)):
            row = grid[r]
            if cols["index"] >= len(row):
                continue
            raw_index = row[cols["index"]]
            if not raw_index.startswith("Б"):
                continue  # строки-заголовки разделов (Блок 1, Обязательная часть…)
            subject = self._build_subject(row, cols, sem_starts, repeated)
            self._subjects[subject.index] = subject

    def _find_header(self, grid: list[list[str]]) -> tuple[int, list[str]]:
        for i, row in enumerate(grid):
            if any(normalize_text(c) == "индекс" for c in row):
                return i, row
        raise ExcelParseError("Не найдена строка-шапка с колонкой «Индекс»")

    def _map_base_columns(self, header: list[str]) -> dict[str, int]:
        """Сопоставляет базовые колонки идентификации/итогов по ключевым словам."""
        cols: dict[str, int] = {}
        first_block = self._first_block_start(header)
        for c, label in enumerate(header):
            n = normalize_text(label)
            if n == "индекс" and "index" not in cols:
                cols["index"] = c
            elif n == "наименование" and "name" not in cols:
                cols["name"] = c
            elif n == "факт" and "ze" not in cols:
                cols["ze"] = c
            elif n == "по плану" and "total" not in cols:
                cols["total"] = c
            elif n.startswith("конт. раб") and "contact" not in cols:
                cols["contact"] = c
            elif n in ("экза мен", "экзамен") and "exam" not in cols:
                cols["exam"] = c
            elif "зачет с оц" in n and "graded" not in cols:
                cols["graded"] = c
            elif n == "зачет" and "credit" not in cols:
                cols["credit"] = c
            # «СР» и «Контроль» — берём итоговые, до первого блока семестров
            elif n == "ср" and c < first_block and "srs" not in cols:
                cols["srs"] = c
            elif n in ("контроль", "конт роль") and c < first_block and "control" not in cols:
                cols["control"] = c
            elif n == "код" and "dep_code" not in cols:
                cols["dep_code"] = c
            elif n == "компетенции" and "competences" not in cols:
                cols["competences"] = c

        if "index" not in cols or "name" not in cols or "ze" not in cols or "total" not in cols:
            raise ExcelParseError(f"Не найдены обязательные колонки. Найдено: {cols}")
        return cols

    @staticmethod
    def _first_block_start(header: list[str]) -> int:
        """Индекс первой колонки «з.е.» блока семестров (после базовых колонок)."""
        ze_cols = [c for c, label in enumerate(header) if normalize_text(label) == "з.е."]
        # Первый «з.е.» — это итоговый? Нет: в «План» итоговая з.е. помечена «Факт».
        # «з.е.» встречается только как заголовок блоков семестров.
        return ze_cols[0] if ze_cols else len(header)

    def _semester_starts(
        self, grid: list[list[str]], header_row: int, header: list[str]
    ) -> dict[int, int]:
        """Сопоставляет стартовую колонку блока → номер семестра (из строки «Семестр N»)."""
        starts: dict[int, int] = {}
        block_cols = [c for c, label in enumerate(header) if normalize_text(label) == "з.е."]
        # Строка «Семестр N» обычно на 1–2 выше шапки.
        for c in block_cols:
            semester = None
            for up in range(1, 4):
                ri = header_row - up
                if ri < 0:
                    break
                # «Семестр N» может стоять в этой же или соседних левее колонках блока.
                for cc in range(c, min(c + 1, len(grid[ri])) + 1):
                    if cc < len(grid[ri]):
                        n = normalize_text(grid[ri][cc])
                        if n.startswith("семестр"):
                            digits = "".join(ch for ch in n if ch.isdigit())
                            if digits:
                                semester = int(digits)
                                break
                if semester is not None:
                    break
            if semester is not None:
                starts[c] = semester
        return starts

    @staticmethod
    def _repeated_columns(header: list[str]) -> dict[str, list[int]]:
        """Колонки, повторяющиеся в каждом блоке семестра (суммируются)."""
        labels = {
            "lectures": "лек",
            "lab": "лаб",
            "practical": "пр",
            "project": "по",
            "srs_block": "ср",
            "control_block": "контроль",
            "ze_block": "з.е.",
        }
        result: dict[str, list[int]] = {k: [] for k in labels}
        for c, label in enumerate(header):
            n = normalize_text(label)
            for key, kw in labels.items():
                if n == kw or (key == "control_block" and n == "конт роль"):
                    result[key].append(c)
        return result

    def _build_subject(
        self,
        row: list[str],
        cols: dict[str, int],
        sem_starts: dict[int, int],
        repeated: dict[str, list[int]],
    ) -> SubjectData:
        def cell(c: int | None) -> str:
            return row[c] if c is not None and c < len(row) else ""

        def sum_cols(keys: list[int]) -> int:
            return sum(as_int(cell(c)) for c in keys)

        index = normalize_index(cell(cols["index"]))
        name = cell(cols["name"])

        lectures = sum_cols(repeated["lectures"])
        lab = sum_cols(repeated["lab"])
        practical = sum_cols(repeated["practical"])
        project = sum_cols(repeated["project"])
        aud = lectures + lab + practical + project

        control_forms = self._control_forms(row, cols)
        per_semester = self._per_semester(row, sem_starts, repeated)

        competence_codes: tuple[str, ...] = ()
        if "competences" in cols:
            raw = cell(cols["competences"])
            competence_codes = tuple(
                code.strip() for code in raw.replace(",", ";").split(";") if code.strip()
            )

        return SubjectData(
            index=index,
            name=name,
            ze=to_float(cell(cols.get("ze"))) or 0.0,
            hours_total=as_int(cell(cols.get("total"))),
            hours_contact=as_int(cell(cols.get("contact"))),
            hours_aud=aud,
            hours_lectures=lectures,
            hours_practical=practical,
            hours_lab=lab,
            hours_project=project,
            hours_srs=as_int(cell(cols.get("srs"))),
            hours_control=as_int(cell(cols.get("control"))),
            control_forms=control_forms,
            per_semester=per_semester,
            department=cell(cols.get("dep_code")) or None,
            competence_codes=competence_codes,
        )

    @staticmethod
    def _control_forms(row: list[str], cols: dict[str, int]) -> tuple[ControlForm, ...]:
        forms: list[ControlForm] = []
        mapping = (
            ("exam", ControlKind.EXAM),
            ("credit", ControlKind.CREDIT),
            ("graded", ControlKind.GRADED_CREDIT),
        )
        for key, kind in mapping:
            c = cols.get(key)
            if c is not None and c < len(row):
                sem = as_int(row[c], default=0)
                if sem > 0:
                    forms.append(ControlForm(kind=kind, semester=sem))
        return tuple(forms)

    def _per_semester(
        self,
        row: list[str],
        sem_starts: dict[int, int],
        repeated: dict[str, list[int]],
    ) -> tuple[SemesterHours, ...]:
        result: list[SemesterHours] = []
        for start, semester in sorted(sem_starts.items(), key=lambda kv: kv[1]):
            end = start + 10  # 10-колоночный блок

            def in_block(c: int, _s: int = start, _e: int = end) -> bool:
                return _s <= c < _e

            def block_val(key: str, _row: list[str] = row) -> int:
                for c in repeated[key]:
                    if in_block(c) and c < len(_row):
                        return as_int(_row[c])
                return 0

            ze_val = 0.0
            for c in repeated["ze_block"]:
                if in_block(c) and c < len(row):
                    ze_val = to_float(row[c]) or 0.0
                    break

            hours = SemesterHours(
                semester=semester,
                ze=ze_val,
                lectures=block_val("lectures"),
                lab=block_val("lab"),
                practical=block_val("practical"),
                project=block_val("project"),
                srs=block_val("srs_block"),
                control=block_val("control_block"),
            )
            if any((hours.lectures, hours.lab, hours.practical, hours.project, hours.ze)):
                result.append(hours)
        return tuple(result)


def load_repository(path: str | Path, sheet: str = "План") -> ExcelSubjectRepository:
    """Фабрика репозитория дисциплин."""
    return ExcelSubjectRepository(path, sheet)
