from __future__ import annotations

from pathlib import Path

import typer

from academicos.sources.doctor import run_doctor, write_doctor_report

app = typer.Typer(
    help="Validate AcademicOS locally and against configured read-only source systems.",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main(
    config: Path = typer.Option(Path("config.local.toml"), "--config"),
    live: bool = typer.Option(False, "--live/--local-only"),
    bootstrap_auth: bool = typer.Option(
        False,
        "--bootstrap-auth/--no-bootstrap-auth",
        help="Allow interactive Brightspace/M365 authentication when local auth is missing.",
    ),
    report: Path = typer.Option(
        Path("data/audits/latest-doctor.json"),
        "--report",
        help="Write a redacted machine-readable validation report.",
    ),
) -> None:
    """Run local checks and optional minimal live read-only probes."""
    result = run_doctor(
        config_path=config,
        live=live,
        bootstrap_auth=bootstrap_auth,
    )
    write_doctor_report(result, report)

    for check in result.checks:
        typer.echo(f"{check.status:4}  {check.name:<36} {check.detail}")

    typer.echo(
        f"Doctor complete · failures={result.failures} warnings={result.warnings} · "
        f"report={report}"
    )
    if result.failures:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
