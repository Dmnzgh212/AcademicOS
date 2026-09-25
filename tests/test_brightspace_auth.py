from __future__ import annotations

import base64
import json
import time
from pathlib import Path

from academicos.sources.brightspace.auth import (
    TOKEN_AUDIENCE,
    TOKEN_ISSUER,
    load_saved_token,
    save_token,
    token_info,
    valid_token_claims,
)


def _segment(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def fake_token(exp: int) -> str:
    return ".".join(
        [
            _segment({"alg": "none", "typ": "JWT"}),
            _segment(
                {
                    "iss": TOKEN_ISSUER,
                    "aud": TOKEN_AUDIENCE,
                    "exp": exp,
                    "sub": "student-1",
                    "tenantid": "tenant-1",
                }
            ),
            "signature",
        ]
    )


def test_valid_token_claims_rejects_expired_token() -> None:
    assert valid_token_claims(fake_token(int(time.time()) - 10)) is None


def test_save_and_load_token_stays_inside_auth_directory(tmp_path: Path) -> None:
    token = fake_token(int(time.time()) + 3600)
    saved = save_token(tmp_path, token)

    assert saved == tmp_path / "token.json"
    assert load_saved_token(tmp_path) == token
    assert token not in str(token_info(tmp_path))
    assert token_info(tmp_path)["status"] == "valid"
    assert token_info(tmp_path)["user_id"] == "student-1"
