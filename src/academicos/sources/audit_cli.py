from __future__ import annotations

from pathlib import Path

import typer

from academicos.sources.audit_bundle import (
    build_collection_audit,
    default_audit_path,
    write_collection_audit,
)

app = typer.Typer(
    help="Build a shareable sanitized AcademicOS collection diagnostic bundle.",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main(
    config: Path = typer.Option(Path("config.local.toml"), "--config"),
    output: Path | None = typer.Option(None, "--output"),
    live: bool = typer.Option(False, "--live/--local-only"),
    bootstrap_auth: bool = typer.Option(False, "--bootstrap-auth"),
) -> None:
    if not config.exists():
        raise typer.BadParameter(f"config file not found: {config}")
    if bootstrap_auth and not live:
        raise typer.BadParameter("--bootstrap-auth requires --live")

    payload = build_collection_audit(
        config_path=config,
        live=live,
        bootstrap_auth=bootstrap_auth,
    )
    destination = output or default_audit_path(config)
    write_collection_audit(payload, destination)

    summary = payload["doctor"]["summary"]
    counts = payload["database"]["counts"]
    coverage = payload["brightspace_coverage"]
    typer.echo(
        f"Audit bundle written: {destination} · "
        f"doctor_failures={summary['failures']} warnings={summary['warnings']} · "
        f"source_items={counts['source_items']} · coverage_courses={len(coverage)}"
    )
    typer.echo(
        "Safe-to-share scope: diagnostics only; raw academic content, tokens, cookies, "
        "email addresses, grades, and downloaded files are excluded."
    )


if __name__ == "__main__":
    app()
