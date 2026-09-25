from __future__ import annotations

from pathlib import Path

import pytest

from academicos.sources.windows_scheduler import (
    SchedulerError,
    install_command,
    sync_action,
)


def test_sync_action_quotes_python_and_config_paths(tmp_path: Path) -> None:
    config = tmp_path / "config local.toml"
    action = sync_action(
        config,
        python_executable=r"C:\Program Files\Python\python.exe",
    )

    assert '"C:\\Program Files\\Python\\python.exe"' in action
    assert "academicos.sources.sync_cli" in action
    assert '"' in action


def test_install_command_enforces_minimum_interval(tmp_path: Path) -> None:
    with pytest.raises(SchedulerError):
        install_command(tmp_path / "config.toml", interval_minutes=5)


def test_install_command_builds_minute_schedule(tmp_path: Path) -> None:
    command = install_command(
        tmp_path / "config.toml",
        interval_minutes=30,
        python_executable=r"C:\Python\python.exe",
    )

    assert command.args[0] == "schtasks"
    assert "/SC" in command.args
    assert "MINUTE" in command.args
    assert "/MO" in command.args
    assert "30" in command.args
    assert "/TR" in command.args
