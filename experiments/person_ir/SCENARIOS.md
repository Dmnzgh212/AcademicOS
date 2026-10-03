# Slice 6: heterogeneous scenario findings

Run `python -m pytest -q experiments/person_ir/tests/test_scenarios.py` from the
repository root. The five graphs are in `scenarios.py`; every effect uses the
SQLite fake executor. The fixtures are illustrative, not production policies.

| Scenario | Reused primitives and observed boundary | Remaining gap |
| --- | --- | --- |
| Academic study block | Deadline observation + calendar view -> proposal; a competing commit makes the older proposal stale. | The graph joins inputs; it cannot select a genuinely free time slot or prove the calendar observation is current. |
| Advisor email | Protected context and draft -> whole-value release to exact recipient -> approved fake email; duplicate request and dispatch do not send twice. | Host must validate recipient and reviewed message. Whole-value disclosure releases the joined context too. |
| Purchase | Order and observed price -> reviewed fake payment; revocation blocks dispatch. | An approved request can still carry an old price/order. There is no pre-dispatch price revalidation or payment-specific limit. Do not connect a real payment executor. |
| Thermostat | Sensor and policy -> reviewed fake device action; expiring grant blocks later dispatch. | Sensor age and policy version are not checked at dispatch; offline status needs a device-specific host policy. |
| Shared plan | Two participants' suggestions + shared view -> versioned proposal; principal mismatch fails. | Alice alone can commit a proposal containing Bob's input. There is no joint authority, shared ownership, merge rule or per-participant consent. |

**Decision gate:** All five examples fit the same data-only graph shape and
host-owned proposal/effect boundaries, but `join` only packages values. It does
not perform planning, price comparison, device control or merge. Three scenarios
demonstrate reusable plumbing, not a distinctive language benefit. Payment,
device and collaboration expose material domain-specific host obligations.
Do not promote this IR to a general compiler or real-world executor on this
evidence. The next slice is adversarial tests and a comparison against the
conventional capability-limited Wasm host.
