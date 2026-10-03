"""Five representative graphs; all external actions remain fake host effects."""

from __future__ import annotations

from .model import Node, Program


def academic() -> Program:
    return Program("academic-study-block", (
        Node("deadline", "observe", parameters={"source": "deadline", "label": "public"}),
        Node("calendar", "state_view", parameters={"source": "calendar", "label": "protected"}),
        Node("block", "join", ("deadline", "calendar")),
        Node("proposal", "propose", ("block",), {"namespace": "study", "key": "block"}),
        Node("commit", "commit_request", ("proposal",)),
    ), version="1")


def email() -> Program:
    destination = "advisor@example.org"
    purpose = "Send reviewed academic draft"
    return Program("email-advisor", (
        Node("context", "observe", parameters={"source": "context", "label": "protected"}),
        Node("draft", "observe", parameters={"source": "draft", "label": "protected"}),
        Node("message", "join", ("context", "draft")),
        Node("release", "declassify", ("message",), {
            "destination": destination, "scope": "whole_value", "purpose": purpose,
        }),
        Node("send", "effect_request", ("release",), {
            "kind": "email", "destination": destination, "purpose": purpose,
        }),
    ), version="1")


def purchase() -> Program:
    destination = "fake-payment-gateway"
    purpose = "Purchase reviewed order"
    return Program("purchase-order", (
        Node("order", "observe", parameters={"source": "order", "label": "protected"}),
        Node("price", "observe", parameters={"source": "price", "label": "public"}),
        Node("payload", "join", ("order", "price")),
        Node("release", "declassify", ("payload",), {
            "destination": destination, "scope": "whole_value", "purpose": purpose,
        }),
        Node("pay", "effect_request", ("release",), {
            "kind": "payment", "destination": destination, "purpose": purpose,
        }),
    ), version="1")


def device() -> Program:
    return Program("device-temperature", (
        Node("sensor", "observe", parameters={"source": "sensor", "label": "public"}),
        Node("policy", "state_view", parameters={"source": "policy", "label": "protected"}),
        Node("command", "join", ("sensor", "policy")),
        Node("release", "declassify", ("command",), {
            "destination": "fake-thermostat", "scope": "whole_value",
            "purpose": "Apply reviewed thermostat command",
        }),
        Node("apply", "effect_request", ("release",), {
            "kind": "device", "destination": "fake-thermostat",
            "purpose": "Apply reviewed thermostat command",
        }),
    ), version="1")


def collaboration() -> Program:
    return Program("shared-plan", (
        Node("alice", "observe", parameters={"source": "alice", "label": "protected"}),
        Node("bob", "observe", parameters={"source": "bob", "label": "protected"}),
        Node("shared", "state_view", parameters={"source": "shared", "label": "protected"}),
        Node("suggestions", "join", ("alice", "bob")),
        Node("merged", "join", ("suggestions", "shared")),
        Node("proposal", "propose", ("merged",), {
            "namespace": "team", "key": "plan",
        }),
        Node("commit", "commit_request", ("proposal",)),
    ), version="1")
