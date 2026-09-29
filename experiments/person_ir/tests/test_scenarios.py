import unittest
from datetime import datetime, timedelta, timezone

from experiments.person_ir import (AuthorityStore, EffectService, FakeExecutor,
                                   Interpreter, Observation, StaleProposal,
                                   StateStore)
from experiments.person_ir.examples import academic, collaboration, email, home, payment


NOW = datetime(2026, 9, 29, 16, tzinfo=timezone.utc)
PRINCIPAL = "person:1"


def grant(store, *, domain, agent, operation, resource, purpose=None, expires_at=None):
    return store.issue(principal=PRINCIPAL, domain=domain, agent=agent,
                       operation=operation, resource=resource, purpose=purpose,
                       issuer=PRINCIPAL, issued_at=NOW, expires_at=expires_at)


class ScenarioTests(unittest.TestCase):
    def test_academic_observation_proposal_and_stale_calendar(self):
        state, authority = StateStore("personal:1"), AuthorityStore()
        handle = grant(authority, domain="personal:1", agent="academic@1",
                       operation="commit", resource="study_blocks")
        inputs = {
            "deadline": Observation({"course": "CSI 2110"}, "course-feed:1", "protected"),
            "availability": Observation({"free_slot": "Thursday"}, "calendar:1", "protected"),
        }
        first = Interpreter().run(academic.GRAPH, inputs, base_version=0,
                                  producer="academic@1")
        self.assertEqual(len(first.effects), 0)
        self.assertEqual(state.snapshot().values, {})
        state.commit(first.commits[0], authority, handle,
                     principal=PRINCIPAL, agent="academic@1", now=NOW)
        inputs["availability"] = Observation({"free_slot": "Friday"}, "calendar:2", "protected")
        stale = Interpreter().run(academic.GRAPH, inputs, base_version=0,
                                  producer="academic@1").commits[0]
        with self.assertRaises(StaleProposal):
            state.commit(stale, authority, handle,
                         principal=PRINCIPAL, agent="academic@1", now=NOW)
        self.assertEqual(state.snapshot().values["study_blocks"], ["CSI 2110", "Thursday"])

    def test_email_egress_requires_grants_and_replay_is_inert(self):
        authority, executor = AuthorityStore(), FakeExecutor()
        service = EffectService({"email": executor})
        destination = "alice@example.com"
        item = email.request(destination)
        send = grant(authority, domain="personal:1", agent="mail@1",
                     operation="effect:email", resource=destination)
        disclose = grant(authority, domain="personal:1", agent="mail@1",
                         operation="disclose", resource=destination,
                         purpose="send requested email")
        result = service.execute(item, authority, send, principal=PRINCIPAL,
                                 domain="personal:1", agent="mail@1",
                                 disclosure_handle=disclose, now=NOW)
        self.assertEqual(result.receipt.status, "succeeded")
        self.assertTrue(service.execute(item, authority, send, principal=PRINCIPAL,
                                        domain="personal:1", agent="mail@1",
                                        disclosure_handle=disclose, now=NOW).replayed)
        self.assertEqual(len(executor.actions), 1)
        self.assertIn("course meeting", str(executor.actions[0].payload))

    def test_email_recipient_value_can_disagree_with_destination_known_gap(self):
        item = Interpreter().run(email.program("alice@example.com"), {
            "context": Observation("meeting", "context:1", "protected"),
            "draft": Observation("hello", "draft:1", "protected"),
            "recipient": Observation("bob@example.com", "recipient:1", "public"),
        }, base_version=0, producer="email-example@1", intent_id="send:mismatch").effects[0]
        self.assertEqual(item.destination, "alice@example.com")
        self.assertEqual(item.payload[1], "bob@example.com")
        # The graph has no dependent constraint tying a recipient value to a sink.

    def test_payment_currently_executes_stale_quote_known_gap(self):
        authority, executor = AuthorityStore(), FakeExecutor()
        merchant = "merchant:bookstore"
        item = payment.request(merchant, observed_price=10)
        # A newer quote exists before execution, but the current host cannot
        # require revalidation against it. This is a falsification finding.
        newer_quote = payment.request(merchant, observed_price=20)
        self.assertNotEqual(item.effect_id, newer_quote.effect_id)
        pay = grant(authority, domain="personal:1", agent="shop@1",
                    operation="effect:payment", resource=merchant,
                    expires_at=NOW + timedelta(hours=1))
        disclose = grant(authority, domain="personal:1", agent="shop@1",
                         operation="disclose", resource=merchant, purpose="purchase")
        result = EffectService({"payment": executor}).execute(
            item, authority, pay, principal=PRINCIPAL, domain="personal:1",
            agent="shop@1", disclosure_handle=disclose, now=NOW + timedelta(minutes=5))
        self.assertEqual(result.receipt.status, "succeeded")
        self.assertEqual(executor.actions[0].payload[1], {"CAD": 10})

    def test_home_currently_acts_on_old_or_below_threshold_sensor_known_gap(self):
        item = home.request(temperature=20)
        authority, executor = AuthorityStore(), FakeExecutor()
        handle = grant(authority, domain="personal:1", agent="home@1",
                       operation="effect:device", resource="thermostat:1")
        result = EffectService({"device": executor}).execute(
            item, authority, handle, principal=PRINCIPAL, domain="personal:1",
            agent="home@1", now=NOW + timedelta(days=1))
        self.assertEqual(result.receipt.status, "succeeded")
        self.assertEqual(executor.actions[0].payload[0], {"celsius": 20})
        self.assertEqual(executor.actions[0].payload[1], {"cool_above_celsius": 25})

    def test_shared_state_accepts_one_grant_without_second_principal_known_gap(self):
        state, authority = StateStore("shared:team"), AuthorityStore()
        item = collaboration.request(["person:2"])  # an unverified data claim
        one_person = grant(authority, domain="shared:team", agent="collab@1",
                           operation="commit", resource="shared_document")
        result = state.commit(item, authority, one_person,
                              principal=PRINCIPAL, agent="collab@1", now=NOW)
        self.assertTrue(result.receipt.applied)
        self.assertEqual(state.snapshot().values["shared_document"][1], ["person:2"])
        # No second capability or authenticated vote was checked.
        self.assertEqual(result.checked_capability_id, authority.describe(one_person).capability_id)


if __name__ == "__main__":
    unittest.main()
