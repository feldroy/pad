from pathlib import Path

import typer

from idios.app import run

app = typer.Typer(
    name="idios",
    help="A command-line code editor.",
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main(path: Path = typer.Argument(default=Path("."))) -> None:
    """Launch the Idios code editor."""
    run(path.resolve())
