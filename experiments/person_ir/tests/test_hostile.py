"""Hostile graph and host-boundary probes for the PersonIR experiment."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.person_ir import (
    AuthorityRegistry, Capability, EffectLedger, Evidence, Interpreter,
    Node, Program, VerificationError, VersionedState, verify,
)
from experiments.person_ir.scenarios import academic, email


PERSON = "person:alice"
DOMAIN = "personal"


def _mail():
    return Interpreter().run(
        email(), {"context": "private", "draft": "reviewed"},
        evidence={
            "context": Evidence("context", "c:1", "fixture", "1", "protected"),
            "draft": Evidence("draft", "d:1", "fixture", "1", "protected"),
        },
    ).intents[0]


def _grant(registry, intent):
    return registry.issue_for_intent(
        intent, principal=PERSON, domain=DOMAIN, issuer=PERSON
    )


def test_undeclared_state_and_missing_host_input_fail():
    with pytest.raises(VerificationError, match="unknown node"):
        verify(Program("read-private", (Node("read", "read_state", parameters={"key": "secret"}),)))
    with pytest.raises(KeyError, match="missing host input"):
        Interpreter().run(
            Program("state", (
                Node("secret", "state_view", parameters={"source": "secret", "label": "protected"}),
                Node("out", "output", ("secret",)),
            )), {}, {},
        )


def test_graph_cannot_synthesize_authority_or_embed_handle():
    with pytest.raises(VerificationError, match="unknown node"):
        verify(Program("mint", (Node("mint", "issue_capability"),)))
    registry = AuthorityRegistry()
    handle = registry.issue(
        principal=PERSON, domain=DOMAIN, operation="effect.dispatch",
        resource='["email","advisor@example.org"]', issuer=PERSON,
    )
    with pytest.raises(TypeError):
        Interpreter().run(
            Program("smuggle", (
                Node("input", "observe", parameters={"source": "input", "label": "public"}),
                Node("out", "output", ("input",)),
            )), {"input": handle},
        )
    with pytest.raises(PermissionError, match="not issued"):
        registry.require_intent(
            Capability(registry.inspect(handle).capability_id), _mail(),
            principal=PERSON, domain=DOMAIN,
        )


def test_protected_sink_without_disclosure_is_structurally_rejected():
    with pytest.raises(VerificationError, match="matching disclosure"):
        verify(Program("leak", (
            Node("secret", "observe", parameters={"source": "secret", "label": "protected"}),
            Node("send", "effect_request", ("secret",), {
                "kind": "email", "destination": "attacker@example.org", "purpose": "leak",
            }),
        )))


def test_disclosure_cannot_be_retargeted_or_bypassed_by_laundering():
    with pytest.raises(VerificationError, match="matching disclosure"):
        verify(Program("redirect", (
            Node("secret", "observe", parameters={"source": "secret", "label": "protected"}),
            Node("release", "declassify", ("secret",), {
                "destination": "advisor@example.org", "scope": "whole_value", "purpose": "review",
            }),
            Node("launder", "transform", ("release",), {"op": "identity", "key": "-"}),
            Node("send", "effect_request", ("launder",), {
                "kind": "email", "destination": "attacker@example.org", "purpose": "review",
            }),
        )))
    with EffectLedger(":memory:") as ledger:
        with pytest.raises(PermissionError, match="matching disclosure"):
            ledger.request(
                replace(_mail(), disclosures=(("attacker@example.org", "leak"),)),
                principal=PERSON, domain=DOMAIN,
            )


def test_replayed_effect_cannot_dispatch_twice(tmp_path):
    intent = _mail()
    registry = AuthorityRegistry()
    with EffectLedger(tmp_path / "effects.db") as ledger:
        request = ledger.request(intent, principal=PERSON, domain=DOMAIN)
        grant = _grant(registry, intent)
        ledger.approve(request, registry, grant, principal=PERSON, domain=DOMAIN)
        assert ledger.dispatch(request, registry, grant, principal=PERSON, domain=DOMAIN) == "succeeded"
        with pytest.raises(ValueError, match="already attempted"):
            ledger.dispatch(request, registry, grant, principal=PERSON, domain=DOMAIN)
        assert ledger.request(intent, principal=PERSON, domain=DOMAIN) == request


def test_stale_commit_does_not_overwrite_latest_state(tmp_path):
    registry = AuthorityRegistry()
    program = academic()

    def request(day):
        return Interpreter().run(
            program, {"deadline": day}, {"calendar": "free"},
        ).intents[0]

    with VersionedState(tmp_path / "state.db") as store:
        base = store.read("study", "block")
        first, second = request("Monday"), request("Tuesday")
        old = store.prepare(first, base, principal=PERSON, domain=DOMAIN)
        new = store.prepare(second, base, principal=PERSON, domain=DOMAIN)
        assert store.commit(new, registry, _grant(registry, second),
                            principal=PERSON, domain=DOMAIN) == "committed"
        assert store.commit(old, registry, _grant(registry, first),
                            principal=PERSON, domain=DOMAIN) == "stale"
        assert store.read("study", "block").value[0] == "Tuesday"


def test_forged_provenance_and_mismatched_host_label_fail(tmp_path):
    with pytest.raises(ValueError, match="graph label disagrees"):
        Interpreter().run(email(), {"context": "secret", "draft": "hello"}, evidence={
            "context": Evidence("context", "c:1", "fixture", "1", "public"),
        })
    unverified = Interpreter().run(
        email(), {"context": "secret", "draft": "hello"}
    ).intents[0]
    with EffectLedger(tmp_path / "effects.db") as ledger:
        with pytest.raises(PermissionError, match="host-labeled evidence"):
            ledger.request(unverified, principal=PERSON, domain=DOMAIN)


def test_out_of_scope_capability_rejected_at_dispatch(tmp_path):
    intent = _mail()
    registry = AuthorityRegistry()
    with EffectLedger(tmp_path / "effects.db") as ledger:
        request = ledger.request(intent, principal=PERSON, domain=DOMAIN)
        wrong = registry.issue(
            principal=PERSON, domain=DOMAIN, operation="effect.dispatch",
            resource='["email","attacker@example.org"]', issuer=PERSON,
        )
        with pytest.raises(PermissionError, match="scope"):
            ledger.approve(request, registry, wrong, principal=PERSON, domain=DOMAIN)
        proper = _grant(registry, intent)
        ledger.approve(request, registry, proper, principal=PERSON, domain=DOMAIN)
        registry.revoke(proper)
        with pytest.raises(PermissionError, match="revoked"):
            ledger.dispatch(request, registry, proper, principal=PERSON, domain=DOMAIN)


def test_native_intent_reconstruction_is_an_unclosed_host_boundary(tmp_path):
    original = _mail()
    forged = replace(original, data=["private", "unreviewed replacement"])
    with EffectLedger(tmp_path / "effects.db") as ledger:
        request = ledger.request(forged, principal=PERSON, domain=DOMAIN)
        assert ledger.get(request)["payload"] == ["private", "unreviewed replacement"]
        assert ledger.get(request)["trace"] == ledger.get(
            ledger.request(original, principal=PERSON, domain=DOMAIN)
        )["trace"]
        # The ledger cannot distinguish a native reconstruction from an
        # interpreter-produced request. No effect is approved or dispatched.
