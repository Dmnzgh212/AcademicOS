import unittest
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from experiments.person_ir import AuthorityError, AuthorityStore, StateStore
from experiments.person_ir.durable import DurableAuthorityStore, DurableStateStore
from experiments.person_ir.examples import collaboration
from experiments.person_ir.joint import JointCommitService


NOW = datetime(2026, 9, 30, 8, tzinfo=timezone.utc)


class JointCommitTests(unittest.TestCase):
    def test_legacy_shared_state_with_receipt_cannot_gain_policy_retroactively(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "legacy.sqlite")
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE state (domain TEXT PRIMARY KEY, version INTEGER NOT NULL, vals TEXT NOT NULL)")
                db.execute("CREATE TABLE commits (domain TEXT NOT NULL, proposal_id TEXT NOT NULL, receipt TEXT NOT NULL, PRIMARY KEY(domain, proposal_id))")
                db.execute("INSERT INTO state VALUES ('shared:team', 0, '{}')")
                db.execute("INSERT INTO commits VALUES ('shared:team', 'old', '{}')")
            with self.assertRaisesRegex(ValueError, "legacy state"):
                DurableStateStore(path, "shared:team",
                                  required_principals=("person:1", "person:2"))

    def test_joint_receipt_and_both_grants_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "shared.sqlite")
            authority = DurableAuthorityStore(path)
            state = DurableStateStore(path, "shared:team",
                                      required_principals=("person:1", "person:2"))
            joint = JointCommitService(("person:1", "person:2"))
            item = collaboration.request(["person:2"])
            handles = {
                principal: authority.issue(
                    principal=principal, domain="shared:team", agent="collab@1",
                    operation="commit", resource="shared_document", issuer=principal,
                    issued_at=NOW)
                for principal in joint.required_principals
            }
            identifiers = {principal: authority.describe(handle).capability_id
                           for principal, handle in handles.items()}
            first = joint.commit(item, state, authority, handles, agent="collab@1", now=NOW)
            self.assertEqual(first.commit.receipt.authority_ids,
                             tuple(identifiers.values()))
            state.close()
            authority.close()

            authority = DurableAuthorityStore(path)
            with self.assertRaisesRegex(ValueError, "requires joint"):
                DurableStateStore(path, "shared:team")
            with self.assertRaisesRegex(ValueError, "policy mismatch"):
                DurableStateStore(path, "shared:team",
                                  required_principals=("person:1", "person:3"))
            state = DurableStateStore(path, "shared:team",
                                      required_principals=("person:1", "person:2"))
            recovered = authority.host_handles()
            handles = {principal: recovered[identifier]
                       for principal, identifier in identifiers.items()}
            replay = joint.commit(item, state, authority, handles,
                                  agent="collab@1", now=NOW)
            self.assertTrue(replay.commit.replayed)
            self.assertEqual(replay.commit.receipt, first.commit.receipt)
            self.assertEqual(state.snapshot().version, 1)
            with self.assertRaisesRegex(AuthorityError, "required principal"):
                state.commit(item, authority, handles["person:1"],
                             principal="person:1", agent="collab@1", now=NOW)
            authority.revoke(identifiers["person:2"])
            with self.assertRaisesRegex(AuthorityError, "revoked"):
                joint.commit(item, state, authority, handles, agent="collab@1", now=NOW)
            state.close()
            authority.close()

    def test_two_distinct_live_grants_required(self):
        authority = AuthorityStore()
        with self.assertRaisesRegex(ValueError, "requires joint"):
            StateStore("shared:team")
        state = StateStore("shared:team", required_principals=("person:1", "person:2"))
        joint = JointCommitService(("person:1", "person:2"))
        item = collaboration.request(["person:2"])  # Claim alone is not a grant.
        def issue(principal):
            return authority.issue(
                principal=principal, domain="shared:team", agent="collab@1",
                operation="commit", resource="shared_document",
                issuer=principal, issued_at=NOW)
        first = issue("person:1")
        with self.assertRaisesRegex(AuthorityError, "required principal"):
            joint.commit(item, state, authority, {"person:1": first},
                         agent="collab@1", now=NOW)
        with self.assertRaisesRegex(AuthorityError, "scope mismatch"):
            joint.commit(item, state, authority,
                         {"person:1": first, "person:2": first},
                         agent="collab@1", now=NOW)
        second = issue("person:2")
        authority.revoke(authority.describe(second).capability_id)
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            joint.commit(item, state, authority,
                         {"person:1": first, "person:2": second},
                         agent="collab@1", now=NOW)
        self.assertEqual(state.snapshot().version, 0)
        with self.assertRaisesRegex(AuthorityError, "required principal"):
            state.commit(item, authority, first, principal="person:1",
                         agent="collab@1", now=NOW)
        second = issue("person:2")
        outcome = joint.commit(item, state, authority,
                               {"person:1": first, "person:2": second},
                               agent="collab@1", now=NOW)
        self.assertEqual(outcome.authority_ids, (
            authority.describe(first).capability_id,
            authority.describe(second).capability_id))
        self.assertTrue(outcome.commit.receipt.applied)
        self.assertEqual(state.snapshot().version, 1)
        with self.assertRaisesRegex(AuthorityError, "required principal"):
            state.commit(item, authority, first, principal="person:1",
                         agent="collab@1", now=NOW)
        self.assertTrue(joint.commit(
            item, state, authority, {"person:1": first, "person:2": second},
            agent="collab@1", now=NOW).commit.replayed)
        authority.revoke(authority.describe(second).capability_id)
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            joint.commit(item, state, authority,
                         {"person:1": first, "person:2": second},
                         agent="collab@1", now=NOW)


if __name__ == "__main__":
    unittest.main()
