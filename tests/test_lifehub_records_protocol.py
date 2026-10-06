import json

import pytest
from typer.testing import CliRunner

from academicos.lifehub.cli import app
from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.web import _extension_body
from test_lifehub import _write_plugin


def test_records_contract_checks_authority_and_returns_detached_data(tmp_path):
    root = tmp_path / 'plugins'
    _write_plugin(root, folder='producer', plugin_id='demo.producer', writes='finance')
    _write_plugin(root, folder='consumer', plugin_id='demo.consumer', writes='consumer',
                  reads='finance')
    hub = LifeHub(db_path=tmp_path / 'hub.db', plugins_path=root)
    try:
        hub.seed_declared_data()
        with pytest.raises(PermissionError):
            hub.read_records('demo.consumer', 'finance.today')
        hub.grant_read('demo.consumer', 'finance')
        data = hub.read_records('demo.consumer', 'finance.today')
        assert data['api'] == 'lifehub.records@1'
        data['records'][0]['payload']['items'].clear()
        assert hub.read_records('demo.consumer', 'finance.today')['records'][0]['payload']['items']
        for limit in (0, -1, 101, True, '8'):
            with pytest.raises(ValueError, match='record limit'):
                hub.read_records('demo.consumer', 'finance.today', limit=limit)
        with pytest.raises(ValueError, match='unsupported records API'):
            hub.read_records('demo.consumer', 'finance.today', api='lifehub.records@2')
        hub.revoke_read('demo.consumer', 'finance')
        with pytest.raises(PermissionError):
            hub.read_records('demo.consumer', 'finance.today')
    finally:
        hub.close()


def test_cli_and_web_consume_records_contract(tmp_path, monkeypatch):
    root, db = tmp_path / 'plugins', tmp_path / 'hub.db'
    _write_plugin(root)
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        hub.seed_declared_data()
        calls = []
        read = hub.read_records

        def read_spy(*args, **kwargs):
            calls.append((args, kwargs))
            return read(*args, **kwargs)

        monkeypatch.setattr(hub, 'read_records', read_spy)
        assert 'Local item' in _extension_body(hub, hub.extension('demo.sample:main'))
        assert calls[0][0] == ('demo.sample', 'sample.today')
        monkeypatch.setattr(hub, 'read_records', lambda *a, **kw: (_ for _ in ()).throw(
            PermissionError('denied')))
        assert 'Record access is not granted' in _extension_body(
            hub, hub.extension('demo.sample:main'))
    finally:
        hub.close()
    result = CliRunner().invoke(app, ['records', 'demo.sample', 'sample.today',
                                     '--db', str(db), '--plugins', str(root)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)['records'][0]['payload']['items']
