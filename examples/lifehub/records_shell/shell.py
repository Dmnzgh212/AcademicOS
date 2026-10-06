"""Independent text shell for trusted-host lifehub.records@1 JSON exports."""

import json
import sys

MAX_INPUT_BYTES = 1024 * 1024


def render(value):
    if not isinstance(value, dict) or value.get('api') != 'lifehub.records@1':
        raise ValueError('unsupported records export')
    if not isinstance(value.get('namespace'), str) or not isinstance(value.get('plugin_id'), str):
        raise ValueError('invalid records identity')
    rows = value.get('records')
    if not isinstance(rows, list) or len(rows) > 100 or any(not isinstance(x, dict) for x in rows):
        raise ValueError('invalid records rows')
    # JSON quoting keeps metadata and payload text from emitting terminal controls.
    return '\n'.join(json.dumps(item, ensure_ascii=True, allow_nan=False) for item in rows)


if __name__ == '__main__':
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError('input exceeds shell limit')
        output = render(json.loads(raw.decode('utf-8')))
    except (ValueError, RecursionError):
        print('Invalid or unsupported LifeHub records export', file=sys.stderr)
        sys.exit(2)
    if output:
        print(output)
