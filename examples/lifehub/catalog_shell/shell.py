"""Independent, metadata-only shell for lifehub.catalog@1 JSON on stdin."""

from __future__ import annotations

import argparse
import html
import json
import sys

MAX_CATALOG_BYTES = 1024 * 1024


def validate_catalog(catalog: object) -> dict:
    """Validate fields this shell consumes; preserve unknown protocol fields."""
    if not isinstance(catalog, dict):
        raise ValueError("catalog must be an object")
    if catalog.get("api") != "lifehub.catalog@1":
        raise ValueError("unsupported catalog API")
    for key, required, optional in (
        ("packages", ("id", "name"), ()),
        ("extensions", ("ref", "plugin_id", "point"), ("contract", "entrypoint")),
    ):
        items = catalog.get(key)
        if not isinstance(items, list):
            raise ValueError(f"catalog {key} must be an array")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"catalog {key} entries must be objects")
            if any(not isinstance(item.get(field), str) for field in required):
                raise ValueError(f"catalog {key} required fields must be strings")
            if any(item.get(field) is not None and not isinstance(item[field], str)
                   for field in optional):
                raise ValueError(f"catalog {key} optional fields must be strings or null")
    return catalog


def render(catalog: dict, *, style: str = "text") -> str:
    catalog = validate_catalog(catalog)
    packages = catalog["packages"]
    extensions = catalog["extensions"]
    names = {item["id"]: item["name"] for item in packages}
    rows = [
        (
            item["ref"],
            names.get(item["plugin_id"], item["plugin_id"]),
            item["point"],
            item.get("contract") or "legacy",
            item.get("entrypoint") or "declarative",
        )
        for item in extensions
    ]
    if style == "text":
        # JSON quoting prevents untrusted metadata from becoming terminal controls.
        lines = [f"LifeHub catalog: {len(packages)} packages, {len(rows)} extensions"]
        lines.extend(
            " | ".join(json.dumps(cell, ensure_ascii=False) for cell in row) for row in rows
        )
        return "\n".join(lines)
    if style != "html":
        raise ValueError("unsupported shell style")
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'\">"
        "<title>LifeHub plugin catalog</title></head><body><h1>Plugin catalog</h1>"
        f"<p>{len(packages)} packages · {len(rows)} extensions</p>"
        "<table><thead><tr><th>Reference</th><th>Package</th><th>Point</th>"
        "<th>Contract</th><th>Entrypoint</th></tr></thead>"
        f"<tbody>{body}</tbody></table></body></html>"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--style", choices=("text", "html"), default="text")
    args = parser.parse_args()
    raw = sys.stdin.buffer.read(MAX_CATALOG_BYTES + 1)
    try:
        if len(raw) > MAX_CATALOG_BYTES:
            raise ValueError("catalog exceeds shell input limit")
        output = render(json.loads(raw.decode("utf-8")), style=args.style)
    except (ValueError, RecursionError):
        # Keep untrusted input and Python internals out of diagnostics.
        print("Invalid or unsupported LifeHub catalog", file=sys.stderr)
        sys.exit(2)
    print(output)
