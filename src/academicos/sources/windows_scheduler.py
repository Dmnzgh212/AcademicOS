from __future__ import annotations

import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

TASK_NAME = "AcademicOS Sync"


class SchedulerError(RuntimeError):
    pass


@dataclass(frozen=True)
class SchedulerCommand:
    args: tuple[str, ...]

    def display(self) -> str:
        return subprocess.list2cmdline(list(self.args))


def _require_windows() -> None:
    if platform.system() != "Windows":
        raise SchedulerError("Windows Task Scheduler integration is available only on Windows")


def sync_action(config_path: Path, *, python_executable: str | None = None) -> str:
    python = python_executable or sys.executable
    config = str(config_path.resolve())
    return subprocess.list2cmdline(
        [python, "-m", "academicos.sources.sync_cli", "--config", config]
    )


def install_command(
    config_path: Path,
    *,
    interval_minutes: int = 30,
    python_executable: str | None = None,
) -> SchedulerCommand:
    if interval_minutes < 15:
        raise SchedulerError("sync interval must be at least 15 minutes")
    action = sync_action(config_path, python_executable=python_executable)
    return SchedulerCommand(
        (
            "schtasks",
            "/Create",
            "/TN",
            TASK_NAME,
            "/SC",
            "MINUTE",
            "/MO",
            str(interval_minutes),
            "/TR",
            action,
            "/F",
        )
    )


def status_command() -> SchedulerCommand:
    return SchedulerCommand(("schtasks", "/Query", "/TN", TASK_NAME, "/V", "/FO", "LIST"))


def remove_command() -> SchedulerCommand:
    return SchedulerCommand(("schtasks", "/Delete", "/TN", TASK_NAME, "/F"))


def run(command: SchedulerCommand) -> subprocess.CompletedProcess[str]:
    _require_windows()
    result = subprocess.run(
        list(command.args),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "schtasks failed").strip()
        raise SchedulerError(detail)
    return result
