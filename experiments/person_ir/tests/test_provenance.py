from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from experiments.person_ir import (
    AuthorityRegistry,
    EffectLedger,
    Evidence,
    Interpreter,
    Node,
    Program,
    VerificationError,
    VersionedState,
    verify,
)


def _email(*, destination="friend@example.org", purpose="Share note", scope="whole_value"):
    return Program(
        "mail-example",
        (
            Node("draft", "observe", parameters={"source": "draft", "label": "protected"}),
            Node("text", "transform", ("draft",), {"op": "get", "key": "text"}),
            Node(
                "release",
                "declassify",
                ("text",),
                {
                    "destination": destination,
                    "scope": scope,
                    "purpose": purpose,
                },
            ),
            Node(
                "send",
                "effect_request",
                ("release",),
                {
                    "kind": "email",
                    "destination": "friend@example.org",
                    "purpose": "Share note",
                },
            ),
        ),
        version="1.2.0",
    )


def test_trace_tracks_input_transform_program_disclosure_and_grant(tmp_path: Path) -> None:
    evidence = Evidence(
        "draft",
        "observation:42",
        "ai-adapter",
        "2.1",
        "protected",
        state_version=7,
        deterministic=False,
        execution_id="inference:abc",
    )
    intent = (
        Interpreter()
        .run(_email(), {"draft": {"text": "hello"}}, evidence={"draft": evidence})
        .intents[0]
    )
    trace = intent.trace
    assert trace.program == "mail-example" and trace.program_version == "1.2.0"
    assert trace.evidence == (evidence,)
    assert trace.steps == (
        "draft:observe",
        "text:transform:get:text",
        "release:declassify",
        "send:effect_request",
    )
    assert trace.disclosures == (("friend@example.org", "whole_value", "Share note"),)
    authority = AuthorityRegistry()
    with EffectLedger(tmp_path / "effects.db") as ledger:
        request_id = ledger.request(intent, principal="person:george", domain="personal")
        handle = authority.issue_for_intent(
            intent, principal="person:george", domain="personal", issuer="person:george"
        )
        ledger.approve(request_id, authority, handle, principal="person:george", domain="personal")
        assert (
            ledger.dispatch(
                request_id, authority, handle, principal="person:george", domain="personal"
            )
            == "succeeded"
        )
        record = ledger.get(request_id)
        assert record["trace"]["evidence"][0]["execution_id"] == "inference:abc"
        assert record["trace"]["evidence"][0]["state_version"] == 7
        assert record["approved_capability_id"] == authority.inspect(handle).capability_id
        assert record["dispatch_capability_id"] == authority.inspect(handle).capability_id


def test_commit_persists_program_lineage_state_version_and_authority(tmp_path: Path) -> None:
    authority = AuthorityRegistry()
    with VersionedState(tmp_path / "state.db") as store:
        base = store.read("study", "plan")
        program = Program(
            "planner",
            (
                Node(
                    "calendar",
                    "state_view",
                    parameters={"source": "calendar", "label": "protected"},
                ),
                Node("proposal", "propose", ("calendar",), {"namespace": "study", "key": "plan"}),
                Node("commit", "commit_request", ("proposal",)),
            ),
            version="0.3",
        )
        intent = (
            Interpreter()
            .run(
                program,
                {},
                {"calendar": base.value},
                evidence={
                    "calendar": Evidence(
                        "calendar", "state:plan@0", "local-store", "1", state_version=0
                    )
                },
            )
            .intents[0]
        )
        proposal_id = store.prepare(intent, base, principal="person:george", domain="personal")
        handle = authority.issue_for_intent(
            intent, principal="person:george", domain="personal", issuer="person:george"
        )
        assert (
            store.commit(
                proposal_id, authority, handle, principal="person:george", domain="personal"
            )
            == "committed"
        )
        record = store.proposal(proposal_id)
        assert record["trace"]["program_version"] == "0.3"
        assert record["trace"]["evidence"][0]["state_version"] == 0
        assert record["authority_id"] == authority.inspect(handle).capability_id


@pytest.mark.parametrize(
    "kwargs, reason",
    [
        ({"destination": "other@example.org"}, "matching disclosure"),
        ({"purpose": "Different use"}, "matching disclosure"),
        ({"scope": "partial"}, "only whole_value"),
    ],
)
def test_verifier_rejects_invalid_disclosure_before_execution(kwargs, reason) -> None:
    with pytest.raises(VerificationError, match=reason):
        verify(_email(**kwargs))


def test_nondeterministic_evidence_requires_execution_identity() -> None:
    with pytest.raises(ValueError, match="execution metadata"):
        Interpreter().run(
            _email(),
            {"draft": {"text": "hello"}},
            evidence={
                "draft": Evidence(
                    "draft", "observation:42", "ai", "2", "protected", deterministic=False
                )
            },
        )


def test_host_label_disagreement_and_unverified_external_input_fail(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="graph label disagrees"):
        Interpreter().run(
            _email(),
            {"draft": {"text": "hello"}},
            evidence={"draft": Evidence("draft", "obs:1", "host", "1", "public")},
        )
    unverified = Interpreter().run(_email(), {"draft": {"text": "hello"}}).intents[0]
    with EffectLedger(tmp_path / "effects.db") as ledger:
        with pytest.raises(PermissionError, match="host-labeled evidence"):
            ledger.request(unverified, principal="person:george", domain="personal")


def test_join_propagates_protected_label_and_requires_full_disclosure() -> None:
    program = Program(
        "join",
        (
            Node("public", "observe", parameters={"source": "public", "label": "public"}),
            Node("private", "observe", parameters={"source": "private", "label": "protected"}),
            Node(
                "release",
                "declassify",
                ("private",),
                {
                    "destination": "friend@example.org",
                    "scope": "whole_value",
                    "purpose": "Share note",
                },
            ),
            Node("again", "state_view", parameters={"source": "more", "label": "protected"}),
            Node("joined", "join", ("release", "again")),
            Node(
                "send",
                "effect_request",
                ("joined",),
                {
                    "kind": "email",
                    "destination": "friend@example.org",
                    "purpose": "Share note",
                },
            ),
        ),
    )
    with pytest.raises(VerificationError, match="matching disclosure"):
        verify(program)


def test_prior_experiment_databases_gain_trace_columns(tmp_path: Path) -> None:
    state_db, effect_db = tmp_path / "old-state.db", tmp_path / "old-effects.db"
    with sqlite3.connect(state_db) as conn:
        conn.execute(
            """CREATE TABLE person_ir_proposals(
                id INTEGER PRIMARY KEY, identity_hash TEXT UNIQUE, principal TEXT, domain TEXT,
                namespace TEXT, record_key TEXT, base_version INTEGER, base_hash TEXT,
                payload_json TEXT, sources_json TEXT, status TEXT, committed_version INTEGER)"""
        )
    with sqlite3.connect(effect_db) as conn:
        conn.execute(
            """CREATE TABLE person_ir_effects(
                id INTEGER PRIMARY KEY, identity_hash TEXT UNIQUE, principal TEXT, domain TEXT,
                kind TEXT, destination TEXT, purpose TEXT, payload_json TEXT, sources_json TEXT,
                disclosures_json TEXT, status TEXT, outcome_json TEXT)"""
        )
    with VersionedState(state_db) as store:
        columns = {
            row["name"] for row in store.conn.execute("PRAGMA table_info(person_ir_proposals)")
        }
        assert {"trace_json", "authority_id"} <= columns
    with EffectLedger(effect_db) as ledger:
        columns = {
            row["name"] for row in ledger.conn.execute("PRAGMA table_info(person_ir_effects)")
        }
        assert {"trace_json", "approved_capability_id", "dispatch_capability_id"} <= columns
