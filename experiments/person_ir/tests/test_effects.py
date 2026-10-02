from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from experiments.person_ir import (
    AuthorityRegistry,
    EffectLedger,
    Interpreter,
    Node,
    Outcome,
    Program,
    VersionedState,
)


def _request(text: str):
    program = Program(
        "send-note",
        (
            Node("draft", "observe", parameters={"source": "draft", "label": "protected"}),
            Node(
                "release",
                "declassify",
                ("draft",),
                {
                    "destination": "friend@example.org",
                    "purpose": "Share selected note",
                },
            ),
            Node(
                "send",
                "effect_request",
                ("release",),
                {
                    "kind": "email",
                    "destination": "friend@example.org",
                    "purpose": "Share selected note",
                },
            ),
        ),
    )
    return Interpreter().run(program, {"draft": {"text": text}}).intents[0]


def _grant(authority, intent):
    return authority.issue_for_intent(
        intent, principal="person:george", domain="personal", issuer="person:george"
    )


def _approve(ledger, request_id, authority, handle):
    return ledger.approve(
        request_id, authority, handle, principal="person:george", domain="personal"
    )


def _dispatch(ledger, request_id, authority, handle):
    return ledger.dispatch(
        request_id, authority, handle, principal="person:george", domain="personal"
    )


def test_request_approval_dispatch_and_deduplication(tmp_path: Path) -> None:
    db = tmp_path / "effects.db"
    authority = AuthorityRegistry()
    intent = _request("hello")
    with EffectLedger(db) as ledger:
        request_id = ledger.request(intent, principal="person:george", domain="personal")
        assert ledger.request(intent, principal="person:george", domain="personal") == request_id
        assert ledger.get(request_id)["status"] == "pending"
        assert (
            ledger.conn.execute("SELECT count(*) FROM person_ir_fake_deliveries").fetchone()[0] == 0
        )
        handle = _grant(authority, intent)
        with pytest.raises(ValueError, match="not approved"):
            _dispatch(ledger, request_id, authority, handle)
        _approve(ledger, request_id, authority, handle)
        assert ledger.get(request_id)["status"] == "approved"
        assert (
            ledger.conn.execute("SELECT count(*) FROM person_ir_fake_deliveries").fetchone()[0] == 0
        )
        assert _dispatch(ledger, request_id, authority, handle) == "succeeded"
        with pytest.raises(ValueError, match="already attempted"):
            _dispatch(ledger, request_id, authority, handle)
        assert (
            ledger.conn.execute("SELECT count(*) FROM person_ir_fake_deliveries").fetchone()[0] == 1
        )
        changed = ledger.request(
            _request("hello, edited"), principal="person:george", domain="personal"
        )
        assert changed != request_id and ledger.get(changed)["status"] == "pending"
    with EffectLedger(db) as ledger:
        assert ledger.get(request_id)["status"] == "succeeded"
        assert ledger.request(intent, principal="person:george", domain="personal") == request_id
        assert (
            ledger.conn.execute("SELECT count(*) FROM person_ir_fake_deliveries").fetchone()[0] == 1
        )


def test_missing_or_revoked_authority_prevents_dispatch(tmp_path: Path) -> None:
    authority = AuthorityRegistry()
    intent = _request("private")
    with EffectLedger(tmp_path / "effects.db") as ledger:
        request_id = ledger.request(intent, principal="person:george", domain="personal")
        with pytest.raises(PermissionError, match="handle required"):
            _approve(ledger, request_id, authority, None)
        handle = _grant(authority, intent)
        _approve(ledger, request_id, authority, handle)
        authority.revoke(handle)
        with pytest.raises(PermissionError, match="revoked"):
            _dispatch(ledger, request_id, authority, handle)
        assert ledger.get(request_id)["status"] == "approved"
        assert (
            ledger.conn.execute("SELECT count(*) FROM person_ir_fake_deliveries").fetchone()[0] == 0
        )


def test_known_failure_and_uncertain_failure_are_distinct_and_never_retried(tmp_path: Path) -> None:
    authority = AuthorityRegistry()
    intent = _request("pay attention")
    calls = []

    def refused(row):
        calls.append(row["id"])
        return Outcome(False, "fake recipient refused")

    db = tmp_path / "effects.db"
    with EffectLedger(db, executor=refused) as ledger:
        request_id = ledger.request(intent, principal="person:george", domain="personal")
        handle = _grant(authority, intent)
        _approve(ledger, request_id, authority, handle)
        assert _dispatch(ledger, request_id, authority, handle) == "failed"
        assert ledger.get(request_id)["outcome"] == {"detail": "fake recipient refused"}
        with pytest.raises(ValueError, match="already attempted"):
            _dispatch(ledger, request_id, authority, handle)
        assert calls == [request_id]

    def lost_response(row):
        calls.append(row["id"])
        raise RuntimeError("response lost after possible action")

    with EffectLedger(db, executor=lost_response) as ledger:
        uncertain_intent = _request("different")
        uncertain_id = ledger.request(
            uncertain_intent, principal="person:george", domain="personal"
        )
        handle = _grant(authority, uncertain_intent)
        _approve(ledger, uncertain_id, authority, handle)
        assert _dispatch(ledger, uncertain_id, authority, handle) == "unknown"
        assert ledger.get(uncertain_id)["outcome"] is None
        with pytest.raises(ValueError, match="already attempted"):
            _dispatch(ledger, uncertain_id, authority, handle)
        assert calls == [request_id, uncertain_id]


def test_interrupted_action_requires_operator_recovery(tmp_path: Path) -> None:
    authority = AuthorityRegistry()
    intent = _request("interrupted")

    def interrupted(_row):
        raise SystemExit("simulated process exit")

    db = tmp_path / "effects.db"
    with EffectLedger(db, executor=interrupted) as ledger:
        request_id = ledger.request(intent, principal="person:george", domain="personal")
        handle = _grant(authority, intent)
        _approve(ledger, request_id, authority, handle)
        with pytest.raises(SystemExit):
            _dispatch(ledger, request_id, authority, handle)
    with EffectLedger(db) as ledger:
        assert ledger.get(request_id)["status"] == "in_flight"
        ledger.mark_unknown(request_id)
        assert ledger.get(request_id)["status"] == "unknown"
        with pytest.raises(ValueError, match="already attempted"):
            _dispatch(ledger, request_id, authority, handle)


def test_local_state_change_does_not_undo_completed_effect(tmp_path: Path) -> None:
    authority = AuthorityRegistry()
    intent = _request("sent")
    with EffectLedger(tmp_path / "effects.db") as ledger:
        request_id = ledger.request(intent, principal="person:george", domain="personal")
        handle = _grant(authority, intent)
        _approve(ledger, request_id, authority, handle)
        assert _dispatch(ledger, request_id, authority, handle) == "succeeded"
        with VersionedState(tmp_path / "state.db") as state:
            base = state.read("notes", "draft")
            program = Program(
                "edit-draft",
                (
                    Node("new", "observe", parameters={"source": "new", "label": "public"}),
                    Node("proposal", "propose", ("new",), {"namespace": "notes", "key": "draft"}),
                    Node("commit", "commit_request", ("proposal",)),
                ),
            )
            edit = Interpreter().run(program, {"new": {"text": "changed later"}}).intents[0]
            proposal_id = state.prepare(edit, base, principal="person:george", domain="personal")
            grant = _grant(authority, edit)
            assert (
                state.commit(
                    proposal_id, authority, grant, principal="person:george", domain="personal"
                )
                == "committed"
            )
            assert state.read("notes", "draft").value == {"text": "changed later"}
        assert ledger.get(request_id)["status"] == "succeeded"
        assert (
            ledger.conn.execute("SELECT count(*) FROM person_ir_fake_deliveries").fetchone()[0] == 1
        )


def test_rejection_and_wrong_disclosure_never_deliver(tmp_path: Path) -> None:
    intent = _request("secret")
    authority = AuthorityRegistry()
    with EffectLedger(tmp_path / "effects.db") as ledger:
        with pytest.raises(PermissionError, match="matching disclosure"):
            ledger.request(
                replace(intent, disclosures=(("other@example.org", "send"),)),
                principal="person:george",
                domain="personal",
            )
        request_id = ledger.request(intent, principal="person:george", domain="personal")
        handle = _grant(authority, intent)
        _approve(ledger, request_id, authority, handle)
        ledger.reject(request_id)
        with pytest.raises(ValueError, match="already attempted"):
            _dispatch(ledger, request_id, authority, handle)
        assert ledger.get(request_id)["status"] == "rejected"
        assert (
            ledger.conn.execute("SELECT count(*) FROM person_ir_fake_deliveries").fetchone()[0] == 0
        )
