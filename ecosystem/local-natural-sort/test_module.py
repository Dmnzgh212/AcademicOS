"""Bounded guest computation and adversarial input, not a Core modification."""
import json
import zipfile

import pytest

from academicos.lifehub.service_runtime import run_json_service
from build import build


@pytest.fixture(scope='module')
def module(tmp_path_factory):
    provider, _ = build(tmp_path_factory.mktemp('sort-packages'))
    with zipfile.ZipFile(provider) as archive:
        return archive.read('sort.wasm')


@pytest.mark.parametrize('labels,expected', [
    (['Lecture 10', 'Lecture 2', 'Lecture 1'], ['Lecture 1', 'Lecture 2', 'Lecture 10']),
    (['file 1.010', 'file 1.02', 'file 1.001'], ['file 1.001', 'file 1.010', 'file 1.02']),
    ([], []), (['same', 'same'], ['same', 'same']),
    (['a"10', 'a"2', 'a\\1'], ['a"2', 'a"10', 'a\\1']),
    (['a10'] * 16, ['a10'] * 16), (['x' * 64], ['x' * 64]),
])
def test_real_guest_sort(module, labels, expected):
    assert run_json_service(module, labels) == expected


@pytest.mark.parametrize('payload', [{}, [1], [None], [['nested']], ['x'] * 17,
                                    ['x' * 65], ['中文'], ['line\nbreak'], ['\x00']])
def test_invalid_input_releases_no_result(module, payload):
    with pytest.raises(ValueError, match='nonzero status'):
        run_json_service(module, payload)


def test_build_repeat_is_byte_identical(tmp_path):
    one, two = build(tmp_path / 'one'), build(tmp_path / 'two')
    assert [p.read_bytes() for p in one] == [p.read_bytes() for p in two]
    inventory = json.loads((tmp_path / 'one/package-hashes.json').read_text())
    assert set(inventory) == {'provider.lhpkg', 'client.lhpkg'}


def test_maximum_reversed_long_prefix_stays_within_host_fuel(module):
    labels = ['x' * 60 + str(i) for i in range(15, -1, -1)]
    assert run_json_service(module, labels) == list(reversed(labels))
