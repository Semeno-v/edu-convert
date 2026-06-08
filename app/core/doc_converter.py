"""Конвертация устаревшего ``.doc`` (OLE2) в ``.docx`` через MS Word COM.

На целевой машине установлен MS Word и доступен COM-автоматизатор, поэтому
используется ``win32com`` (ТЗ §2 разрешает win32com на Windows). Метод
:meth:`WordComConverter.convert` синхронный и блокирующий — оркестратор обязан
вызывать его в пуле потоков (``anyio.to_thread``), чтобы не блокировать
event loop (ТЗ §2, §4 Этап 2.7, §7.1).

Реализация :class:`~app.core.interfaces.SourceConverter`.
"""

from __future__ import annotations

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
        except Exception as exc:  # noqa: BLE001 — любые COM-ошибки → доменная
            raise DocConversionError(
                f"Не удалось конвертировать '{path.name}': {exc}"
            ) from exc
        finally:
            if document is not None:
                try:
                    document.Close(SaveChanges=False)
                except Exception:  # noqa: BLE001, S110
                    pass
            if word is not None:
                try:
                    word.Quit()
                except Exception:  # noqa: BLE001, S110
                    pass
            pythoncom.CoUninitialize()

        if not out_path.exists():
            raise DocConversionError(f"Word не создал файл '{out_path.name}'")
        return out_path


def ensure_docx(path: Path, out_dir: Path, converter: WordComConverter | None = None) -> Path:
    """Возвращает путь к ``.docx``: конвертирует, если на входе ``.doc``."""
    converter = converter or WordComConverter()
    if converter.supports(path):
        return converter.convert(path, out_dir)
    return path
