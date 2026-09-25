from __future__ import annotations

import json
from pathlib import Path

from academicos.sources.audit_bundle import (
    build_collection_audit,
    default_audit_path,
    redact_text,
    write_collection_audit,
)
from academicos.sources.health import mark_failure
from academicos.storage.db import connect_db, initialize_db


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
                "[privacy]",
                'cloud_policy = "explicit_only"',
                "background_cloud_calls = false",
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


def test_redact_text_removes_common_identity_and_auth_material() -> None:
    jwt = "eyJabc.def.ghi"
    text = (
        "Bearer super-secret user@example.com "
        f"{jwt} C:\\Users\\alice\\AcademicOS "
        "https://example.test/path?token=secret"
    )
    redacted = redact_text(text)

    assert "super-secret" not in redacted
    assert "user@example.com" not in redacted
    assert jwt not in redacted
    assert "\\alice\\" not in redacted
    assert "/path?token=secret" not in redacted
    assert "<email>" in redacted
    assert "<token>" in redacted


def test_collection_audit_is_allow_listed_and_excludes_raw_source_payloads(tmp_path: Path) -> None:
    config = _config(tmp_path)
    db = tmp_path / "data" / "academicos.db"
    conn = connect_db(db)
    initialize_db(conn)
    conn.execute(
        """
        INSERT INTO source_items(
            id, source_type, source_id, fetched_at, content_hash, raw_text, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "private-source",
            "email",
            "m365:private",
            "2026-09-25T12:00:00+00:00",
            "hash",
            "Professor secret body user@example.com GRADE=97",
            json.dumps({"access_token": "DO_NOT_LEAK", "body": "private assignment text"}),
        ),
    )
    conn.commit()
    mark_failure(
        conn,
        "mail:m365",
        "Bearer TOPSECRET for user@example.com at https://example.test/private?x=1",
    )
    conn.close()

    payload = build_collection_audit(config_path=config)
    serialized = json.dumps(payload)

    assert payload["sanitized"] is True
    assert payload["database"]["counts"]["source_items"] == 1
    assert "Professor secret body" not in serialized
    assert "private assignment text" not in serialized
    assert "DO_NOT_LEAK" not in serialized
    assert "TOPSECRET" not in serialized
    assert "user@example.com" not in serialized
    assert "GRADE=97" not in serialized
    assert "example.test/private" not in serialized
    assert "<email>" in serialized


def test_collection_audit_can_be_written_to_default_audit_directory(tmp_path: Path) -> None:
    config = _config(tmp_path)
    payload = build_collection_audit(config_path=config)
    destination = default_audit_path(config)

    write_collection_audit(payload, destination)

    assert destination.exists()
    assert destination.parent == tmp_path / "data" / "audits"
    saved = json.loads(destination.read_text(encoding="utf-8"))
    assert saved["format"] == "academicos.collection_audit.v1"
