"""Trusted Python handoff for two programs using one generic core-WASM ABI."""

import json
from pathlib import Path
import subprocess

from .baseline import (ComponentSession, Manifest, academic_component,
                       email_component)
from .model import Observation
from .package import PackageManifest
from .runtime import _json_value
from .wasm_bridge import WasmRequestRejected


def request_from_generic_wasm(program: str, manifest: PackageManifest,
                              observations: dict[str, Observation], *,
                              destination: str | None = None,
                              base_version: int = 0, intent_id: str = "default",
                              mutation: dict | None = None):
    """Validate one isolated description and create a conventional host request.

    This bridge still knows the two examples' payload shapes. Its validation
    work is evidence against assuming a generic WIT interface solves binding.
    """
    if not isinstance(manifest, PackageManifest) or type(observations) is not dict:
        raise TypeError("host-approved manifest and observation map required")
    if program == "academic":
        names, fields, target, kind = ("deadline", "availability"), ("course", "free_slot"), "study_blocks", None
        if target not in manifest.commit_targets:
            raise WasmRequestRejected("commit target not declared")
    elif program == "email":
        names, fields, target, kind = ("context", "draft", "recipient"), (), None, "email"
        if type(destination) is not str or not destination.strip():
            raise ValueError("destination required")
        if (kind, destination) not in manifest.effect_scopes:
            raise WasmRequestRejected("effect scope not declared")
    else:
        raise ValueError("unsupported generic WASM program")
    if not set(names).issubset(manifest.sources):
        raise WasmRequestRejected("source not declared")
    snapshots = {}
    for name in names:
        item = observations[name]
        if (not isinstance(item, Observation) or item.label not in {"public", "protected"} or
                type(item.source) is not str or not item.source.strip()):
            raise WasmRequestRejected("invalid host observation")
        snapshots[name] = Observation(_json_value(item.value), item.source, item.label,
                                      item.execution_id, item.engine)
    protected = any(item.label == "protected" for item in snapshots.values())
    purpose = "send requested email" if kind and protected else None
    if purpose and (destination, purpose) not in manifest.disclosures:
        raise WasmRequestRejected("disclosure not declared")
    config = {
        "sourceNames": [*names, "secret"], "fieldNames": fields,
        "targetNames": [target] if target else [], "effectNames": [kind] if kind else [],
        "destination": destination or "", "disclosurePurpose": purpose,
        "destinationPath": [1] if kind else None,
        "manifest": {"sources": sorted(manifest.sources),
                     "commit_targets": sorted(manifest.commit_targets),
                     "effect_scopes": sorted([list(scope) for scope in manifest.effect_scopes]),
                     "disclosures": sorted([list(scope) for scope in manifest.disclosures])},
        "observations": {name: {"value": item.value, "source": item.source,
                                "label": item.label}
                         for name, item in snapshots.items()},
    }
    encoded = json.dumps({"program": program, "config": config,
                          "mutation": mutation or {}}, allow_nan=False)
    if len(encoded.encode("utf-8")) > 1_000_000:
        raise WasmRequestRejected("oversized WASM host input")
    try:
        result = subprocess.run(
            ["node", str(Path(__file__).with_name("wasm_generic.mjs")), "--json"],
            input=encoded, text=True, capture_output=True, timeout=5, check=True)
        if len(result.stdout) > 1_000_000:
            raise WasmRequestRejected("oversized WASM host response")
        response = json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise WasmRequestRejected("generic WASM host failed") from exc
    if type(response) is not dict or response.get("ok") is not True:
        raise WasmRequestRejected("generic WASM request rejected")
    session = ComponentSession(
        Manifest(manifest.producer, manifest.sources, manifest.commit_targets,
                 manifest.effect_scopes), snapshots, base_version=base_version,
        intent_id=intent_id)
    if program == "academic":
        request = academic_component(session)
        expected = {"target": target, "value": request.proposal.value,
                    "sources": [snapshots[name].source for name in names],
                    "label": "protected" if protected else "public"}
    else:
        request = email_component(session, destination)
        expected = {"kind": kind, "destination": destination,
                    "payload": request.payload,
                    "label": "protected" if protected else "public",
                    "disclosure_purpose": purpose,
                    "sources": [snapshots[name].source for name in names]}
    if response.get("request") != expected:
        raise WasmRequestRejected("generic WASM request differs from host observations")
    return request
