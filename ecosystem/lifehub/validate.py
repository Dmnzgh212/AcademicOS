"""Common installed-wheel lifecycle acceptance for three domains; no Core changes."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import PLUGINS, build  # noqa: E402


def validate(repo):
    import academicos
    from academicos.lifehub.kernel import LifeHub

    repo = Path(repo).resolve()
    if Path(academicos.__file__).resolve().is_relative_to(repo):
        raise RuntimeError('requires a non-editable wheel outside the source checkout')
    results = []
    with tempfile.TemporaryDirectory(prefix='lifehub-ecosystem-') as directory:
        work = Path(directory)
        archives = build(work / 'packages')
        hub = LifeHub(db_path=work / 'hub.db', plugins_path=work / 'installed')
        try:
            for archive in archives:
                hub.packages.install(archive, approved_hash=hub.packages.review(archive).content_hash)

            def process(script, *args, incoming=None, success=True):
                result = subprocess.run([sys.executable, '-I', str(script), *map(str, args)],
                                        cwd=work, text=True, input=incoming, capture_output=True,
                                        timeout=60)
                if success and result.returncode:
                    raise RuntimeError(result.stderr)
                if not success and (result.returncode == 0 or result.stdout):
                    raise RuntimeError('invalid operation succeeded or leaked stdout')
                return result.stdout

            catalog = json.dumps(hub.catalog())
            assert len(hub.catalog()['packages']) == 4
            rendered = process(repo / 'examples/lifehub/catalog_shell/shell.py', incoming=catalog)
            for domain in PLUGINS:
                assert f'ecosystem.{domain}' in rendered

            for domain, (_, namespace, fields) in PLUGINS.items():
                plugin = f'ecosystem.{domain}'
                target = f'{plugin}:describe'
                old_store = hub.scoped_store(plugin)
                for operation in [lambda: old_store.read(namespace),
                                  lambda: hub.run_wasm(f'{plugin}:read'),
                                  lambda: hub.call_service('ecosystem.consumer', target,
                                                          {'operation': 'describe'})]:
                    try:
                        operation()
                    except PermissionError:
                        pass
                    else:
                        raise AssertionError('requested capability already had authority')
                args = [domain, '--db', work / 'hub.db', '--installed', work / 'installed',
                        '--approve-ingest']
                if domain != 'system':
                    fixture = 'academic.csv' if domain == 'academic' else 'feed.xml'
                    args += ['--source', repo / 'ecosystem/lifehub/fixtures' / fixture]
                process(repo / 'ecosystem/lifehub/operator.py', *args)
                hub.grant_read(plugin, namespace)
                assert hub.run_wasm(f'{plugin}:read') > 0
                records = hub.read_records(plugin, namespace)
                assert records['records']
                for row in records['records']:
                    assert set(row['payload']) == set(fields)
                    assert row['source'].startswith('operator:')
                process(repo / 'examples/lifehub/records_shell/shell.py',
                        incoming=json.dumps(records))
                contract = 'lifehub.service-json@1'
                review = hub.review_service('ecosystem.consumer', target, contract)
                hub.grant_service('ecosystem.consumer', target, contract,
                                  approved_digest=review['approval_digest'])
                expected = {'api': f'ecosystem.{domain}-schema@1', 'namespace': namespace,
                            'fields': fields}
                assert hub.call_service('ecosystem.consumer', target,
                                        {'operation': 'describe'}) == expected
                assert hub.run_wasm(f'ecosystem.consumer:{domain}') > 0
                try:
                    hub.call_service('ecosystem.consumer', target, {'operation': 'unknown'})
                except ValueError:
                    pass
                else:
                    raise AssertionError('descriptor accepted unsupported operation')
                hub.revoke_read(plugin, namespace)
                hub.revoke_service('ecosystem.consumer', target, contract)
                for operation in [lambda: old_store.read(namespace),
                                  lambda: hub.read_records(plugin, namespace),
                                  lambda: hub.run_wasm(f'{plugin}:read'),
                                  lambda: hub.run_wasm(f'ecosystem.consumer:{domain}')]:
                    try:
                        operation()
                    except PermissionError:
                        pass
                    else:
                        raise AssertionError('revoked capability still usable')
                hub.grant_read(plugin, namespace)
                review = hub.review_service('ecosystem.consumer', target, contract)
                hub.grant_service('ecosystem.consumer', target, contract,
                                  approved_digest=review['approval_digest'])
                tamper = work / 'installed' / plugin / 'tampered.txt'
                tamper.write_text('controlled tamper')
                try:
                    hub.run_wasm(f'{plugin}:read')
                except PermissionError:
                    pass
                else:
                    raise AssertionError('tampered package executed')
                tamper.unlink()
                hub.packages.uninstall(plugin)
                assert plugin not in [p['id'] for p in hub.catalog()['packages']]
                assert not hub.store.grants(plugin)
                for grant in hub.store.grants('ecosystem.consumer'):
                    assert target not in grant['resource']
                for operation in [lambda: old_store.read(namespace),
                                  lambda: hub.run_wasm(f'{plugin}:read'),
                                  lambda: hub.run_wasm(f'ecosystem.consumer:{domain}')]:
                    try:
                        operation()
                    except (PermissionError, KeyError):
                        pass
                    else:
                        raise AssertionError('uninstalled authority still usable')
                results.append({'plugin': plugin, 'status': 'PASS',
                                'source': 'live minimal system snapshot' if domain == 'system'
                                          else 'real-format synthetic fixture',
                                'records': len(records['records'])})
        finally:
            hub.close()
    return {'status': 'PASS', 'core_changes': False, 'plugins': results,
            'live_user_academic_and_rss_acceptance': 'pending user-selected files'}


if __name__ == '__main__':
    print(json.dumps(validate(sys.argv[1]), indent=2))
