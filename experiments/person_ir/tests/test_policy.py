import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from experiments.person_ir import (AuthorityStore, EffectService, FakeExecutor,
                                   Interpreter, Observation)
from experiments.person_ir.baseline import ComponentSession, Manifest
from experiments.person_ir.durable import DurableEffectService
from experiments.person_ir.examples import email, home, payment
from experiments.person_ir.policy import (ComparePaths, DestinationEquals, EffectPolicy,
                                          Evidence, FreshEvidence, NumberBetween,
                                          PolicyRejected)


NOW = datetime(2026, 9, 30, 7, tzinfo=timezone.utc)
ACTOR = {"principal": "person:1", "domain": "personal:1"}


def grants(authority, agent, kind, destination, purpose=None):
    args = ACTOR | {"agent": agent, "resource": destination,
                    "issuer": "person:1", "issued_at": NOW}
    effect = authority.issue(**(args | {"operation": f"effect:{kind}"}))
    disclose = (authority.issue(**(args | {"operation": "disclose", "purpose": purpose}))
                if purpose else None)
    return effect, disclose


class HostPolicyTests(unittest.TestCase):
    def test_same_payment_policy_accepts_conventional_host_request(self):
        merchant = "merchant:bookstore"
        policy = EffectPolicy((
            NumberBetween((1, "CAD"), 0, 15),
            FreshEvidence("quote:1", (1,), timedelta(minutes=5)),
        ))
        session = ComponentSession(
            Manifest("shop@1", frozenset({"price"}), frozenset(),
                     frozenset({("payment", merchant)})),
            {"price": Observation({"CAD": 10}, "quote:1", "protected")},
            base_version=0, intent_id="buy:conventional")
        price = session.read("price")
        item = session.effect("payment", merchant, [{"item": "textbook"}, price],
                              disclosure_purpose="purchase")
        authority, executor = AuthorityStore(), FakeExecutor()
        pay, disclose = grants(authority, "shop@1", "payment", merchant, "purchase")
        result = EffectService({"payment": executor}, policy=policy).execute(
            item, authority, pay, **ACTOR, agent="shop@1",
            disclosure_handle=disclose, now=NOW,
            evidence={"quote:1": Evidence({"CAD": 10}, NOW)})
        self.assertEqual(result.receipt.status, "succeeded")
        self.assertEqual(len(executor.actions), 1)

    def test_payment_bound_and_current_quote_are_required(self):
        merchant = "merchant:bookstore"
        policy = EffectPolicy((
            NumberBetween((1, "CAD"), 0, 15),
            FreshEvidence("quote:1", (1,), timedelta(minutes=5)),
        ))
        authority, executor = AuthorityStore(), FakeExecutor()
        pay, disclose = grants(authority, "shop@1", "payment", merchant, "purchase")
        service = EffectService({"payment": executor}, policy=policy)
        kwargs = dict(authority=authority, effect_handle=pay,
                      disclosure_handle=disclose, agent="shop@1", now=NOW, **ACTOR)
        old = payment.request(merchant, 10, intent_id="old")
        with self.assertRaisesRegex(PolicyRejected, "no longer matches"):
            service.execute(old, evidence={"quote:1": Evidence({"CAD": 20}, NOW)}, **kwargs)
        with self.assertRaisesRegex(PolicyRejected, "outside approved bounds"):
            service.execute(payment.request(merchant, 20, intent_id="high"),
                            evidence={"quote:1": Evidence({"CAD": 20}, NOW)}, **kwargs)
        with self.assertRaisesRegex(PolicyRejected, "stale"):
            service.execute(old, evidence={"quote:1": Evidence({"CAD": 10},
                            NOW - timedelta(minutes=6))}, **kwargs)
        self.assertEqual(executor.actions, [])
        accepted = service.execute(old, evidence={"quote:1": Evidence({"CAD": 10}, NOW)},
                                   **kwargs)
        self.assertEqual(accepted.receipt.status, "succeeded")
        # Receipt lookup does not re-execute or require the earlier quote to remain current.
        self.assertTrue(service.execute(old, evidence={"quote:1": Evidence({"CAD": 20}, NOW)},
                                        **kwargs).replayed)
        self.assertEqual(len(executor.actions), 1)

    def test_device_threshold_and_fresh_sensor_apply_to_durable_service(self):
        policy = EffectPolicy((
            ComparePaths((0, "celsius"), (1, "cool_above_celsius"), "gt"),
            FreshEvidence("sensor:thermostat:1", (0,), timedelta(minutes=2)),
        ))
        authority, executor = AuthorityStore(), FakeExecutor()
        handle, _ = grants(authority, "home@1", "device", "thermostat:1")
        kwargs = dict(authority=authority, effect_handle=handle,
                      agent="home@1", now=NOW, **ACTOR)
        with tempfile.TemporaryDirectory() as directory:
            service = DurableEffectService(str(Path(directory) / "host.sqlite"),
                                           {"device": executor}, policy=policy)
            low = home.request(20, intent_id="low")
            with self.assertRaisesRegex(PolicyRejected, "relation failed"):
                service.execute(low, evidence={
                    "sensor:thermostat:1": Evidence({"celsius": 20}, NOW)}, **kwargs)
            high = home.request(30, intent_id="high")
            with self.assertRaisesRegex(PolicyRejected, "stale"):
                service.execute(high, evidence={
                    "sensor:thermostat:1": Evidence({"celsius": 30},
                                                   NOW - timedelta(minutes=3))}, **kwargs)
            self.assertIsNone(service._journal.lookup("personal:1", high.effect_id))
            self.assertEqual(executor.actions, [])
            accepted = service.execute(high, evidence={
                "sensor:thermostat:1": Evidence({"celsius": 30}, NOW)}, **kwargs)
            self.assertEqual(accepted.receipt.status, "succeeded")
            service.close()

    def test_recipient_path_must_equal_destination(self):
        destination = "alice@example.com"
        policy = EffectPolicy((DestinationEquals((1,)),))
        graph = email.program(destination)
        item = Interpreter().run(graph, {
            "context": Observation("meeting", "context:1", "protected"),
            "draft": Observation("hello", "draft:1", "protected"),
            "recipient": Observation("bob@example.com", "recipient:1"),
        }, base_version=0, producer="mail@1", intent_id="mismatch").effects[0]
        authority, executor = AuthorityStore(), FakeExecutor()
        send, disclose = grants(authority, "mail@1", "email", destination,
                                "send requested email")
        with self.assertRaisesRegex(PolicyRejected, "destination mismatch"):
            EffectService({"email": executor}, policy=policy).execute(
                item, authority, send, **ACTOR, agent="mail@1",
                disclosure_handle=disclose, now=NOW)
        self.assertEqual(executor.actions, [])


if __name__ == "__main__":
    unittest.main()
