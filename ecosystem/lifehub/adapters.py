"""Domain adapters run explicitly by a trusted local operator, never by the guest."""

import csv
from datetime import datetime
import io
from pathlib import Path
import platform
import xml.etree.ElementTree as ET

MAX_SOURCE_BYTES = 1024 * 1024
MAX_RECORDS = 100


def source_text(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError('source exceeds 1 MiB')
    return raw.decode('utf-8-sig')


def academic(path):
    reader = csv.DictReader(io.StringIO(source_text(path)))
    if reader.fieldnames != ['course', 'title', 'due']:
        raise ValueError('expected CSV columns course,title,due')
    records = []
    for row in reader:
        if len(records) >= MAX_RECORDS or set(row) != {'course', 'title', 'due'}:
            raise ValueError('invalid or excessive academic records')
        if any(not isinstance(value, str) or not value.strip() for value in row.values()):
            raise ValueError('academic fields must be nonempty')
        due = datetime.fromisoformat(row['due'])
        if due.utcoffset() is None:
            raise ValueError('deadline must include a timezone offset')
        records.append({'course': row['course'].strip(), 'title': row['title'].strip(),
                        'due': due.isoformat()})
    return records


def rss(path):
    text = source_text(path)
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('RSS document declarations are not supported')
    root = ET.fromstring(text)
    if root.tag != 'rss' or root.get('version') != '2.0' or root.find('channel') is None:
        raise ValueError('expected RSS 2.0 channel; Atom/RDF not supported')
    records = []
    for item in root.findall('./channel/item'):
        if len(records) >= MAX_RECORDS:
            raise ValueError('too many feed items')
        title, link = (item.findtext('title') or '').strip(), (item.findtext('link') or '').strip()
        if not title or not link.startswith(('https://', 'http://')):
            raise ValueError('RSS item needs a title and HTTP(S) link')
        records.append({'title': title, 'link': link, 'guid': item.findtext('guid') or link,
                        'published': item.findtext('pubDate')})
    return records


def system_snapshot():
    # Deliberately omit hostname, usernames, process lists, paths and environment variables.
    return [{'os': platform.system(), 'release': platform.release(),
             'architecture': platform.machine(), 'python': platform.python_version()}]
