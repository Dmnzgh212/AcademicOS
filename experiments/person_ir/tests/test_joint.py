import unittest
from datetime import datetime, timezone

from experiments.person_ir import AuthorityError, AuthorityStore, StateStore
from experiments.person_ir.examples import collaboration
from experiments.person_ir.joint import JointCommitService


NOW = datetime(2026, 9, 30, 8, tzinfo=timezone.utc)


class JointCommitTests(unittest.TestCase):
    def test_two_distinct_live_grants_required(self):
        authority, state = AuthorityStore(), StateStore("shared:team")
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
        second = issue("person:2")
        outcome = joint.commit(item, state, authority,
                               {"person:1": first, "person:2": second},
                               agent="collab@1", now=NOW)
        self.assertEqual(outcome.authority_ids, (
            authority.describe(first).capability_id,
            authority.describe(second).capability_id))
        self.assertTrue(outcome.commit.receipt.applied)
        self.assertEqual(state.snapshot().version, 1)
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
