"""Check retained proof completeness/integrity, not independent authorship or truth."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root, wheel, proof_log, expected_sha):
    evidence_path = root / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if evidence.get("status") != "PASS":
        raise ValueError("recovery run is not complete")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise ValueError("expected checkout SHA must be explicit")
    if evidence.get("git_sha") != expected_sha:
        raise ValueError("checkout identity mismatch")
    if evidence.get("platform") not in {"linux", "win32"} or not evidence.get("python"):
        raise ValueError("missing supported platform/Python evidence")
    elapsed = evidence.get("elapsed_seconds")
    if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed <= 0:
        raise ValueError("invalid elapsed time")
    ids = evidence.get("execution_ids", [])
    if len(ids) != 3 or not all(isinstance(x, str) and x for x in ids) or len(set(ids)) != 3:
        raise ValueError("missing distinct initial/recovered/restored execution identities")
    if evidence.get("old_guest_exited_by_replacement_ready") is not True:
        raise ValueError("old-worker exit observation missing")
    packages = evidence.get("packages")
    if not isinstance(packages, dict) or len(packages) < 2:
        raise ValueError("missing package identities")
    for name, expected in packages.items():
        if not isinstance(name, str) or "/" in name or "\\" in name or not name.endswith(".lhpkg"):
            raise ValueError("invalid package filename")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("invalid package digest")
        if digest(root / "packages" / name) != expected:
            raise ValueError("package digest mismatch")
    if {p.name for p in (root / "packages").glob("*.lhpkg")} != set(packages):
        raise ValueError("package inventory mismatch")
    for path in (root / "engine.log", proof_log, wheel):
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("missing or empty log/wheel")
    if wheel.suffix != ".whl":
        raise ValueError("wheel artifact required")
    return {"status": "PASS", "scope": "retained file completeness and digest checks only",
            "checkout_sha": expected_sha, "wheel_sha256": digest(wheel),
            "evidence_sha256": digest(evidence_path), "packages": packages,
            "independent_authorship_verified": False, "M1_accepted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("proof_log", type=Path)
    parser.add_argument("expected_sha")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = check(args.root, args.wheel, args.proof_log, args.expected_sha)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("PASS: retained recovery files and package digests")
