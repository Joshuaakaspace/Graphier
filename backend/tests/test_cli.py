import pytest

from graphier import cli


def test_engine_detected_in_dev_environment():
    assert cli.engine_installed() is True


def test_missing_engine_message_and_exit(monkeypatch, capsys):
    monkeypatch.setattr(cli, "engine_installed", lambda: False)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "graphier setup" in err and "--no-deps" in err


def test_setup_invokes_lean_pip_install(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.subprocess, "call", lambda cmd: calls.append(cmd) or 0)
    monkeypatch.setattr(cli.sys, "argv", ["graphier", "setup"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert calls and "--no-deps" in calls[0] and "semantica" in calls[0]


def test_mcp_guard(monkeypatch, capsys):
    monkeypatch.setattr(cli, "engine_installed", lambda: False)
    with pytest.raises(SystemExit):
        cli.mcp_main()
    assert "graphier setup" in capsys.readouterr().err
