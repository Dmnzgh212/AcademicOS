from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from experiments.person_ir import AuthorityRegistry, EffectLedger, Evidence, Interpreter, VersionedState
from experiments.person_ir import scenarios


PERSON = "person:alice"
DOMAIN = "personal"


def evidence(source: str, label: str = "protected") -> Evidence:
    return Evidence(source, f"fixture:{source}", "scenario-host", "1", label)


def grant(authority, intent, principal=PERSON):
    return authority.issue_for_intent(
        intent, principal=principal, domain=DOMAIN, issuer=principal
    )


def test_academic_proposal_does_not_commit_stale_calendar(tmp_path):
    authority = AuthorityRegistry()
    with VersionedState(tmp_path / "study.db") as state:
        base = state.read("study", "block")
        intent = Interpreter().run(
            scenarios.academic(), {"deadline": {"due": "Friday"}},
            {"calendar": {"free": "Thursday"}},
            {"deadline": evidence("deadline", "public"),
             "calendar": evidence("calendar")},
        ).intents[0]
        stale = state.prepare(intent, base, principal=PERSON, domain=DOMAIN)
        competing_intent = Interpreter().run(
            scenarios.academic(), {"deadline": {"due": "Saturday"}},
            {"calendar": {"free": "Wednesday"}},
            {"deadline": evidence("deadline", "public"),
             "calendar": evidence("calendar")},
        ).intents[0]
        competing = state.prepare(
            competing_intent, base, principal=PERSON, domain=DOMAIN
        )
        assert state.commit(competing, authority, grant(authority, competing_intent),
                            principal=PERSON, domain=DOMAIN) == "committed"
        assert state.commit(stale, authority, grant(authority, intent),
                            principal=PERSON, domain=DOMAIN) == "stale"
        assert state.read("study", "block").value == [
            {"due": "Saturday"}, {"free": "Wednesday"}
        ]


def test_email_disclosure_and_single_fake_delivery(tmp_path):
    intent = Interpreter().run(
        scenarios.email(), {"context": {"course": "BIO101"}, "draft": "Please meet"},
        evidence={"context": evidence("context"), "draft": evidence("draft")},
    ).intents[0]
    assert [item.source for item in intent.trace.evidence] == ["context", "draft"]
    authority = AuthorityRegistry()
    with EffectLedger(tmp_path / "effects.db") as ledger:
        request = ledger.request(intent, principal=PERSON, domain=DOMAIN)
        assert ledger.request(intent, principal=PERSON, domain=DOMAIN) == request
        handle = grant(authority, intent)
        ledger.approve(request, authority, handle, principal=PERSON, domain=DOMAIN)
        assert ledger.dispatch(request, authority, handle,
                               principal=PERSON, domain=DOMAIN) == "succeeded"
        with pytest.raises(ValueError, match="already attempted"):
            ledger.dispatch(request, authority, handle, principal=PERSON, domain=DOMAIN)
        assert ledger.conn.execute(
            "SELECT count(*) FROM person_ir_fake_deliveries"
        ).fetchone()[0] == 1


def test_purchase_revocation_blocks_fake_payment_but_price_is_not_refreshed(tmp_path):
    intent = Interpreter().run(
        scenarios.purchase(), {"order": {"item": "book"}, "price": {"cents": 1200}},
        evidence={"order": evidence("order"), "price": evidence("price", "public")},
    ).intents[0]
    authority = AuthorityRegistry()
    with EffectLedger(tmp_path / "payment.db") as ledger:
        request = ledger.request(intent, principal=PERSON, domain=DOMAIN)
        handle = grant(authority, intent)
        ledger.approve(request, authority, handle, principal=PERSON, domain=DOMAIN)
        authority.revoke(handle)
        with pytest.raises(PermissionError, match="revoked"):
            ledger.dispatch(request, authority, handle, principal=PERSON, domain=DOMAIN)
        assert ledger.get(request)["status"] == "approved"
        # The current price can change without invalidating this approved request.
        # The host needs a fresh price/order check immediately before dispatch.
        assert ledger.get(request)["payload"] == [{"item": "book"}, {"cents": 1200}]


def test_device_expired_grant_prevents_fake_physical_effect(tmp_path):
    intent = Interpreter().run(
        scenarios.device(), {"sensor": {"celsius": 16}},
        {"policy": {"target": 20}},
        {"sensor": evidence("sensor", "public"), "policy": evidence("policy")},
    ).intents[0]
    current = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
    authority = AuthorityRegistry(clock=lambda: current[0])
    with EffectLedger(tmp_path / "device.db") as ledger:
        request = ledger.request(intent, principal=PERSON, domain=DOMAIN)
        handle = authority.issue_for_intent(
            intent, principal=PERSON, domain=DOMAIN, issuer=PERSON,
            expires_at=current[0] + timedelta(seconds=1),
        )
        ledger.approve(request, authority, handle, principal=PERSON, domain=DOMAIN)
        current[0] += timedelta(seconds=2)
        with pytest.raises(PermissionError, match="expired"):
            ledger.dispatch(request, authority, handle, principal=PERSON, domain=DOMAIN)
        assert ledger.get(request)["status"] == "approved"


def test_collaboration_conflict_and_single_person_authority_gap(tmp_path):
    intent = Interpreter().run(
        scenarios.collaboration(), {"alice": "Monday", "bob": "Tuesday"},
        {"shared": {"meeting": "Friday"}},
        {name: evidence(name) for name in ("alice", "bob", "shared")},
    ).intents[0]
    authority = AuthorityRegistry()
    with VersionedState(tmp_path / "team.db") as state:
        base = state.read("team", "plan")
        proposal = state.prepare(intent, base, principal=PERSON, domain=DOMAIN)
        alice = grant(authority, intent)
        with pytest.raises(PermissionError):
            state.commit(proposal, authority, alice,
                         principal="person:bob", domain=DOMAIN)
        # A single Alice grant still commits data sourced from Bob. This is a
        # demonstrated missing multi-principal policy, not a collaboration pass.
        assert state.commit(proposal, authority, alice,
                            principal=PERSON, domain=DOMAIN) == "committed"
        assert state.read("team", "plan").value[0] == ["Monday", "Tuesday"]
