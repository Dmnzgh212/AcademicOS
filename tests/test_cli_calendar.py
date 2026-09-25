import json
from pathlib import Path

from typer.testing import CliRunner

from academicos.cli import app

runner = CliRunner()


def test_cli_import_and_day(tmp_path: Path) -> None:
    db = tmp_path / "academic.db"
    timetable = tmp_path / "timetable.json"
    timetable.write_text(
        json.dumps(
            {
                "term": "2026F",
                "courses": [
                    {
                        "code": "CEG2136",
                        "name": "Computer Architecture I",
                        "section": "A00",
                        "sessions": [
                            {
                                "session_type": "lecture",
                                "days": ["MO"],
                                "start_time": "14:30",
                                "end_time": "15:50",
                                "start_date": "2026-09-01",
                                "end_date": "2026-12-04",
                                "location": "SITE",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["timetable-import", str(timetable), "--db", str(db)],
    )
    assert result.exit_code == 0, result.output
    assert "1 course(s)" in result.output

    result = runner.invoke(
        app,
        ["day", "2026-09-28", "--db", str(db)],
    )
    assert result.exit_code == 0, result.output
    assert "CEG2136 A00" in result.output
    assert "14:30–15:50" in result.output


def test_cli_day_json(tmp_path: Path) -> None:
    db = tmp_path / "academic.db"
    result = runner.invoke(app, ["init-db", "--db", str(db)])
    assert result.exit_code == 0

    result = runner.invoke(app, ["day", "2026-09-28", "--db", str(db), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == []


def test_cli_week(tmp_path: Path) -> None:
    db = tmp_path / "academic.db"
    timetable = tmp_path / "timetable.json"
    timetable.write_text(
        json.dumps(
            {
                "term": "2026F",
                "courses": [
                    {
                        "code": "CEG2136",
                        "name": "Computer Architecture I",
                        "section": "A00",
                        "sessions": [
                            {
                                "session_type": "lecture",
                                "days": ["MO", "TH"],
                                "start_time": "14:30",
                                "end_time": "15:50",
                                "start_date": "2026-09-01",
                                "end_date": "2026-12-04"
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    runner.invoke(app, ["timetable-import", str(timetable), "--db", str(db)])

    result = runner.invoke(app, ["week", "2026-09-30", "--db", str(db)])
    assert result.exit_code == 0, result.output
    assert "2026-09-28" in result.output
    assert result.output.count("CEG2136 A00") == 2
