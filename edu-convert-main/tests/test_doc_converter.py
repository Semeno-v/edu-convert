"""Конвертация .doc → .docx через LibreOffice (app/core/doc_converter.py).

Настоящий LibreOffice не запускается: он есть не на каждой машине и в CI, а
проверять надо не его работу, а реакцию на её исход. Поэтому в каждом тесте
на место ``soffice`` подставляется короткий shell-скрипт с нужным поведением.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from app.core.doc_converter import LibreOfficeConverter, ensure_docx, find_soffice
from app.core.exceptions import DocConversionError


def _fake_soffice(directory: Path, body: str) -> str:
    """Кладёт исполняемую заглушку soffice и возвращает путь к ней."""
    script = directory / "soffice"
    script.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


@pytest.fixture
def doc(tmp_path: Path) -> Path:
    source = tmp_path / "РПД.doc"
    source.write_bytes(b"\xd0\xcf\x11\xe0")  # сигнатура OLE2, содержимое не важно
    return source


def test_supports_only_doc(tmp_path: Path) -> None:
    conv = LibreOfficeConverter(binary=_fake_soffice(tmp_path, "exit 0"))

    assert conv.supports(Path("РПД.doc"))
    assert conv.supports(Path("РПД.DOC"))  # регистр расширения не важен
    assert not conv.supports(Path("РПД.docx"))


def test_converts_and_returns_result_path(tmp_path: Path, doc: Path) -> None:
    out_dir = tmp_path / "out"
    binary = _fake_soffice(tmp_path, f'touch "{out_dir}/РПД.docx"')

    result = LibreOfficeConverter(binary=binary).convert(doc, out_dir)

    assert result == out_dir / "РПД.docx"
    assert result.exists()


def test_nonzero_exit_code_is_reported(tmp_path: Path, doc: Path) -> None:
    """Ненулевой код — ошибка, даже если файл всё-таки записан.

    LibreOffice умеет сохранить частично сконвертированный документ и выйти
    с ошибкой. Раньше проверяли только наличие файла, и такой обрубок уходил
    в выдачу как успешный результат.
    """
    out_dir = tmp_path / "out"
    binary = _fake_soffice(tmp_path, f'touch "{out_dir}/РПД.docx"\necho "сбой" >&2\nexit 1')

    with pytest.raises(DocConversionError) as exc:
        LibreOfficeConverter(binary=binary).convert(doc, out_dir)

    assert "1" in str(exc.value)
    assert "сбой" in str(exc.value)


def test_missing_output_is_reported(tmp_path: Path, doc: Path) -> None:
    binary = _fake_soffice(tmp_path, 'echo "нечего конвертировать" >&2\nexit 0')

    with pytest.raises(DocConversionError, match="не создал файл"):
        LibreOfficeConverter(binary=binary).convert(doc, tmp_path / "out")


def test_timeout_is_reported(tmp_path: Path, doc: Path) -> None:
    binary = _fake_soffice(tmp_path, "sleep 5")

    with pytest.raises(DocConversionError, match="не ответил"):
        LibreOfficeConverter(binary=binary, timeout=0.5).convert(doc, tmp_path / "out")


def test_absent_libreoffice_explains_how_to_install(
    tmp_path: Path, doc: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "пусто"))  # иначе найдётся настоящий

    with pytest.raises(DocConversionError, match="libreoffice-writer"):
        LibreOfficeConverter().convert(doc, tmp_path / "out")


def test_find_soffice_uses_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_soffice(tmp_path, "exit 0")
    monkeypatch.setenv("PATH", str(tmp_path))

    assert find_soffice() == str(tmp_path / "soffice")


def test_find_soffice_returns_none_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "пусто"))

    assert find_soffice() is None


def test_ensure_docx_passes_docx_through(tmp_path: Path) -> None:
    """Готовый .docx не трогаем — конвертер даже не вызывается."""
    source = tmp_path / "РПД.docx"
    source.touch()
    conv = LibreOfficeConverter(binary=_fake_soffice(tmp_path, "exit 1"))

    assert ensure_docx(source, tmp_path / "out", conv) == source


def test_ensure_docx_converts_doc(tmp_path: Path, doc: Path) -> None:
    out_dir = tmp_path / "out"
    conv = LibreOfficeConverter(binary=_fake_soffice(tmp_path, f'touch "{out_dir}/РПД.docx"'))

    assert ensure_docx(doc, out_dir, conv) == out_dir / "РПД.docx"


def test_broken_binary_is_reported(tmp_path: Path, doc: Path) -> None:
    """Файл на месте, но запуску не подлежит — OSError, а не падение наружу."""
    binary = tmp_path / "soffice"
    binary.write_text("не скрипт", encoding="utf-8")
    binary.chmod(binary.stat().st_mode & ~stat.S_IEXEC)

    with pytest.raises(DocConversionError, match="Не удалось запустить"):
        LibreOfficeConverter(binary=str(binary)).convert(doc, tmp_path / "out")


def test_uses_isolated_profile(tmp_path: Path, doc: Path) -> None:
    """Профиль LibreOffice — свой на каждый вызов.

    Без ``-env:UserInstallation`` headless-запуск падает, когда у пользователя
    уже открыт обычный LibreOffice с тем же профилем.
    """
    out_dir = tmp_path / "out"
    args_dump = tmp_path / "args.txt"
    binary = _fake_soffice(
        tmp_path, f'echo "$@" > "{args_dump}"\ntouch "{out_dir}/РПД.docx"'
    )

    LibreOfficeConverter(binary=binary).convert(doc, out_dir)

    recorded = args_dump.read_text(encoding="utf-8")
    assert "-env:UserInstallation=file://" in recorded
    assert "--headless" in recorded


@pytest.mark.skipif(os.name == "nt", reason="заглушка soffice — sh-скрипт")
def test_profile_directory_removed_after_run(tmp_path: Path, doc: Path) -> None:
    out_dir = tmp_path / "out"
    args_dump = tmp_path / "args.txt"
    binary = _fake_soffice(
        tmp_path, f'echo "$@" > "{args_dump}"\ntouch "{out_dir}/РПД.docx"'
    )

    LibreOfficeConverter(binary=binary).convert(doc, out_dir)

    profile = next(
        part.removeprefix("-env:UserInstallation=file://")
        for part in args_dump.read_text(encoding="utf-8").split()
        if part.startswith("-env:UserInstallation=")
    )
    assert not Path(profile).exists()
