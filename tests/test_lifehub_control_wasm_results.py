"""Control-plane results expose only built-in bounded Wasm integers."""
from __future__ import annotations

import pytest

from academicos.lifehub.control import _execution_json
from academicos.lifehub.engine import ExecutionState, ExecutionView


def view(runner: str, state: ExecutionState, result):
    return ExecutionView(
        execution_id="synthetic",
        component_ref="thirdparty.checkout:calculate",
        runner_id=runner,
        state=state,
        started_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        result=result,
    )


def test_completed_wasm_i32_is_visible_to_independent_clients():
    response = _execution_json(view("lifehub.wasm", ExecutionState.COMPLETED, 21))
    assert response["result"] == 21
    assert response["state"] == "completed"


@pytest.mark.parametrize(
    ("runner", "state", "result"),
    [
        ("trusted.python", ExecutionState.COMPLETED, {"secret": "opaque"}),
        ("trusted.python", ExecutionState.COMPLETED, 21),
        ("lifehub.wasm", ExecutionState.RUNNING, 21),
        ("lifehub.wasm", ExecutionState.COMPLETED, {"secret": "opaque"}),
        ("lifehub.wasm", ExecutionState.COMPLETED, True),
        ("lifehub.wasm", ExecutionState.COMPLETED, 2**31),
        ("lifehub.wasm", ExecutionState.COMPLETED, -(2**31) - 1),
    ],
)
def test_control_does_not_expose_arbitrary_runner_data(runner, state, result):
    response = _execution_json(view(runner, state, result))
    assert "result" not in response
