"""The ``g3mt`` command-line interface.

A thin shell over the core library: it parses arguments, handles the
interactive path prompt, renders results, and maps outcomes to exit codes. All
real work lives in the library so the same logic can back a future UI.

Exit codes: 0 = success, 1 = validation problems found, 2 = usage/input error.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from gen3_metadata_templates import __version__
from gen3_metadata_templates.constants import DEFAULT_EXCLUDED_NODES
from gen3_metadata_templates.errors import G3mtError
from gen3_metadata_templates.model import build_template_spec
from gen3_metadata_templates.paths import enumerate_paths, resolve_path
from gen3_metadata_templates.schema import SchemaBundle
from gen3_metadata_templates.validation.report import render_console, to_json
from gen3_metadata_templates.validation.runner import validate_workbook
from gen3_metadata_templates.workbook.annotate import write_annotated_copy
from gen3_metadata_templates.workbook.writer import write_template

app = typer.Typer(
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=True,
    help=(
        "[bold]g3mt[/] — build and check Gen3 metadata submission templates.\n\n"
        "A Gen3 schema is a graph of node types (subject, sample, file, ...) linked "
        "parent-to-child. You pick a [bold]target node[/]; g3mt generates an Excel "
        "workbook with one sheet per node on the path from the root down to it, with "
        "dropdowns and guidance so filling it in is hard to get wrong. When you're "
        "done, [bold]g3mt validate[/] checks the file and tells you exactly which cell "
        "to fix.\n\n"
        "[bold]Examples[/]\n"
        "  g3mt generate schema.json sample -o sample_template.xlsx\n"
        "  g3mt generate schema.json sample --path 2 --exclude-node acknowledgement\n"
        "  g3mt validate sample_template.xlsx -s schema.json --annotate checked.xlsx"
    ),
)

err_console = Console(stderr=True)
console = Console()


def _effective_excluded(include_node: List[str], exclude_node: List[str],
                        no_default_excludes: bool) -> List[str]:
    excluded = set() if no_default_excludes else set(DEFAULT_EXCLUDED_NODES)
    excluded.difference_update(include_node or [])
    excluded.update(exclude_node or [])
    return sorted(excluded)


def _interactive_chooser(paths: List[List[str]]) -> int:
    """Prompt the user to choose a path (only used when attached to a terminal)."""
    err_console.print(
        f"\n[bold]Multiple paths lead to '{paths[0][-1]}'.[/] "
        "Choose one — it decides which sheets your template contains:\n"
    )
    for i, path in enumerate(paths, start=1):
        arrows = " [dim]->[/] ".join(path[:-1] + [f"[bold]{path[-1]}[/]"])
        err_console.print(f"  {i}. {arrows}   [dim]({len(path) - 1} steps)[/]")
    choice = typer.prompt("\nPath number", default="1")
    try:
        idx = int(choice) - 1
    except ValueError:
        raise typer.BadParameter(f"'{choice}' is not a path number.")
    if not 0 <= idx < len(paths):
        raise typer.BadParameter(f"Choose a number between 1 and {len(paths)}.")
    return idx


def _choose_path(bundle, target, path_arg, excluded) -> List[str]:
    """Resolve a path, prompting interactively only when a TTY is available."""
    paths = enumerate_paths(bundle, target, excluded)
    if len(paths) == 1:
        return paths[0]
    if path_arg is None and not (sys.stdin.isatty() and sys.stdout.isatty()):
        # Non-interactive and ambiguous: show options and fail clearly.
        err_console.print(f"[red]Node '{target}' has multiple paths:[/]")
        for i, path in enumerate(paths, start=1):
            err_console.print(f"  {i}. {' -> '.join(path)}")
        err_console.print("Re-run with --path N (see numbers above).")
        raise typer.Exit(2)
    chooser = None if path_arg is not None else _interactive_chooser
    return resolve_path(paths, path_arg=path_arg, chooser=chooser)


@app.command()
def generate(
    schema: Path = typer.Argument(..., exists=True, dir_okay=False,
                                  help="Path to the Gen3 JSON schema bundle."),
    target_node: str = typer.Argument(..., help="The node you want to submit data for."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", rich_help_panel="Output",
        help="Where to write the .xlsx (default: <target_node>_template.xlsx)."),
    rows: int = typer.Option(
        5000, "--rows", rich_help_panel="Output",
        help="Number of blank data rows to provision per sheet."),
    force: bool = typer.Option(
        False, "--force", rich_help_panel="Output",
        help="Overwrite the output file if it already exists."),
    path: Optional[str] = typer.Option(
        None, "--path", rich_help_panel="Path selection",
        help="Choose among multiple paths: a number (e.g. 2) or a node chain "
             "(e.g. subject,visit,sample)."),
    list_paths: bool = typer.Option(
        False, "--list-paths", rich_help_panel="Path selection",
        help="Print the numbered paths to the target node and exit."),
    include_node: List[str] = typer.Option(
        [], "--include-node", rich_help_panel="Node & column filters",
        help="Re-include a node excluded by default (e.g. --include-node project)."),
    exclude_node: List[str] = typer.Option(
        [], "--exclude-node", rich_help_panel="Node & column filters",
        help="Exclude an extra node from the template."),
    exclude_column: List[str] = typer.Option(
        [], "--exclude-column", rich_help_panel="Node & column filters",
        help="Exclude an extra property column from every sheet."),
    no_default_excludes: bool = typer.Option(
        False, "--no-default-excludes", rich_help_panel="Node & column filters",
        help="Keep the normally-excluded nodes (program, project, "
             "core_metadata_collection, acknowledgement)."),
):
    """Generate an Excel template for a target node.

    g3mt builds one sheet per node on the path from the schema's root down to
    your target node, with dropdowns for parent links and controlled values.
    """
    from gen3_metadata_templates.constants import DEFAULT_EXCLUDED_COLUMNS

    with _handle_errors():
        bundle = SchemaBundle(schema)
        excluded = _effective_excluded(include_node, exclude_node, no_default_excludes)

        if list_paths:
            paths = enumerate_paths(bundle, target_node, excluded)
            for i, p in enumerate(paths, start=1):
                console.print(f"{i}. {' -> '.join(p)}")
            raise typer.Exit(0)

        chosen = _choose_path(bundle, target_node, path, excluded)
        columns = list(DEFAULT_EXCLUDED_COLUMNS) + list(exclude_column)
        spec = build_template_spec(
            bundle, target_node, chosen,
            excluded_nodes=excluded, excluded_columns=columns,
        )

        out_path = output or Path(f"{target_node}_template.xlsx")
        if out_path.exists() and not force:
            err_console.print(
                f"[red]{out_path} already exists.[/] Use --force to overwrite."
            )
            raise typer.Exit(2)

        write_template(spec, out_path, data_rows=rows)
        console.print(
            f"[green]Wrote[/] {out_path}  "
            f"[dim]({len(spec.nodes)} sheet(s): {' -> '.join(n.node for n in spec.nodes)})[/]"
        )


@app.command()
def validate(
    workbook: Path = typer.Argument(..., exists=True, dir_okay=False,
                                    help="The filled .xlsx template to check."),
    schema: Path = typer.Option(..., "--schema", "-s", exists=True, dir_okay=False,
                                help="Path to the Gen3 JSON schema bundle."),
    annotate: Optional[Path] = typer.Option(
        None, "--annotate", help="Write a copy with the problem cells highlighted."),
    json_out: bool = typer.Option(
        False, "--json", help="Print the report as JSON instead of tables."),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Also show the raw underlying error messages."),
    path: Optional[str] = typer.Option(
        None, "--path", help="Node path, if the workbook has no g3mt metadata."),
):
    """Validate a filled template and report problems by sheet, row, and column."""
    with _handle_errors():
        report = validate_workbook(workbook, schema, path_arg=path)

        if json_out:
            console.print_json(json.dumps(to_json(report)))
        else:
            render_console(report, console, verbose=verbose)

        if annotate is not None:
            write_annotated_copy(workbook, report, annotate)
            console.print(f"[green]Wrote annotated copy[/] {annotate}")

        raise typer.Exit(0 if report.ok else 1)


@app.command()
def nodes(
    schema: Path = typer.Argument(..., exists=True, dir_okay=False,
                                  help="Path to the Gen3 JSON schema bundle."),
):
    """List the nodes in a schema, with their links."""
    with _handle_errors():
        bundle = SchemaBundle(schema)
        table = Table(header_style="bold")
        table.add_column("Node")
        table.add_column("Links to")
        for node in bundle.node_names:
            targets = ", ".join(sorted({link.target_type for link in bundle.links(node)}))
            table.add_row(node, targets or "[dim]-[/]")
        console.print(table)


@app.command()
def paths(
    schema: Path = typer.Argument(..., exists=True, dir_okay=False,
                                  help="Path to the Gen3 JSON schema bundle."),
    target_node: str = typer.Argument(..., help="The node to enumerate paths to."),
):
    """Show the numbered paths from the root to a target node."""
    with _handle_errors():
        bundle = SchemaBundle(schema)
        for i, p in enumerate(enumerate_paths(bundle, target_node, DEFAULT_EXCLUDED_NODES), start=1):
            console.print(f"{i}. {' -> '.join(p)}")


@app.command()
def version():
    """Print the g3mt version."""
    console.print(__version__)


class _handle_errors:
    """Context manager: turn expected G3mtErrors into a clean exit code 2."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            return False
        if issubclass(exc_type, typer.Exit) or issubclass(exc_type, typer.Abort):
            return False
        if issubclass(exc_type, G3mtError):
            err_console.print(f"[red]Error:[/] {exc}")
            raise typer.Exit(2)
        return False


def main() -> None:
    app()


if __name__ == "__main__":
    main()
