"""Конвертация устаревшего ``.doc`` (OLE2) в ``.docx``.

Две реализации :class:`~app.core.interfaces.SourceConverter`:

* :class:`WordComConverter` — MS Word через ``win32com`` (Windows, ТЗ §2);
* :class:`LibreOfficeConverter` — headless LibreOffice (Linux/macOS, там же,
  где Word недоступен).

Подходящую для текущей ОС выбирает :func:`make_converter`. Оба метода
``convert`` синхронные и блокирующие — оркестратор обязан вызывать их в пуле
потоков (``anyio.to_thread``), чтобы не блокировать event loop
(ТЗ §2, §4 Этап 2.7, §7.1).
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from app.config import settings
from app.core.exceptions import DocConversionError


class WordComConverter:
    """Конвертер ``.doc`` → ``.docx`` на базе COM-объекта Word.Application."""

    def __init__(self, doc_format: int | None = None) -> None:
        self.doc_format = doc_format if doc_format is not None else settings.doc_format_docx

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".doc"

    def convert(self, path: Path, out_dir: Path) -> Path:
        """Открывает ``.doc`` в Word и сохраняет как ``.docx`` в ``out_dir``.

        Инициализирует COM в текущем потоке (предполагается вызов из worker-потока).
        """
        try:
            import pythoncom  # noqa: PLC0415 — импорт внутри: только Windows + worker-поток
            import win32com.client  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover — окружение без pywin32
            raise DocConversionError(
                "pywin32 не установлен — конвертация .doc недоступна"
            ) from exc

        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / (path.stem + ".docx")
        src = str(path.resolve())
        dst = str(out_path.resolve())

        pythoncom.CoInitialize()
        word = None
        document = None
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            document = word.Documents.Open(src, ReadOnly=True, AddToRecentFiles=False)
            document.SaveAs2(dst, FileFormat=self.doc_format)
        except Exception as exc:  # любые COM-ошибки заворачиваем в доменную
            raise DocConversionError(
                f"Не удалось конвертировать '{path.name}': {exc}"
            ) from exc
        finally:
            # Освобождение COM-объектов: сбой здесь не должен подменять собой
            # исходную ошибку конвертации, которая уже летит наверх.
            if document is not None:
                with contextlib.suppress(Exception):
                    document.Close(SaveChanges=False)
            if word is not None:
                with contextlib.suppress(Exception):
                    word.Quit()
            pythoncom.CoUninitialize()

        if not out_path.exists():
            raise DocConversionError(f"Word не создал файл '{out_path.name}'")
        return out_path


class LibreOfficeConverter:
    """Конвертер ``.doc`` → ``.docx`` через headless LibreOffice.

    Используется там, где нет MS Word (Linux, macOS). LibreOffice запускается
    с отдельным профилем (``-env:UserInstallation``), иначе вызов падает,
    когда у пользователя уже открыт обычный LibreOffice.
    """

    #: имена исполняемого файла в порядке предпочтения
    BINARIES = ("soffice", "libreoffice")

    def __init__(self, binary: str | None = None, timeout: float = 180.0) -> None:
        self.binary = binary or find_soffice()
        self.timeout = timeout

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".doc"

    def convert(self, path: Path, out_dir: Path) -> Path:
        if not self.binary:
            raise DocConversionError(
                "LibreOffice не найден — конвертация .doc недоступна. "
                "Установите его: sudo apt install libreoffice-writer"
            )
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / (path.stem + ".docx")

        with tempfile.TemporaryDirectory(prefix="educonvert_lo_") as profile:
            command = [
                self.binary,
                f"-env:UserInstallation=file://{profile}",
                "--headless",
                "--norestore",
                "--convert-to",
                "docx:MS Word 2007 XML",
                "--outdir",
                str(out_dir.resolve()),
                str(path.resolve()),
            ]
            try:
                completed = subprocess.run(  # noqa: S603 — команда собрана из констант
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise DocConversionError(
                    f"LibreOffice не ответил за {self.timeout:.0f} с при конвертации "
                    f"'{path.name}'"
                ) from exc
            except OSError as exc:
                raise DocConversionError(
                    f"Не удалось запустить LibreOffice ('{self.binary}'): {exc}"
                ) from exc

        detail = (completed.stderr or completed.stdout or "").strip()
        # Ненулевой код возврата — самый прямой признак сбоя, и раньше он терялся:
        # смотрели только на наличие файла. LibreOffice умеет записать частично
        # сконвертированный документ и выйти с ошибкой — такой файл уходил
        # в выдачу как успешный результат.
        if completed.returncode != 0:
            raise DocConversionError(
                f"LibreOffice завершился с кодом {completed.returncode} при конвертации "
                f"'{path.name}'" + (f": {detail}" if detail else "")
            )
        if not out_path.exists():
            raise DocConversionError(
                f"LibreOffice не создал файл '{out_path.name}'"
                + (f": {detail}" if detail else "")
            )
        return out_path


def find_soffice() -> str | None:
    """Путь к исполняемому файлу LibreOffice или ``None``, если его нет."""
    for name in LibreOfficeConverter.BINARIES:
        if found := shutil.which(name):
            return found
    return None


def make_converter() -> WordComConverter | LibreOfficeConverter:
    """Конвертер ``.doc``, подходящий для текущей ОС."""
    if sys.platform == "win32":
        return WordComConverter()
    return LibreOfficeConverter()


def doc_support_hint() -> str | None:
    """Причина, по которой ``.doc`` не конвертируется, или ``None``, если всё готово.

    UI показывает подсказку до запуска, чтобы пользователь не узнавал
    о неподдерживаемом формате из отчёта об ошибках.
    """
    if sys.platform == "win32":
        try:
            import win32com.client  # noqa: F401, PLC0415
        except ImportError:
            return (
                "Файлы .doc не будут сконвертированы: не установлен pywin32 "
                "(pip install pywin32)"
            )
        return None
    if find_soffice() is None:
        return (
            "Файлы .doc не будут сконвертированы: не найден LibreOffice "
            "(sudo apt install libreoffice-writer)"
        )
    return None


def ensure_docx(
    path: Path,
    out_dir: Path,
    converter: WordComConverter | LibreOfficeConverter | None = None,
) -> Path:
    """Возвращает путь к ``.docx``: конвертирует, если на входе ``.doc``."""
    converter = converter or make_converter()
    if converter.supports(path):
        return converter.convert(path, out_dir)
    return path
