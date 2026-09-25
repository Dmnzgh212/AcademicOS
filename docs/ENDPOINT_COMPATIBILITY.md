# Endpoint Compatibility Learning

AcademicOS runs against institution-managed Brightspace environments where endpoint availability can vary by tenant, course, role, and API version.

The collector therefore treats compatibility as learned local state rather than assuming every documented Brightspace endpoint is available everywhere.

## Storage

Schema v5 adds `endpoint_capabilities`.

Each row is keyed by:

```text
source_key + endpoint
```

For Brightspace course-level collection the source key is:

```text
brightspace:<org_unit_id>
```

The table stores only compatibility diagnostics:

- status;
- HTTP status when known;
- last probe time;
- next allowed probe time;
- a value-free response-shape summary;
- a bounded error summary.

It does **not** store tokens, cookies, email addresses, course text, grades, or response values.

## Status policy

### supported

A successful request clears previous cooldown state. Supported endpoints continue to be collected normally.

### unsupported

HTTP `404` or `405` is treated as a strong signal that the endpoint is unavailable for that course/tenant/API combination.

Default re-probe interval: **30 days**.

### forbidden

HTTP `403` may reflect course- or role-specific permissions rather than permanent platform incompatibility.

Default re-probe interval: **12 hours**.

### auth_error

HTTP `401` is treated as an authentication/session problem, not an endpoint-capability problem.

It is **not** cooled down so authentication repair can take effect immediately.

### transient

HTTP `429`, `502`, `503`, and `504` represent throttling or temporary service failure.

Default re-probe interval: **10 minutes**.

The underlying HTTP clients also perform bounded retries where appropriate.

### error

Other failures receive a conservative **1 hour** cooldown so a broken optional endpoint does not generate the same error every scheduled sync while still being retried reasonably soon.

## Collector behavior

`sync_all()` uses the capability-aware Brightspace wrapper.

Before a course sync:

```text
requested datasets
       ↓
endpoint_capabilities
       ↓
remove endpoints still in cooldown
       ↓
normal Brightspace collector
```

After the request:

```text
success → supported
HTTP failure → classified cooldown
```

Only top-level course endpoints are capability-cached. Nested resources such as individual assignment submissions, quiz attempts, content modules, and discussion posts remain isolated item-by-item because availability can differ within the same course.

## Live doctor integration

`academicos-doctor --live` probes a small read-only sample course and records structural capability results for:

- announcements/news;
- assignments;
- quizzes;
- content TOC;
- grades;
- calendar;
- updates.

The doctor stores only response structure, for example:

```json
{
  "kind": "list",
  "count": 4,
  "item_keys": ["Id", "Name", "DueDate"]
}
```

Actual values are intentionally excluded.

## Inspecting the learned matrix

```powershell
academicos-capabilities
```

To produce a sanitized JSON file that can be shared for debugging:

```powershell
academicos-capabilities --json-out data/audits/capabilities.json
```

## Why this exists

Without compatibility memory, a scheduled collector can repeatedly hit the same known-disabled endpoint every 30 minutes, creating noise, slowing sync, and making source-health reports look worse than the actual useful data coverage.

AcademicOS instead learns the local Brightspace surface while periodically re-probing so temporary permissions and platform upgrades can recover automatically.
