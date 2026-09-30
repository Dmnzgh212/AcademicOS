import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone

from experiments.person_ir import AuthorityStore, Interpreter, Observation
from experiments.person_ir.durable import DurableEffectJournal, DurableStateStore
from experiments.person_ir.examples import academic


ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 9, 29, tzinfo=timezone.utc)


class CoreWasmBaselineTests(unittest.TestCase):
    def run_case(self, name):
        result = subprocess.run(["node", "experiments/person_ir/wasm_baseline.mjs", name],
                                cwd=ROOT, text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_isolated_academic_and_host_denials(self):
        self.assertEqual(self.run_case("academic")["proposal"]["value"], [2110, 4])
        self.assertIn("source not declared", self.run_case("undeclared")["error"])
        self.assertIn("commit target not declared", self.run_case("no_commit")["error"])


class RecoveryTests(unittest.TestCase):
    def test_version_receipt_and_replay_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "host.sqlite")
            observations = {
                "deadline": Observation({"course": "CSI 2110"}, "course:1", "protected"),
                "availability": Observation({"free_slot": "Thursday"}, "calendar:1", "protected"),
            }
            request = Interpreter().run(academic.GRAPH, observations, base_version=0,
                                        producer="academic@1").commits[0]
            authority = AuthorityStore()
            handle = authority.issue(principal="person:1", domain="personal:1",
                                     agent="academic@1", operation="commit",
                                     resource="study_blocks", issuer="person:1", issued_at=NOW)
            store = DurableStateStore(path, "personal:1")
            original = store.commit(request, authority, handle, principal="person:1",
                                    agent="academic@1", now=NOW)
            store.close()
            store = DurableStateStore(path, "personal:1")
            self.assertEqual(store.snapshot().version, 1)
            self.assertEqual(store.snapshot().values["study_blocks"], ["CSI 2110", "Thursday"])
            replay = store.commit(request, authority, handle, principal="person:1",
                                  agent="academic@1", now=NOW)
            self.assertTrue(replay.replayed)
            self.assertEqual(replay.receipt, original.receipt)
            store.close()

    def test_pending_intent_is_unknown_and_never_reexecuted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "host.sqlite")
            journal = DurableEffectJournal(path)
            self.assertTrue(journal.begin("personal:1", "effect:1"))
            journal.close()  # Simulate restart between intent and external acknowledgement.
            journal = DurableEffectJournal(path)
            self.assertEqual(journal.lookup("personal:1", "effect:1"), ("unknown", None))
            self.assertFalse(journal.begin("personal:1", "effect:1"))
            journal.finish("personal:1", "effect:1",
                           {"status": "succeeded", "external_ref": "reconciled:1"})
            self.assertEqual(journal.lookup("personal:1", "effect:1")[0], "succeeded")
            with self.assertRaises(ValueError):
                journal.finish("personal:1", "effect:1", {"status": "failed"})
            journal.close()


if __name__ == "__main__":
    unittest.main()
