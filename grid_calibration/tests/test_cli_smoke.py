from __future__ import annotations

from pathlib import Path

import pytest

import grid_calibration.cli as cli


def test_cli_help_is_available_without_launching_gui(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"], launch_gui=lambda *args, **kwargs: None)

    assert exc.value.code == 0
    assert "Launch the GONet grid-calibration GUI" in capsys.readouterr().out


def test_cli_filters_inputs_and_delegates_to_launcher(
    tmp_path: Path,
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

    cli.main(
        [
            str(jpg),
            str(txt),
            "--outdir",
            str(tmp_path / "out"),
            "--debug",
        ],
        launch_gui=fake_launch,
    )

    assert calls["files"] == [jpg]
    assert calls["output_dir"] == str(tmp_path / "out")
    assert calls["debug"] is True

def test_module_entrypoint_delegates_to_cli_main(monkeypatch):
    import grid_calibration.__main__ as module_main

    called = {}

    def fake_main():
        called["ok"] = True

    monkeypatch.setattr(module_main, "main", fake_main)

    module_main.main()

    assert called["ok"] is True