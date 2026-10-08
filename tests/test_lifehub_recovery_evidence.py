import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "recovery_evidence_check", Path(__file__).resolve().parents[1] / "scripts/check_lifehub_recovery_evidence.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.fixture
def bundle(tmp_path):
    (tmp_path / "packages").mkdir()
    packages = {}
    for name in ("provider.lhpkg", "consumer.lhpkg"):
        path = tmp_path / "packages" / name
        path.write_bytes(b"synthetic fixture, not a real integration")
        packages[name] = checker.digest(path)
    for name in ("engine.log", "proof.log", "fixture.whl"):
        (tmp_path / name).write_bytes(b"synthetic fixture")
    evidence = {"status": "PASS", "git_sha": "a" * 40, "platform": "linux", "python": "3.12",
                "elapsed_seconds": 1.0, "execution_ids": ["initial", "recovered", "restored"],
                "old_guest_exited_by_replacement_ready": True, "packages": packages}
    (tmp_path / "evidence.json").write_text(json.dumps(evidence))
    return tmp_path


def check(root):
    return checker.check(root, root / "fixture.whl", root / "proof.log", "a" * 40)


def test_complete_fixture_does_not_claim_authorship(bundle):
    result = check(bundle)
    assert result["status"] == "PASS" and result["independent_authorship_verified"] is False
    assert result["M1_accepted"] is False


def test_wheel_only_artifact_is_not_evidence(tmp_path):
    (tmp_path / "fixture.whl").write_bytes(b"wheel only")
    with pytest.raises(FileNotFoundError):
        check(tmp_path)


@pytest.mark.parametrize("field,value", [("status", "NOT COMPLETED"), ("git_sha", "b" * 40),
                                          ("execution_ids", ["same"] * 3)])
def test_incomplete_or_mismatched_metadata_fails(bundle, field, value):
    path = bundle / "evidence.json"
    metadata = json.loads(path.read_text())
    metadata[field] = value
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        check(bundle)


def test_package_tampering_fails(bundle):
    (bundle / "packages" / "provider.lhpkg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest mismatch"):
        check(bundle)
