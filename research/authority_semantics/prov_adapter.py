"""Isolated upstream PROV serializer adapter; never an authorization importer."""
import json
import sys
from importlib.metadata import version
from pathlib import Path

from prov.model import ProvDocument


KINDS = {"evidence", "derived", "proposal"}


def export_records(records):
    """Accept trusted synthetic host records, not guest-provided provenance."""
    doc = ProvDocument()
    doc.add_namespace("lh", "urn:lifehub:research:")
    for key, record in records.items():
        if record["kind"] not in KINDS:
            raise ValueError("unsupported record kind")
        doc.entity(f"lh:{key}", {"lh:kind": record["kind"],
                               "lh:status": record.get("status", "recorded")})
        for owner in record["owners"]:
            doc.agent(f"lh:person_{owner}")
            # Attribution expresses an assertion, not ownership/permission proof.
            doc.wasAttributedTo(f"lh:{key}", f"lh:person_{owner}")
    for key, record in records.items():
        for source in record["inputs"]:
            if source not in records:
                raise ValueError("dangling source")
            doc.wasDerivedFrom(f"lh:{key}", f"lh:{source}")
    return doc


def run(output):
    assert version("prov") == "3.1.0"
    source = json.loads(Path(__file__).with_name("results.json").read_text())
    cases = []
    for case in source["cases"]:
        left = export_records(case["B1"]["records"])
        right = export_records(case["R_graph"]["records"])
        assert left == right
        wire = left.serialize(format="json")
        restored = ProvDocument.deserialize(content=wire, format="json")
        assert restored == left
        cases.append({"name": case["name"], "roundtrip": True,
                      "frontend_documents_equal": True,
                      "document": json.loads(wire)})
    for malformed in (
        {"x": {"kind": "authority", "owners": [], "inputs": []}},
        {"x": {"kind": "derived", "owners": [], "inputs": ["missing"]}},
    ):
        try:
            export_records(malformed)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed host record accepted")
    # The upstream library accepts an untrusted attribution assertion. This
    # adapter intentionally offers no import-to-grant/host-state operation.
    forged = ProvDocument()
    forged.add_namespace("lh", "urn:lifehub:research:")
    forged.entity("lh:private")
    forged.agent("lh:attacker")
    forged.wasAttributedTo("lh:private", "lh:attacker")
    assert ProvDocument.deserialize(content=forged.serialize(format="json"),
                                    format="json") == forged
    result = {"upstream": "prov", "version": version("prov"),
              "scope": "trusted synthetic records to PROV-JSON; not Engine integration",
              "authorization_enforced_by_PROV": False,
              "guest_attribution_assertion_is_serializable": True,
              "import_to_authority_supported": False,
              "unsupported_kind_and_dangling_source_rejected": True,
              "cases": cases}
    Path(output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"PASS: {len(cases)} upstream roundtrips and two adapter failure cases")


if __name__ == "__main__":
    run(sys.argv[1])
