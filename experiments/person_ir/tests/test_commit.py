from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from experiments.person_ir import AuthorityRegistry, Interpreter, Node, Program, VersionedState


def _request(observation: dict, current: object):
    program = Program(
        "academic-plan",
        (
            Node("evidence", "observe", parameters={"source": "deadline", "label": "public"}),
            Node("current", "state_view", parameters={"source": "plan", "label": "protected"}),
            Node("derived", "join", ("evidence", "current")),
            Node("proposal", "propose", ("derived",), {"namespace": "study", "key": "plan"}),
            Node("commit", "commit_request", ("proposal",)),
        ),
    )
    return Interpreter().run(program, {"deadline": observation}, {"plan": current}).intents[0]


def _grant(authority: AuthorityRegistry, intent):
    return authority.issue_for_intent(
        intent, principal="person:george", domain="personal", issuer="person:george"
    )


def _commit(store, proposal_id, authority, handle):
    return store.commit(
        proposal_id, authority, handle, principal="person:george", domain="personal"
    )


def test_valid_commit_persists_and_recomputation_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "person-ir.db"
    authority = AuthorityRegistry()
    evidence = {"due": "Friday"}
    with VersionedState(db) as store:
        base = store.read("study", "plan")
        intent = _request(evidence, base.value)
        proposal_id = store.prepare(intent, base, principal="person:george", domain="personal")
        assert (
            store.prepare(intent, base, principal="person:george", domain="personal") == proposal_id
        )
        assert store.read("study", "plan").version == 0
        assert store.proposal(proposal_id)["sources"] == ["deadline", "plan"]
        handle = _grant(authority, intent)
        assert _commit(store, proposal_id, authority, handle) == "committed"
    with VersionedState(db) as store:
        assert store.read("study", "plan").value == [{"due": "Friday"}, None]
        assert store.read("study", "plan").version == 1
        assert _commit(store, proposal_id, authority, handle) == "already_committed"
        assert store.proposal(proposal_id)["committed_version"] == 1
    assert evidence == {"due": "Friday"}


def test_stale_and_rejected_proposals_leave_current_state_and_evidence_intact(
    tmp_path: Path,
) -> None:
    evidence = {"due": "Friday"}
    authority = AuthorityRegistry()
    with VersionedState(tmp_path / "state.db") as store:
        base = store.read("study", "plan")
        first = _request(evidence, base.value)
        second = _request({"due": "Saturday"}, base.value)
        first_id = store.prepare(first, base, principal="person:george", domain="personal")
        stale_id = store.prepare(second, base, principal="person:george", domain="personal")
        assert _commit(store, first_id, authority, _grant(authority, first)) == "committed"
        assert _commit(store, stale_id, authority, _grant(authority, second)) == "stale"
        assert store.proposal(stale_id)["status"] == "stale"
        assert store.read("study", "plan").value == [{"due": "Friday"}, None]
        current = store.read("study", "plan")
        later = _request({"due": "Sunday"}, current.value)
        rejected_id = store.prepare(later, current, principal="person:george", domain="personal")
        store.reject(rejected_id)
        with pytest.raises(ValueError, match="no longer pending"):
            _commit(store, rejected_id, authority, _grant(authority, later))
        assert store.proposal(rejected_id)["status"] == "rejected"
        assert store.read("study", "plan").version == 1
    assert evidence == {"due": "Friday"}


def test_no_authority_revoked_authority_and_forged_snapshot_fail(tmp_path: Path) -> None:
    authority = AuthorityRegistry()
    with VersionedState(tmp_path / "state.db") as store:
        base = store.read("study", "plan")
        intent = _request({"due": "Friday"}, base.value)
        with pytest.raises(PermissionError, match="host-issued snapshot"):
            store.prepare(intent, replace(base), principal="person:george", domain="personal")
        proposal_id = store.prepare(intent, base, principal="person:george", domain="personal")
        with pytest.raises(PermissionError, match="handle required"):
            _commit(store, proposal_id, authority, None)
        read_only = authority.issue(
            principal="person:george",
            domain="personal",
            operation="state.read",
            resource='["study","plan"]',
            issuer="person:george",
        )
        with pytest.raises(PermissionError, match="scope"):
            _commit(store, proposal_id, authority, read_only)
        handle = _grant(authority, intent)
        authority.revoke(handle)
        with pytest.raises(PermissionError, match="revoked"):
            _commit(store, proposal_id, authority, handle)
        assert store.proposal(proposal_id)["status"] == "pending"
        assert store.read("study", "plan").version == 0
