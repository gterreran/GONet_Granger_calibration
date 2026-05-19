from __future__ import annotations

from pathlib import Path

import pytest

import grid_calibration.__main__ as cli


def test_cli_help_is_available_without_launching_gui(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"], launch_gui=lambda *args, **kwargs: None)

    assert exc.value.code == 0
    assert "GONet Grid Calibration GUI Launcher" in capsys.readouterr().out


def test_cli_filters_inputs_and_delegates_to_launcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jpg = tmp_path / "frame_001.jpg"
    txt = tmp_path / "notes.txt"
    jpg.write_bytes(b"jpg")
    txt.write_text("not an image")

    calls: dict[str, object] = {}

    def fake_launch(files, *, output_dir=None, debug=False):
        calls["files"] = files
        calls["output_dir"] = output_dir
        calls["debug"] = debug

    cli.main([str(jpg), str(txt), "--outdir", str(tmp_path / "out"), "--debug"], launch_gui=fake_launch)

    assert calls["files"] == [jpg]
    assert calls["output_dir"] == str(tmp_path / "out")
    assert calls["debug"] is True
