"""Domain adapter/contract tests; platform runtime remains unchanged."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'ecosystem/lifehub' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adapters = load('adapters')
builder = load('build')


def test_academic_real_format_fixture():
    rows = adapters.academic(ROOT / 'ecosystem/lifehub/fixtures/academic.csv')
    assert len(rows) == 2
    assert rows[0]['course'] == 'CSI2110'
    assert rows[0]['due'].endswith('-04:00')


@pytest.mark.parametrize('text', [
    'course,title,due\nCSI2110,Lab,2026-10-08T23:59:00\n',
    'course,title,due\nCSI2110,,2026-10-08T23:59:00-04:00\n',
    'title,course,due\nLab,CSI2110,2026-10-08T23:59:00-04:00\n',
])
def test_academic_rejects_ambiguous_or_invalid_source(tmp_path, text):
    source = tmp_path / 'source.csv'
    source.write_text(text)
    with pytest.raises(ValueError):
        adapters.academic(source)


def test_rss_real_format_fixture():
    rows = adapters.rss(ROOT / 'ecosystem/lifehub/fixtures/feed.xml')
    assert rows == [{'title': 'Example article', 'link': 'https://example.com/article',
                     'guid': 'fixture-one', 'published': None}]


@pytest.mark.parametrize('text', [
    '<!DOCTYPE rss [<!ENTITY x "example">]><rss version="2.0"><channel/></rss>',
    '<feed xmlns="http://www.w3.org/2005/Atom"/>',
    '<rss version="2.0"><channel><item><link>https://example.com</link></item></channel></rss>',
])
def test_rss_rejects_unsupported_or_invalid_source(tmp_path, text):
    source = tmp_path / 'feed.xml'
    source.write_text(text)
    with pytest.raises(ValueError):
        adapters.rss(source)


def test_system_snapshot_deliberately_omits_personal_identifiers():
    rows = adapters.system_snapshot()
    assert len(rows) == 1
    assert set(rows[0]) == {'os', 'release', 'architecture', 'python'}
    assert all(isinstance(value, str) for value in rows[0].values())


@pytest.mark.parametrize('domain', builder.PLUGINS)
def test_domain_descriptor_service_contract(domain):
    wasmtime = pytest.importorskip('wasmtime')
    from academicos.lifehub.service_runtime import run_json_service

    _, namespace, fields = builder.PLUGINS[domain]
    expected = {'api': f'ecosystem.{domain}-schema@1', 'namespace': namespace, 'fields': fields}
    wasm = wasmtime.wat2wasm(builder.descriptor(json.dumps(expected, separators=(',', ':')).encode()))
    assert run_json_service(wasm, {'operation': 'describe'}) == expected
    with pytest.raises(ValueError, match='nonzero status'):
        run_json_service(wasm, {'operation': 'unknown'})
