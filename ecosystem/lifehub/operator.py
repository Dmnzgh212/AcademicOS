"""Explicit operator ingress from selected local sources; never an executable guest."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapters import academic, rss, system_snapshot  # noqa: E402
from build import PLUGINS  # noqa: E402


def main():
    from academicos.lifehub.kernel import LifeHub

    parser = argparse.ArgumentParser()
    parser.add_argument('domain', choices=PLUGINS)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--approve-ingest', action='store_true', required=True)
    args = parser.parse_args()
    if args.domain == 'system':
        if args.source is not None:
            parser.error('system snapshot takes no file')
        records = system_snapshot()
        provenance = 'operator:system-snapshot'
    else:
        if args.source is None:
            parser.error('academic/RSS requires an explicitly selected local source file')
        records = (academic if args.domain == 'academic' else rss)(args.source)
        provenance = f'operator:{args.domain}:selected-local-file'
    hub = LifeHub(db_path=args.db, plugins_path=args.installed)
    try:
        hub.bundle(f'ecosystem.{args.domain}')
        namespace = PLUGINS[args.domain][1]
        for record in records:
            key = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
            # Trusted operator ingress is intentionally distinct from guest authority.
            hub.store.append_record(plugin_id='operator.ingress', namespace=namespace,
                                    record_key=key, payload=record, source=provenance)
        print(json.dumps({'namespace': namespace, 'selected_records': len(records)}))
    finally:
        hub.close()


if __name__ == '__main__':
    main()
