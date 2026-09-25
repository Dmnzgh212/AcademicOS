import typer

app = typer.Typer(help="AcademicOS local academic planning system.")


@app.command()
def status() -> None:
    """Show bootstrap status."""
    typer.echo("AcademicOS bootstrap: Calendar v0.1 is the current target.")


@app.command()
def sync() -> None:
    """Placeholder for future source synchronization."""
    typer.echo("Source sync is not implemented yet.")


@app.command()
def week() -> None:
    """Placeholder for the local weekly calendar view."""
    typer.echo("Calendar engine is not implemented yet.")


if __name__ == "__main__":
    app()
