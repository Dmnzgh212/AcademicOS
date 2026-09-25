from __future__ import annotations

from pathlib import Path

from academicos.sources.sync import load_sync_config


def test_load_sync_config_preserves_course_source_mappings(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        """
[app]
timezone = "America/Toronto"
database = "data/test.db"

[brightspace]
enabled = true
host = "https://example.brightspace.com"

[[brightspace.courses]]
code = "CEG2136"
section = "A00"
org_id = "12345"
download_files = true

[mail]
enabled = false
client_id = "example-client-id"
""".strip(),
        encoding="utf-8",
    )

    loaded = load_sync_config(config)

    assert loaded["brightspace"]["host"] == "https://example.brightspace.com"
    assert loaded["brightspace"]["courses"][0]["code"] == "CEG2136"
    assert loaded["brightspace"]["courses"][0]["org_id"] == "12345"
    assert loaded["brightspace"]["courses"][0]["download_files"] is True
    assert loaded["mail"]["enabled"] is False
