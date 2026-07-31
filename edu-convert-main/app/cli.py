"""CLI EduConvert — пакетный прогон без UI (этап A: проверка ядра).

Пример::

    python -m app.cli --db база.xlsx --input ./Б1_О_01_РПД.docx ./ФОС_*.docx \
        --out ./результат.zip

Без ``--rpd-template`` / ``--fos-template`` берутся размеченные шаблоны из
``app/templates/`` (см. :data:`app.config.settings`).
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

import anyio

from app.config import settings
from app.core.models import FileStatus
from app.services.orchestrator import Orchestrator, RunResult

_DOC_GLOBS = ("*.doc", "*.docx")


def _collect_inputs(paths: list[str]) -> list[Path]:
    """Разворачивает пути: каталоги → все .doc/.docx внутри; файлы — как есть."""
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for pattern in _DOC_GLOBS:
                files.extend(sorted(p.glob(pattern)))
        elif p.is_file():
            files.append(p)
    # Исключаем сами шаблоны и временные файлы Word (~$...).
    return [f for f in files if not f.name.startswith("~$")]


def _progress(done: int, total: int, message: str) -> None:
    bar_total = max(total, 1)
    pct = int(done / bar_total * 100)
    sys.stdout.write(f"\r[{pct:3d}%] {message:<60}")
    sys.stdout.flush()
    if done >= total:
        sys.stdout.write("\n")


def _print_summary(result: RunResult) -> None:
    report = result.report
    print("\n=== СВОДНЫЙ ОТЧЁТ ===")
    print(
        f"Всего: {report.total} | Успешно: {report.succeeded} | "
        f"Расхождений: {report.with_discrepancies} | Ошибок: {report.failed}\n"
    )
    for r in report.results:
        mark = {
            FileStatus.SUCCESS: "[OK]",
            FileStatus.DISCREPANCY: "[~]",
            FileStatus.ERROR: "[X]",
        }[r.status]
        print(f"{mark} {r.filename}  ({r.index or '—'}, {r.doc_type.value})")
        if r.message:
            print(f"      {r.message}")
        for d in r.diffs:
            print(f"      • {d.field}: было «{d.old_value}» → стало «{d.new_value}» (База)")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="EduConvert — конвертация РПД/ФОС (CLI)")
    ap.add_argument("--db", required=True, help="Путь к база.xlsx")
    ap.add_argument("--rpd-template", default=str(settings.rpd_template))
    ap.add_argument("--fos-template", default=str(settings.fos_template))
    ap.add_argument("--input", nargs="+", required=True, help="Файлы или каталоги с РПД/ФОС")
    ap.add_argument("--out", default="результат.zip", help="Куда сохранить ZIP с результатами")
    args = ap.parse_args(argv)

    inputs = _collect_inputs(args.input)
    if not inputs:
        print("Не найдено входных .doc/.docx файлов.", file=sys.stderr)
        return 2

    orch = Orchestrator(args.db, args.rpd_template, args.fos_template)

    async def _run() -> RunResult:
        return await orch.run(inputs, progress=_progress)

    result = anyio.run(_run)
    _print_summary(result)

    out_path = Path(args.out)
    shutil.copy(result.zip_path, out_path)
    print(f"\nАрхив сохранён: {out_path.resolve()}")
    result.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
