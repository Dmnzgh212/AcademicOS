"""Trusted Python host bridge for the isolated core-WASM email probe."""

import json
from pathlib import Path
import subprocess

from .baseline import ComponentSession, Manifest
from .model import Observation
from .package import PackageManifest
from .runtime import _json_value


class WasmRequestRejected(ValueError):
    pass


def _materialize_email(description: dict, manifest: PackageManifest,
                       observations: dict[str, Observation], destination: str,
                       intent_id: str):
    """Validate the subprocess response against host input before making a request."""
    required = ("context", "draft", "recipient")
    session = ComponentSession(
        Manifest(manifest.producer, manifest.sources, manifest.commit_targets,
                 manifest.effect_scopes), observations, base_version=0,
        intent_id=intent_id)
    values = [session.read(name) for name in required]
    expected_payload = [[values[0], values[1]], values[2]]
    protected = any(observations[name].label == "protected" for name in required)
    purpose = "send requested email" if protected else None
    expected = {
        "kind": "email", "destination": destination, "payload": expected_payload,
        "label": "protected" if protected else "public",
        "disclosure_purpose": purpose,
        "sources": [observations[name].source for name in required],
    }
    if type(description) is not dict or description != expected:
        raise WasmRequestRejected("WASM request differs from host observations or scope")
    if values[2] != destination:
        raise WasmRequestRejected("recipient and destination differ")
    if protected and (destination, purpose) not in manifest.disclosures:
        raise WasmRequestRejected("disclosure not declared")
    return session.effect("email", destination, description["payload"],
                          disclosure_purpose=purpose)


def email_request_from_wasm(manifest: PackageManifest,
                            observations: dict[str, Observation], destination: str,
                            *, intent_id: str = "default"):
    """Run the WASM module with approved inputs; grants remain in the Python host."""
    if not isinstance(manifest, PackageManifest):
        raise TypeError("host-approved manifest required")
    if type(destination) is not str or not destination.strip():
        raise ValueError("destination required")
    if type(observations) is not dict:
        raise TypeError("host observation map required")
    required = ("context", "draft", "recipient")
    if any(name not in manifest.sources for name in required):
        raise WasmRequestRejected("source not declared")
    if ("email", destination) not in manifest.effect_scopes:
        raise WasmRequestRejected("effect scope not declared")
    selected = {}
    snapshots = {}
    for name in required:
        item = observations[name]
        if (not isinstance(item, Observation) or item.label not in {"public", "protected"} or
                type(item.source) is not str or not item.source.strip()):
            raise WasmRequestRejected("invalid host observation")
        value = _json_value(item.value)
        snapshots[name] = Observation(value, item.source, item.label,
                                      item.execution_id, item.engine)
        selected[name] = {"value": value, "source": item.source, "label": item.label}
    payload = {
        "manifest": {
            "sources": sorted(manifest.sources),
            "effect_scopes": sorted([list(scope) for scope in manifest.effect_scopes]),
            "disclosures": sorted([list(scope) for scope in manifest.disclosures]),
        },
        "observations": selected,
        "destination": destination,
    }
    encoded = json.dumps(payload, allow_nan=False)
    if len(encoded.encode("utf-8")) > 1_000_000:
        raise WasmRequestRejected("oversized WASM host input")
    try:
        result = subprocess.run(
            ["node", str(Path(__file__).with_name("wasm_email.mjs")), "--json"],
            input=encoded, text=True, capture_output=True,
            timeout=5, check=True)
        if len(result.stdout) > 1_000_000:
            raise WasmRequestRejected("oversized WASM host response")
        response = json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise WasmRequestRejected("isolated component host failed") from exc
    if type(response) is not dict:
        raise WasmRequestRejected("invalid isolated component host response")
    if response.get("ok") is not True:
        raise WasmRequestRejected(f"isolated component rejected request: {response.get('error')}")
    return _materialize_email(response.get("request"), manifest, snapshots,
                              destination, intent_id)
