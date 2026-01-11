import platform
import shutil
from pathlib import Path

import pytest

from evt_parser.exceptions import (
    FileValidationError,
    PlatformNotSupportedError,
    WevtutilNotFoundError,
)
from evt_parser.utils import (
    check_platform,
    check_wevtutil_available,
    find_evt_files,
    generate_output_path,
    validate_legacy_evt_signature,
    validate_evt_file,
)


def test_check_platform_raises_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    with pytest.raises(PlatformNotSupportedError):
        check_platform()


def test_check_platform_allows_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    check_platform()


def test_check_wevtutil_available_raises_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(WevtutilNotFoundError):
        check_wevtutil_available()


def test_check_wevtutil_available_allows_when_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        shutil, "which", lambda _: "C:\\Windows\\System32\\wevtutil.exe"
    )
    check_wevtutil_available()


def test_validate_evt_file_rejects_missing_input(tmp_path: Path) -> None:
    with pytest.raises(FileValidationError):
        validate_evt_file(tmp_path / "missing.evt")


def test_validate_evt_file_rejects_wrong_extension(tmp_path: Path) -> None:
    p = tmp_path / "not_evt.txt"
    p.write_text("x", encoding="utf-8")
    with pytest.raises(FileValidationError):
        validate_evt_file(p)


def test_validate_evt_file_rejects_missing_output_dir(tmp_path: Path) -> None:
    input_evt = tmp_path / "in.evt"
    input_evt.write_bytes(b"\x00\x00\x00\x00LfLe")

    out_dir = tmp_path / "does-not-exist"
    with pytest.raises(FileValidationError):
        validate_evt_file(input_evt, out_dir / "out.evtx")


def test_validate_legacy_evt_signature_rejects_missing_signature(
    tmp_path: Path,
) -> None:
    p = tmp_path / "bad.evt"
    p.write_bytes(b"\x00\x00\x00\x00NOPE")
    with pytest.raises(FileValidationError):
        validate_legacy_evt_signature(p)


def test_generate_output_path_default_dir(tmp_path: Path) -> None:
    input_evt = tmp_path / "System.evt"
    assert generate_output_path(input_evt) == tmp_path / "System.evtx"


def test_generate_output_path_custom_dir(tmp_path: Path) -> None:
    input_evt = tmp_path / "System.evt"
    out_dir = tmp_path / "out"
    assert generate_output_path(input_evt, out_dir) == out_dir / "System.evtx"


def test_find_evt_files_non_recursive(tmp_path: Path) -> None:
    (tmp_path / "a.evt").write_bytes(b"a")
    (tmp_path / "b.evt").write_bytes(b"b")
    (tmp_path / "c.evtx").write_bytes(b"c")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "d.evt").write_bytes(b"d")

    files = find_evt_files(tmp_path, recursive=False)
    assert [p.name for p in files] == ["a.evt", "b.evt"]


def test_find_evt_files_recursive(tmp_path: Path) -> None:
    (tmp_path / "a.evt").write_bytes(b"a")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "d.evt").write_bytes(b"d")

    files = find_evt_files(tmp_path, recursive=True)
    assert [p.relative_to(tmp_path).as_posix() for p in files] == ["a.evt", "sub/d.evt"]
