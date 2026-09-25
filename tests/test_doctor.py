from __future__ import annotations

import json
from pathlib import Path

from academicos.sources.doctor import run_doctor, write_doctor_report


def _config(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    config = tmp_path / "config.local.toml"
    config.write_text(
        "\n".join(
            [
                "[app]",
                f'data_dir = "{data_dir.as_posix()}"',
                f'database = "{(data_dir / "academicos.db").as_posix()}"',
                "",
                "[brightspace]",
                "enabled = false",
                "",
                "[mail]",
                "enabled = false",
            ]
        ),
        encoding="utf-8",
    )
    return config


def test_doctor_local_checks_initialize_database(tmp_path: Path) -> None:
    config = _config(tmp_path)

    report = run_doctor(config_path=config)

    assert report.failures == 0
    checks = {item.name: item for item in report.checks}
    assert checks["python"].status == "PASS"
    assert checks["config"].status == "PASS"
    assert checks["data_dir"].status == "PASS"
    assert checks["database"].status == "PASS"
    assert "schema=v5" in checks["database"].detail
    assert checks["brightspace"].status == "SKIP"
    assert checks["mail"].status == "SKIP"


def test_doctor_missing_config_is_failure(tmp_path: Path) -> None:
    report = run_doctor(config_path=tmp_path / "missing.toml")

    assert report.failures == 1
    assert report.checks[-1].name == "config"
    assert report.checks[-1].status == "FAIL"


def test_doctor_report_is_machine_readable_and_contains_no_secret_fields(tmp_path: Path) -> None:
    config = _config(tmp_path)
    report = run_doctor(config_path=config)
    output = tmp_path / "doctor.json"

    write_doctor_report(report, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    serialized = json.dumps(payload).lower()

    assert payload["summary"]["failures"] == 0
    assert "access_token" not in serialized
    assert "authorization" not in serialized
    assert "cookie" not in serialized
