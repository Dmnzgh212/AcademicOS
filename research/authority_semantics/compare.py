"""Synthetic trace study, not a Wasm runtime, policy engine or PersonIR compiler."""

from copy import deepcopy
import json
from pathlib import Path
import sys


class Model:
    def __init__(self):
        self.records = {}
        self.effects = {}
        self.grants = {}
        self.snapshot = 1
        self.trace = []

    def authorized(self, action, resource, owners):
        return all(self.grants.get((action, resource, owner)) == self.snapshot for owner in owners)

    def apply(self, node):
        op = node['op']
        try:
            result = self.perform(node)
            self.trace.append([node['id'], op, 'allow', result])
        except PermissionError as exc:
            self.trace.append([node['id'], op, 'deny', str(exc)])

    def perform(self, n):
        op = n['op']
        if op in ('grant', 'revoke', 'replace', 'observe') and n.get('role') != 'operator':
            raise PermissionError('trusted source required')
        if op == 'observe':
            self.records[n['id']] = {'kind': 'evidence', 'owners': n['owners'], 'inputs': []}
        elif op == 'derive':
            owners = sorted({owner for ref in n['inputs'] for owner in self.records[ref]['owners']})
            # Claimed kind/owners are guest assertions and cannot override host handles.
            self.records[n['id']] = {'kind': 'derived', 'owners': owners, 'inputs': n['inputs']}
        elif op == 'propose':
            source = self.records[n['input']]
            self.records[n['id']] = {'kind': 'proposal', 'owners': source['owners'],
                                     'inputs': [n['input']], 'status': 'pending'}
        elif op == 'reject':
            target = self.records[n['input']]
            if target['kind'] != 'proposal':
                raise PermissionError('only proposals can be rejected')
            target['status'] = 'rejected'
        elif op == 'grant':
            self.grants[(n['action'], n['resource'], n['owner'])] = self.snapshot
        elif op == 'revoke':
            self.grants.pop((n['action'], n['resource'], n['owner']), None)
        elif op == 'replace':
            self.snapshot += 1
        elif op == 'disclose':
            if not self.authorized('disclose', n['destination'], self.records[n['input']]['owners']):
                raise PermissionError('disclosure authority missing or stale')
            return 'synthetic disclosure only'
        elif op == 'request':
            self.effects[n['id']] = {'kind': n['kind'], 'owners': self.records[n['input']]['owners'],
                                     'snapshot': self.snapshot, 'status': 'pending'}
        elif op == 'execute':
            effect = self.effects[n['input']]
            if effect['snapshot'] != self.snapshot:
                raise PermissionError('stale effect snapshot')
            if not self.authorized('effect', effect['kind'], effect['owners']):
                raise PermissionError('effect authority missing or stale')
            if effect['status'] != 'pending':
                raise PermissionError('effect cannot be blindly replayed')
            effect['status'] = n['outcome']
            return effect['status']
        else:
            raise ValueError(f'unsupported operation: {op}')
        return None

    def result(self):
        return {'trace': self.trace, 'records': self.records, 'effects': self.effects,
                'snapshot': self.snapshot}


def sequential(nodes):
    host = Model()
    for node in nodes:
        host.apply(deepcopy(node))
    return host.result()


def graph(nodes):
    host = Model()
    pending = deepcopy(nodes)
    done = set()
    while pending:
        eligible = next((n for n in pending if set(n['after']) <= done), None)
        if eligible is None:
            raise ValueError('cycle or missing ordering dependency')
        host.apply(eligible)
        done.add(eligible['id'])
        pending.remove(eligible)
    return host.result()


def scenario(name, steps, denied):
    # Explicit chain is a deliberately modest graph baseline. It provides no
    # static flow analysis and does not invent a PersonIR enforcement advantage.
    nodes = []
    for index, step in enumerate(steps):
        node = {'id': f'n{index}', **step}
        node['after'] = [nodes[-1]['id']] if nodes else []
        nodes.append(node)
    return {'name': name, 'nodes': nodes, 'denied': denied}


def cases():
    evidence = {'op': 'observe', 'role': 'operator', 'owners': ['alice']}
    grant = {'op': 'grant', 'role': 'operator', 'action': 'effect', 'resource': 'device', 'owner': 'alice'}
    return [
        scenario('observation_survives_proposal_rejection', [evidence,
            {'op': 'propose', 'input': 'n0'}, {'op': 'reject', 'input': 'n1'},
            {'op': 'reject', 'input': 'n0'}], ['n3']),
        scenario('derived_mail_cannot_launder_label', [evidence,
            {'op': 'derive', 'inputs': ['n0'], 'claimed_owners': [], 'claimed_kind': 'evidence'},
            {'op': 'disclose', 'input': 'n1', 'destination': 'ai'}], ['n2']),
        scenario('shared_note_requires_both_owners', [evidence,
            {'op': 'observe', 'role': 'operator', 'owners': ['bob']},
            {'op': 'derive', 'inputs': ['n0', 'n1']},
            {'op': 'grant', 'role': 'operator', 'action': 'disclose', 'resource': 'export', 'owner': 'alice'},
            {'op': 'disclose', 'input': 'n2', 'destination': 'export'},
            {'op': 'grant', 'role': 'operator', 'action': 'disclose', 'resource': 'export', 'owner': 'bob'},
            {'op': 'disclose', 'input': 'n2', 'destination': 'export'}], ['n4']),
        scenario('read_is_not_payment_authority', [evidence,
            {'op': 'grant', 'role': 'operator', 'action': 'read', 'resource': 'payment', 'owner': 'alice'},
            {'op': 'request', 'input': 'n0', 'kind': 'payment'},
            {'op': 'execute', 'input': 'n2', 'outcome': 'completed'},
            {'op': 'grant', 'role': 'guest', 'action': 'effect', 'resource': 'payment', 'owner': 'alice'}], ['n3', 'n4']),
        scenario('device_revoke_and_unknown_replay', [evidence, grant,
            {'op': 'request', 'input': 'n0', 'kind': 'device'},
            {**grant, 'op': 'revoke'},
            {'op': 'execute', 'input': 'n2', 'outcome': 'completed'}, grant,
            {'op': 'execute', 'input': 'n2', 'outcome': 'unknown'},
            {'op': 'execute', 'input': 'n2', 'outcome': 'completed'}], ['n4', 'n7']),
        scenario('replacement_invalidates_old_authority', [evidence, grant,
            {'op': 'request', 'input': 'n0', 'kind': 'device'},
            {'op': 'replace', 'role': 'operator'},
            {'op': 'execute', 'input': 'n2', 'outcome': 'completed'}], ['n4']),
    ]


def run():
    results = []
    for case in cases():
        baseline = sequential(case['nodes'])
        candidate = graph(list(reversed(case['nodes'])))
        assert baseline == candidate, case['name']
        assert [row[0] for row in baseline['trace'] if row[2] == 'deny'] == case['denied']
        assert baseline['records']['n0']['kind'] == 'evidence'
        if case['name'] == 'derived_mail_cannot_launder_label':
            assert baseline['records']['n1']['owners'] == ['alice']
            assert baseline['records']['n1']['kind'] == 'derived'
        if case['name'] == 'device_revoke_and_unknown_replay':
            assert baseline['effects']['n2']['status'] == 'unknown'
        results.append({'name': case['name'], 'status': 'PASS', 'fixture': case['nodes'],
                        'B1': baseline, 'R_graph': candidate})
    return {'scope': 'synthetic closed-operation trace model; not production enforcement',
            'B0_executed': False, 'Wasm_executed': False, 'PersonIR_compiler': False,
            'equivalence_by_shared_host': True, 'unique_IR_advantage_demonstrated': False,
            'cases': results}


if __name__ == '__main__':
    result = json.dumps(run(), ensure_ascii=False, indent=2)
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(result + '\n', encoding='utf-8')
    else:
        print(result)
