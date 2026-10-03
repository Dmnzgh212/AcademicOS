from __future__ import annotations

import pytest

from experiments.person_ir import Interpreter, Node, Program, VerificationError, verify


def test_academic_graph_returns_proposal_and_commit_request_without_mutation() -> None:
    program = Program(
        "academic",
        (
            Node("deadline", "observe", parameters={"source": "course", "label": "public"}),
            Node("date", "transform", ("deadline",), {"op": "get", "key": "due"}),
            Node("calendar", "state_view", parameters={"source": "calendar", "label": "protected"}),
            Node("plan", "join", ("date", "calendar")),
            Node("derived", "derive", ("plan",)),
            Node("proposal", "propose", ("derived",), {"namespace": "study", "key": "plan"}),
            Node("commit", "commit_request", ("proposal",)),
            Node("show", "output", ("derived",)),
        ),
    )
    observed = {"course": {"due": "Friday"}}
    state = {"calendar": ["Thursday 16:00"]}
    result = Interpreter().run(program, observed, state)
    assert [item.kind for item in result.intents] == ["commit_request", "output"]
    assert result.intents[0].parameters == {"namespace": "study", "key": "plan"}
    assert result.intents[0].data == ["Friday", ["Thursday 16:00"]]
    assert result.intents[0].label == "protected"
    assert result.intents[0].sources == {"course", "calendar"}
    result.values["calendar"].data.append("tamper")
    assert state == {"calendar": ["Thursday 16:00"]}
    assert observed == {"course": {"due": "Friday"}}


def test_effect_is_only_a_request_and_protected_input_needs_disclosure() -> None:
    base = (Node("draft", "observe", parameters={"source": "draft", "label": "protected"}),)
    effect = Node(
        "send",
        "effect_request",
        ("draft",),
        {"kind": "email", "destination": "recipient@example.org", "purpose": "Send draft"},
    )
    with pytest.raises(ValueError, match="matching disclosure"):
        Interpreter().run(Program("email", base + (effect,)), {"draft": {"text": "hello"}})
    disclosed = Node(
        "disclosed",
        "declassify",
        ("draft",),
        {"destination": "recipient@example.org", "scope": "whole_value", "purpose": "Send draft"},
    )
    program = Program(
        "email",
        base + (disclosed, Node("send", "effect_request", ("disclosed",), effect.parameters)),
    )
    result = Interpreter().run(program, {"draft": {"text": "hello"}})
    assert result.intents[0].kind == "effect_request"
    assert result.intents[0].disclosures == (("recipient@example.org", "Send draft"),)
    assert result.intents[0].data == {"text": "hello"}


@pytest.mark.parametrize(
    "nodes,reason",
    [
        ((Node("x", "python", parameters={}), Node("end", "output", ("x",))), "unknown node"),
        ((Node("end", "output", ("later",)), Node("later", "derive", ("end",))), "earlier value"),
        (
            (Node("x", "observe", parameters={"source": "s", "label": "public", "callback": "x"}),),
            "wrong parameters",
        ),
        (
            (
                Node("x", "observe", parameters={"source": "s", "label": "public"}),
                Node("x", "output", ("x",)),
            ),
            "unique",
        ),
        (
            (
                Node("x", "observe", parameters={"source": "s", "label": "public"}),
                Node("bad", "commit_request", ("x",)),
            ),
            "reference a proposal",
        ),
    ],
)
def test_verifier_rejects_invalid_graph(nodes, reason) -> None:
    with pytest.raises(VerificationError, match=reason):
        verify(Program("invalid", nodes))


def test_ambient_objects_cannot_cross_host_input_boundary() -> None:
    program = Program(
        "blocked",
        (
            Node("x", "observe", parameters={"source": "s", "label": "public"}),
            Node("end", "output", ("x",)),
        ),
    )
    with pytest.raises(TypeError):
        Interpreter().run(program, {"s": lambda: None})


def test_disclosing_one_join_input_does_not_release_another() -> None:
    program = Program(
        "partial-disclosure",
        (
            Node("a", "observe", parameters={"source": "a", "label": "protected"}),
            Node("b", "observe", parameters={"source": "b", "label": "protected"}),
            Node(
                "released_a",
                "declassify",
                ("a",),
                {
                    "destination": "recipient@example.org",
                    "scope": "whole_value",
                    "purpose": "Send a",
                },
            ),
            Node("combined", "join", ("released_a", "b")),
            Node(
                "send",
                "effect_request",
                ("combined",),
                {"kind": "email", "destination": "recipient@example.org", "purpose": "Send both"},
            ),
        ),
    )
    with pytest.raises(ValueError, match="matching disclosure"):
        Interpreter().run(program, {"a": "A", "b": "B"})
