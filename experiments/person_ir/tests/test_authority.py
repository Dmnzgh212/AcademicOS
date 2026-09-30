import json
import unittest
from datetime import datetime, timedelta, timezone

from experiments.person_ir import Graph, Interpreter, Node, Observation
from experiments.person_ir.authority import AuthorityError, AuthorityStore


NOW = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
ACTOR = {"principal": "person:1", "domain": "personal:1", "agent": "plugin:mail"}


def effect(*, protected=True, destination="alice@example.com"):
    label = "protected" if protected else "public"
    nodes = [Node("draft", "source", config={"name": "draft", "label": label})]
    source = "draft"
    if protected:
        nodes.append(Node("disclose", "declassify", (source,),
                          {"destination": destination, "purpose": "send requested message"}))
        source = "disclose"
    nodes.append(Node("send", "effect_request", (source,),
                      {"kind": "email", "destination": destination}))
    return Interpreter().run(Graph(tuple(nodes)),
                             {"draft": Observation("hello", "draft:1", label)},
                             base_version=0).effects[0]


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.store = AuthorityStore()

    def grant(self, operation="effect:email", resource="alice@example.com", **overrides):
        return self.store.issue(**(ACTOR | {"operation": operation, "resource": resource,
                                            "issuer": "person:1", "issued_at": NOW} | overrides))

    def test_serialized_id_or_other_store_handle_is_not_authority(self):
        handle = self.grant()
        description = self.store.describe(handle)
        self.assertIsInstance(json.dumps(description.capability_id), str)
        with self.assertRaises(TypeError):
            json.dumps({"handle": handle})
        for forged in (description.capability_id, {"capability_id": description.capability_id},
                       AuthorityStore().issue(**(ACTOR | {"operation": "effect:email",
                                                       "resource": "alice@example.com",
                                                       "issuer": "person:1", "issued_at": NOW}))):
            with self.assertRaises(AuthorityError):
                self.store.check_effect_request(effect(protected=False), forged, **ACTOR, now=NOW)

    def test_revoked_and_expired_delegation_fail_at_check_time(self):
        request = effect(protected=False)
        handle = self.grant(expires_at=NOW + timedelta(minutes=10))
        self.assertEqual(len(self.store.check_effect_request(request, handle, **ACTOR, now=NOW).capability_ids), 1)
        with self.assertRaises(AuthorityError):
            self.store.check_effect_request(request, handle, **ACTOR, now=NOW + timedelta(minutes=10))
        self.store.revoke(self.store.describe(handle).capability_id)
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            self.store.check_effect_request(request, handle, **ACTOR, now=NOW + timedelta(minutes=1))

    def test_scope_actor_and_activation_context(self):
        request = effect(protected=False)
        wrong_destination = self.grant(resource="bob@example.com")
        with self.assertRaisesRegex(AuthorityError, "scope"):
            self.store.check_effect_request(request, wrong_destination, **ACTOR, now=NOW)
        handle = self.grant(activation_context="user-click")
        with self.assertRaisesRegex(AuthorityError, "context"):
            self.store.check_effect_request(request, handle, **ACTOR, now=NOW)
        with self.assertRaisesRegex(AuthorityError, "scope"):
            self.store.check_effect_request(request, handle,
                                            **(ACTOR | {"agent": "plugin:other"}),
                                            context="user-click", now=NOW)
        self.store.check_effect_request(request, handle, **ACTOR,
                                        context="user-click", now=NOW)

    def test_effect_and_protected_disclosure_need_separate_grants(self):
        request = effect()
        send_handle = self.grant()
        with self.assertRaises(AuthorityError):
            self.store.check_effect_request(request, send_handle, **ACTOR, now=NOW)
        disclose_handle = self.grant(operation="disclose", purpose="send requested message")
        result = self.store.check_effect_request(request, send_handle, **ACTOR,
                                                 disclosure_handle=disclose_handle, now=NOW)
        self.assertEqual(len(result.capability_ids), 2)
        self.store.revoke(self.store.describe(disclose_handle).capability_id)
        with self.assertRaisesRegex(AuthorityError, "revoked"):
            self.store.check_effect_request(request, send_handle, **ACTOR,
                                            disclosure_handle=disclose_handle, now=NOW)

    def test_own_state_read_does_not_grant_effect_or_commit(self):
        handle = self.grant(operation="read", resource="own:state")
        with self.assertRaisesRegex(AuthorityError, "scope"):
            self.store.check_effect_request(effect(protected=False), handle, **ACTOR, now=NOW)
        graph = Graph((Node("src", "source", config={"name": "x", "label": "public"}),
                       Node("proposal", "propose", ("src",), {"target": "study_blocks"}),
                       Node("commit", "commit_request", ("proposal",))))
        request = Interpreter().run(graph, {"x": Observation("plan", "user")}, base_version=1).commits[0]
        with self.assertRaisesRegex(AuthorityError, "scope"):
            self.store.check_commit_request(request, handle, **ACTOR, now=NOW)
        commit_handle = self.grant(operation="commit", resource="study_blocks")
        self.store.check_commit_request(request, commit_handle, **ACTOR, now=NOW)

    def test_validity_inputs_reject_naive_time_and_impossible_expiry(self):
        with self.assertRaises(ValueError):
            self.grant(issued_at=datetime(2026, 9, 29))
        with self.assertRaises(ValueError):
            self.grant(expires_at=NOW)


if __name__ == "__main__":
    unittest.main()
