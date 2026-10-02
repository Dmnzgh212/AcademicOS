from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from experiments.person_ir import (
    AuthorityRegistry,
    Capability,
    Interpreter,
    Node,
    Program,
    VerificationError,
)


def _intent(kind: str):
    source = Node("source", "observe", parameters={"source": "input", "label": "public"})
    if kind == "commit":
        tail = (
            Node("proposal", "propose", ("source",), {"namespace": "tasks", "key": "today"}),
            Node("request", "commit_request", ("proposal",)),
        )
    else:
        tail = (
            Node(
                "request",
                "effect_request",
                ("source",),
                {
                    "kind": "email",
                    "destination": "friend@example.org",
                    "purpose": "Share a note",
                },
            ),
        )
    return Interpreter().run(Program(kind, (source,) + tail), {"input": {"text": "hi"}}).intents[0]


def _registry(now):
    return AuthorityRegistry(clock=lambda: now[0])


def test_serialized_or_reconstructed_capability_cannot_authorize() -> None:
    now = [datetime(2026, 10, 2, tzinfo=UTC)]
    registry = _registry(now)
    handle = registry.issue_for_intent(
        _intent("commit"), principal="person:george", domain="personal", issuer="person:george"
    )
    info = registry.inspect(handle)
    assert info.scope == "exact" and info.revoked is False
    assert (
        registry.require_intent(
            handle, _intent("commit"), principal="person:george", domain="personal"
        )
        == info
    )
    serialized = json.loads(json.dumps({"capability_id": info.capability_id}))
    with pytest.raises(PermissionError, match="handle required"):
        registry.require_intent(
            serialized, _intent("commit"), principal="person:george", domain="personal"
        )
    with pytest.raises(PermissionError, match="not issued"):
        registry.require_intent(
            Capability(serialized["capability_id"]),
            _intent("commit"),
            principal="person:george",
            domain="personal",
        )
    with pytest.raises(TypeError):
        Interpreter().run(
            Program(
                "data",
                (
                    Node("source", "observe", parameters={"source": "input", "label": "public"}),
                    Node("out", "output", ("source",)),
                ),
            ),
            {"input": handle},
        )
    with pytest.raises(VerificationError, match="unknown node"):
        Interpreter().run(Program("forge", (Node("mint", "issue_capability"),)), {})


def test_revocation_and_expiry_are_checked_at_use_time() -> None:
    now = [datetime(2026, 10, 2, tzinfo=UTC)]
    registry = _registry(now)
    kwargs = dict(
        principal="person:george",
        domain="personal",
        operation="state.commit",
        resource='["tasks","today"]',
        issuer="person:george",
    )
    handle = registry.issue(**kwargs)
    request = _intent("commit")
    registry.require_intent(handle, request, principal="person:george", domain="personal")
    registry.revoke(handle)
    assert registry.inspect(handle).revoked is True
    with pytest.raises(PermissionError, match="revoked or expired"):
        registry.require_intent(handle, request, principal="person:george", domain="personal")
    expiring = registry.issue(**kwargs, expires_at=now[0] + timedelta(minutes=1))
    now[0] += timedelta(minutes=1)
    with pytest.raises(PermissionError, match="revoked or expired"):
        registry.require_intent(expiring, request, principal="person:george", domain="personal")


def test_scope_principal_domain_context_and_operation_are_distinct() -> None:
    now = [datetime(2026, 10, 2, tzinfo=UTC)]
    registry = _registry(now)
    read = registry.issue(
        principal="person:george",
        domain="personal",
        operation="state.read",
        resource='["tasks","today"]',
        issuer="person:george",
    )
    with pytest.raises(PermissionError, match="scope"):
        registry.require_intent(
            read, _intent("effect"), principal="person:george", domain="personal"
        )
    write = registry.issue(
        principal="person:george",
        domain="personal",
        operation="state.commit",
        resource='["tasks","today"]',
        issuer="person:george",
        activation_context="review:home",
    )
    request = _intent("commit")
    for principal, domain, resource, context in (
        ("person:other", "personal", '["tasks","today"]', "review:home"),
        ("person:george", "shared", '["tasks","today"]', "review:home"),
        ("person:george", "personal", '["tasks","tomorrow"]', "review:home"),
        ("person:george", "personal", '["tasks","today"]', "review:other"),
    ):
        with pytest.raises(PermissionError, match="scope"):
            registry.require(
                write,
                principal=principal,
                domain=domain,
                operation="state.commit",
                resource=resource,
                context=context,
            )
    assert (
        registry.require_intent(
            write, request, principal="person:george", domain="personal", context="review:home"
        ).issuer
        == "person:george"
    )


def test_other_registry_and_invalid_dates_fail_closed() -> None:
    now = [datetime(2026, 10, 2, tzinfo=UTC)]
    a, b = _registry(now), _registry(now)
    handle = a.issue(principal="p", domain="d", operation="state.read", resource="r", issuer="p")
    with pytest.raises(PermissionError, match="not issued"):
        b.inspect(handle)
    with pytest.raises(ValueError, match="timezone-aware"):
        a.issue(
            principal="p",
            domain="d",
            operation="state.read",
            resource="r",
            issuer="p",
            expires_at=datetime(2027, 1, 1),
        )
