from pathlib import Path
from typing import Annotated

import typer

from pad.app import run
from pad.license import check_license

app = typer.Typer(
    name="pad",
    help="A command-line code editor.",
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main(
    path: Path = typer.Argument(default=Path(".")),
    license_key: Annotated[
        str | None,
        typer.Option("--license-key", help="Provide a license key for activation"),
    ] = None,
) -> None:
    """Launch the Pad code editor."""
    if not check_license(license_key):
        raise typer.Exit(1)
    run(path.resolve())
