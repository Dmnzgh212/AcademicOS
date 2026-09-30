import unittest
from datetime import datetime, timezone

from experiments.person_ir import AuthorityError, AuthorityStore, EffectService, FakeExecutor, Observation
from experiments.person_ir.package import PackageManifest
from experiments.person_ir.wasm_bridge import (WasmRequestRejected, _materialize_email,
                                                email_request_from_wasm)


NOW = datetime(2026, 9, 29, 20, tzinfo=timezone.utc)
DEST = "alice@example.com"
ACTOR = {"principal": "person:1", "domain": "personal:1", "agent": "mail@1"}
OBS = {
    "context": Observation("meeting", "context:1", "protected"),
    "draft": Observation("hello", "draft:1", "protected"),
    "recipient": Observation(DEST, "recipient:1"),
    "overprovided": Observation("secret", "secret:1", "protected"),
}
MANIFEST = PackageManifest("mail@1", frozenset({"context", "draft", "recipient"}),
                           frozenset(), frozenset({("email", DEST)}),
                           frozenset({(DEST, "send requested email")}))


def grant(store, operation, purpose=None):
    return store.issue(**(ACTOR | {"operation": operation, "resource": DEST,
                                  "purpose": purpose, "issuer": "person:1",
                                  "issued_at": NOW}))


class WasmHostBridgeTests(unittest.TestCase):
    def test_authorized_wasm_request_executes_once_and_replays(self):
        item = email_request_from_wasm(MANIFEST, OBS, DEST, intent_id="send:1")
        self.assertEqual(item.payload, [["meeting", "hello"], DEST])
        self.assertEqual(item.sources, frozenset({"context:1", "draft:1", "recipient:1"}))
        authority, executor = AuthorityStore(), FakeExecutor()
        send = grant(authority, "effect:email")
        disclose = grant(authority, "disclose", "send requested email")
        service = EffectService({"email": executor})
        kwargs = dict(authority=authority, effect_handle=send, disclosure_handle=disclose,
                      now=NOW, **ACTOR)
        first = service.execute(item, **kwargs)
        replay_item = email_request_from_wasm(MANIFEST, OBS, DEST, intent_id="send:1")
        second = service.execute(replay_item, **kwargs)
        self.assertEqual(item.effect_id, replay_item.effect_id)
        self.assertEqual(first.receipt.status, "succeeded")
        self.assertTrue(second.replayed)
        self.assertEqual(len(executor.actions), 1)

    def test_missing_or_revoked_grants_block_wasm_effect(self):
        item = email_request_from_wasm(MANIFEST, OBS, DEST, intent_id="send:2")
        authority, executor = AuthorityStore(), FakeExecutor()
        send = grant(authority, "effect:email")
        disclose = grant(authority, "disclose", "send requested email")
        service = EffectService({"email": executor})
        with self.assertRaises(AuthorityError):
            service.execute(item, authority, send, **ACTOR, now=NOW)
        authority.revoke(authority.describe(send).capability_id)
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            service.execute(item, authority, send, **ACTOR,
                            disclosure_handle=disclose, now=NOW)
        self.assertEqual(executor.actions, [])

    def test_host_rejects_missing_manifest_disclosure_and_tampered_response(self):
        unapproved = PackageManifest("mail@1", MANIFEST.sources, frozenset(),
                                     MANIFEST.effect_scopes, frozenset())
        with self.assertRaisesRegex(WasmRequestRejected, "disclosure"):
            email_request_from_wasm(unapproved, OBS, DEST)
        forged = {"kind": "email", "destination": DEST,
                  "payload": [["meeting", "forged"], DEST], "label": "protected",
                  "disclosure_purpose": "send requested email",
                  "sources": ["context:1", "draft:1", "recipient:1"]}
        with self.assertRaisesRegex(WasmRequestRejected, "differs"):
            _materialize_email(forged, MANIFEST, OBS, DEST, "send:3")


if __name__ == "__main__":
    unittest.main()
