import subprocess
from pathlib import Path

import pytest

import evt_parser.converter as converter
from evt_parser.converter import ConversionStatus, convert_evt_to_evtx


def test_convert_returns_skipped_when_output_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_evt = tmp_path / "in.evt"
    input_evt.write_bytes(b"\x00\x00\x00\x00LfLe")
    output_evtx = tmp_path / "out.evtx"
    output_evtx.write_bytes(b"existing")

    monkeypatch.setattr(converter, "check_platform", lambda: None)
    monkeypatch.setattr(converter, "check_wevtutil_available", lambda: None)

    result = convert_evt_to_evtx(input_evt, output_evtx, overwrite=False)
    assert result.status == ConversionStatus.SKIPPED


def test_convert_builds_wevtutil_command_and_writes_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_evt = tmp_path / "in.evt"
    input_evt.write_bytes(b"\x00\x00\x00\x00LfLe")
    output_evtx = tmp_path / "out.evtx"

    monkeypatch.setattr(converter, "check_platform", lambda: None)
    monkeypatch.setattr(converter, "check_wevtutil_available", lambda: None)

    captured = {}

    def fake_run(command, capture_output, text, timeout, check):
        captured["command"] = command
        output_evtx.write_bytes(b"evtx")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(converter.subprocess, "run", fake_run)

    result = convert_evt_to_evtx(input_evt, output_evtx, overwrite=True, timeout=5)
    assert result.status == ConversionStatus.SUCCESS
    assert result.output_file == output_evtx
    assert output_evtx.exists()
    assert captured["command"][0:3] == ["wevtutil", "epl", str(input_evt.absolute())]
    assert captured["command"][-1] == "/lf:true"
