"""Engineering-only extracted-kit smoke, including real interactive authority lifecycle."""
import argparse
from pathlib import Path
import subprocess
import sys


def verify(root, python, launcher=False):
    subprocess.run([python, str(root / 'check_kit.py')], check=True)
    commands = '1\nyes\n3\nBeforeGrant9\n\n2\nyes\n3\nLecture 10\nLecture 2\nLecture 1\n\n4\n3\nAfterRevoke9\n\n5\nyes\n1\nyes\n3\nAfterReinstall9\n\n5\nyes\n0\n'
    command = ['cmd', '/c', str(root / 'Start.cmd')] if launcher else [
        python, '-X', 'utf8', str(root / 'menu.py')]
    result = subprocess.run(command, input=commands, text=True, encoding='utf-8',
                            capture_output=True, timeout=180)
    if result.returncode or 'Lecture 1\nLecture 2\nLecture 10\n' not in result.stdout:
        raise RuntimeError('kit launch/output smoke failed')
    if result.stdout.count('LHSORT_OPERATION_FAILED') != 3:
        raise RuntimeError('grant/revoke/reinstall denial smoke failed')
    if 'Removed.' not in result.stdout or 'Traceback' in result.stdout + result.stderr:
        raise RuntimeError('kit cleanup/diagnostic smoke failed')
    print('Extracted kit: offline launch, menu, grant, revoke and reinstall denial PASS')
    target = root / 'packages' / 'provider.lhpkg'
    original = target.read_bytes()
    try:
        target.write_bytes(original + b'tampered')
        rejected = subprocess.run([python, str(root / 'check_kit.py')], capture_output=True)
        if rejected.returncode == 0 or b'LHSORT_KIT_INVALID' not in rejected.stderr:
            raise RuntimeError('tampered kit was accepted')
    finally:
        target.write_bytes(original)
    print('Bundle tamper rejection PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--launcher', action='store_true')
    args = parser.parse_args()
    verify(args.root.resolve(), args.python, args.launcher)
