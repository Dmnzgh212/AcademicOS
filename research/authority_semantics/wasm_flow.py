"""Real core-Wasm implicit-flow experiment; custom research ABI, no real egress."""

import json
from pathlib import Path
import sys

import wasmtime

MODULES = {
    'implicit_branch': '''(module
      (import "research" "read_private_bit" (func $read (result i32)))
      (import "research" "release" (func $release (param i32) (result i32)))
      (func (export "run") (result i32)
        (if (call $read)
          (then (drop (call $release (i32.const 1))))
          (else (drop (call $release (i32.const 0)))))
        i32.const 0))''',
    'constant_after_private_read': '''(module
      (import "research" "read_private_bit" (func $read (result i32)))
      (import "research" "release" (func $release (param i32) (result i32)))
      (func (export "run") (result i32)
        (drop (call $read))
        (drop (call $release (i32.const 7)))
        i32.const 0))''',
    'public_constant': '''(module
      (import "research" "release" (func $release (param i32) (result i32)))
      (func (export "run") (result i32)
        (drop (call $release (i32.const 7)))
        i32.const 0))''',
}


def execute(module_name, secret, mode, delegated=False, revoke_before_release=False):
    config = wasmtime.Config()
    config.consume_fuel = True
    engine = wasmtime.Engine(config)
    module = wasmtime.Module(engine, wasmtime.wat2wasm(MODULES[module_name]))
    store = wasmtime.Store(engine)
    store.set_limits(memory_size=8 * 1024 * 1024, instances=1, memories=1, tables=0)
    store.set_fuel(1_000_000)
    linker = wasmtime.Linker(engine)
    touched_private = False
    authority = delegated
    released = []
    trace = []

    def read():
        nonlocal touched_private
        touched_private = True
        trace.append('private input accessed')
        return secret

    def release(value):
        nonlocal authority
        if revoke_before_release:
            authority = False  # Trusted fault injection, not concurrent control dispatch.
            trace.append('delegation revoked before release check')
        # Deliberately unsound negative control: literals are treated as public
        # regardless of private control dependencies. Not our fair baseline.
        allowed = mode == 'literal_only_negative_control' or not touched_private or authority
        trace.append('release allowed' if allowed else 'release denied')
        if allowed:
            released.append(value)  # In-memory observation only, never external I/O.
        return 0 if allowed else 1

    linker.define_func('research', 'read_private_bit',
                       wasmtime.FuncType([], [wasmtime.ValType.i32()]), read)
    linker.define_func('research', 'release',
                       wasmtime.FuncType([wasmtime.ValType.i32()], [wasmtime.ValType.i32()]), release)
    guest = linker.instantiate(store, module)
    assert guest.exports(store)['run'](store) == 0
    return {'module': module_name, 'synthetic_secret': secret, 'mode': mode,
            'delegated_initially': delegated, 'revoke_before_release': revoke_before_release,
            'released': released, 'trace': trace}


def run():
    negative = [execute('implicit_branch', bit, 'literal_only_negative_control') for bit in (0, 1)]
    conservative = [execute('implicit_branch', bit, 'conservative_execution_label') for bit in (0, 1)]
    imprecise = [execute('constant_after_private_read', bit, 'conservative_execution_label') for bit in (0, 1)]
    public = execute('public_constant', 0, 'conservative_execution_label')
    authorized = execute('implicit_branch', 1, 'conservative_execution_label', delegated=True)
    revoked = execute('implicit_branch', 1, 'conservative_execution_label', delegated=True,
                      revoke_before_release=True)
    assert [row['released'] for row in negative] == [[0], [1]]
    assert all(not row['released'] for row in conservative)
    assert all(not row['released'] for row in imprecise)
    assert public['released'] == [7]
    assert authorized['released'] == [1] and not revoked['released']
    return {'scope': 'real core-Wasm, custom research host, synthetic one-bit input and in-memory sink',
            'production_ABI': False, 'PersonIR_executed': False, 'external_effects': False,
            'unique_IR_advantage_demonstrated': False,
            'negative_control_leaks_one_bit': negative,
            'ordinary_conservative_host_blocks_release': conservative,
            'conservative_label_also_blocks_secret_independent_constant': imprecise,
            'public_without_private_read': public, 'authorized_disclosure': authorized,
            'revoked_before_release': revoked,
            'WAT_sources': MODULES}


if __name__ == '__main__':
    encoded = json.dumps(run(), indent=2)
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(encoded + '\n', encoding='utf-8')
    else:
        print(encoded)
