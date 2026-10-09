"""Synthetic installed-wheel proof; automatic approvals apply only to these fixtures."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def verify(packages):
    with tempfile.TemporaryDirectory() as temp:
        def call(action, *labels, success=True):
            p = subprocess.run([sys.executable, '-I', str(HERE / 'sort_shell.py'), action,
                                *labels, '--workspace', temp, '--packages', str(packages), '--yes'],
                               text=True, capture_output=True, timeout=40)
            assert (p.returncode == 0) == success, p.stderr
            return p.stdout
        call('import')
        labels = ['Lecture 10.pdf', 'Lecture 2.pdf', 'Lecture 1.pdf']
        call('sort', *labels, success=False)
        call('enable')
        assert call('sort', *labels).splitlines() == ['Lecture 1.pdf', 'Lecture 2.pdf', 'Lecture 10.pdf']
        call('disable')
        call('sort', *labels, success=False)
        call('remove')
        call('import')
        call('sort', *labels, success=False)  # Reinstall does not revive an old grant.
        call('remove')
        print(json.dumps({'status': 'PASS', 'checks': ['pregrant deny', 'sort', 'revoke deny',
                                                     'uninstall/reinstall deny'],
                          'core_changes': False, 'acceptance': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('packages', type=Path)
    verify(parser.parse_args().packages)
