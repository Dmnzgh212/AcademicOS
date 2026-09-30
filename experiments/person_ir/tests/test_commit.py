import unittest
from dataclasses import replace
from datetime import datetime, timezone

from experiments.person_ir import (AuthorityError, AuthorityStore, Graph,
                                   Interpreter, InvalidProposal, Node, Observation,
                                   StaleProposal, StateStore)
from experiments.person_ir.model import CommitRequest


NOW = datetime(2026, 9, 29, 13, tzinfo=timezone.utc)
GRAPH = Graph((Node("source", "source", config={"name": "plan", "label": "protected"}),
               Node("suggestion", "propose", ("source",), {"target": "study_blocks"}),
               Node("request", "commit_request", ("suggestion",))))


def request(value, version, *, observation=None):
    evidence = observation or Observation(value, "course:deadline:1", "protected")
    return Interpreter().run(GRAPH, {"plan": evidence}, base_version=version,
                             producer="academic@0.1").commits[0]


class CommitTests(unittest.TestCase):
    def setUp(self):
        self.state = StateStore("personal:1", {"other": "untouched"})
        self.authority = AuthorityStore()
        self.handle = self.authority.issue(principal="person:1", domain="personal:1",
                                           agent="plugin:academic", operation="commit",
                                           resource="study_blocks", issuer="person:1",
                                           issued_at=NOW)

    def commit(self, value, version=0, *, handle=None, evidence=None):
        return self.state.commit(request(value, version, observation=evidence),
                                 self.authority, self.handle if handle is None else handle,
                                 principal="person:1", agent="plugin:academic", now=NOW)

    def test_valid_commit_updates_only_target_and_replay_does_not_reapply(self):
        initial = self.state.snapshot()
        first = self.commit(["CSI 2110", "Thursday 18:00"])
        self.assertTrue(first.receipt.applied)
        self.assertEqual(first.receipt.old_version, 0)
        self.assertEqual(first.receipt.new_version, 1)
        self.assertEqual(initial.values, {"other": "untouched"})
        self.assertEqual(self.state.snapshot().values,
                         {"other": "untouched", "study_blocks": ["CSI 2110", "Thursday 18:00"]})
        replay = self.commit(["CSI 2110", "Thursday 18:00"])
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.receipt, first.receipt)
        self.assertEqual(self.state.snapshot().version, 1)

    def test_stale_and_unauthorized_do_not_change_state_or_evidence(self):
        raw = {"course": "CSI 2110"}
        evidence = Observation(raw, "course:deadline:1", "protected")
        self.commit({"course": "CSI 2110"}, evidence=evidence)
        before = self.state.snapshot()
        with self.assertRaises(StaleProposal):
            self.commit({"course": "MAT 2322"}, version=0)
        self.authority.revoke(self.authority.describe(self.handle).capability_id)
        with self.assertRaises(AuthorityError):
            self.commit({"course": "MAT 2322"}, version=1)
        self.assertEqual(self.state.snapshot(), before)
        self.assertEqual(raw, {"course": "CSI 2110"})
        self.assertEqual(evidence.value, raw)

    def test_replay_needs_live_authority(self):
        self.commit("plan")
        self.authority.revoke(self.authority.describe(self.handle).capability_id)
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            self.commit("plan")
        self.assertEqual(self.state.snapshot().version, 1)

    def test_tampered_proposal_is_rejected(self):
        original = request("plan", 0)
        changed = CommitRequest(replace(original.proposal, value="different"))
        with self.assertRaises(InvalidProposal):
            self.state.commit(changed, self.authority, self.handle,
                              principal="person:1", agent="plugin:academic", now=NOW)
        self.assertEqual(self.state.snapshot().version, 0)

    def test_no_op_does_not_bump_version(self):
        self.commit("plan")
        no_op = self.commit("plan", version=1)
        self.assertFalse(no_op.receipt.applied)
        self.assertFalse(no_op.replayed)
        self.assertEqual(self.state.snapshot().version, 1)

    def test_wrong_domain_grant_fails(self):
        other = self.authority.issue(principal="person:1", domain="personal:2",
                                     agent="plugin:academic", operation="commit",
                                     resource="study_blocks", issuer="person:1", issued_at=NOW)
        with self.assertRaises(AuthorityError):
            self.commit("plan", handle=other)
        self.assertEqual(self.state.snapshot().version, 0)


if __name__ == "__main__":
    unittest.main()
