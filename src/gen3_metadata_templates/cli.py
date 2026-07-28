"""The ``g3mt`` command-line interface.

A thin shell over the core library: it parses arguments, handles the
interactive path prompt, renders results, and maps outcomes to exit codes. All
real work lives in the library so the same logic can back a future UI.

Exit codes: 0 = success, 1 = validation problems found, 2 = usage/input error.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from gen3_metadata_templates import __version__
from gen3_metadata_templates.constants import DEFAULT_EXCLUDED_NODES
from gen3_metadata_templates.errors import G3mtError, SelectionError
from gen3_metadata_templates.model import build_multi_template_spec
from gen3_metadata_templates.paths import enumerate_paths, resolve_path
from gen3_metadata_templates.schema import SchemaBundle
from gen3_metadata_templates.selection import resolve_selection
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
        "parent-to-child. You pick the node — or the whole [bold]category[/] — you want "
        "to submit; g3mt generates an Excel workbook with one sheet per node, parents "
        "before children, with dropdowns and guidance so filling it in is hard to get "
        "wrong. When you're done, [bold]g3mt validate[/] checks the file and tells you "
        "exactly which cell to fix.\n\n"
        "[bold]Examples[/]\n"
        "  g3mt categories schema.json\n"
        "  g3mt generate schema.json --category clinical -o clinical_template.xlsx\n"
        "  g3mt generate schema.json sample -o sample_template.xlsx\n"
        "  g3mt validate clinical_template.xlsx -s schema.json --annotate checked.xlsx"
    ),
)

err_console = Console(stderr=True)
console = Console()

# Global CLI state set by the top-level callback and read by _handle_errors.
_state = {"debug": False}


@app.callback()
def _configure(
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show full tracebacks on error and enable verbose (DEBUG) logging.",
    ),
):
    """Shared setup that runs before any command."""
    _state["debug"] = debug
    # Quiet the underlying engine's chatty INFO logs by default; open them up
    # (and everything else) when debugging.
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(level=level)
    logging.getLogger().setLevel(level)


def _effective_excluded(
    include_node: List[str], exclude_node: List[str], no_default_excludes: bool
) -> List[str]:
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
        raise typer.BadParameter(f"'{choice}' is not a path number.") from None
    if not 0 <= idx < len(paths):
        raise typer.BadParameter(f"Choose a number between 1 and {len(paths)}.")
    return idx


def _dedupe(names: List[str]) -> List[str]:
    """Drop blanks and repeats, keeping the order the user gave."""
    seen: List[str] = []
    for name in names:
        cleaned = (name or "").strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _parse_path_overrides(values: List[str], targets: List[str], single_target_mode: bool) -> dict:
    """Turn ``--path`` values into ``{target: choice}``.

    A bare value (``--path 2``) is only unambiguous when there is one target;
    with several, it has to name the node it applies to (``--path sample=2``).
    """
    overrides: dict = {}
    for raw in values:
        text = (raw or "").strip()
        if not text:
            continue
        if "=" in text:
            target, _, choice = text.partition("=")
            overrides[target.strip()] = choice.strip()
        elif single_target_mode and targets:
            overrides[targets[0]] = text
        else:
            raise SelectionError(
                f"--path needs to say which node it applies to when you select more "
                f"than one. Use --path {targets[0] if targets else 'NODE'}={text}."
            )
    return overrides


def _default_filename(category: Optional[str], targets: List[str]) -> str:
    """Work out a sensible output filename for whatever was selected."""
    if category:
        safe = re.sub(r"\W+", "_", category.strip().lower()).strip("_")
        return f"{safe}_template.xlsx"
    if len(targets) == 1:
        return f"{targets[0]}_template.xlsx"
    if len(targets) <= 3:
        return f"{'_'.join(targets)}_template.xlsx"
    return f"{targets[0]}_and_{len(targets) - 1}_more_template.xlsx"


def _print_paths(bundle, targets: List[str], excluded) -> None:
    """Print the numbered paths to each selected node."""
    if len(targets) == 1:
        for i, p in enumerate(enumerate_paths(bundle, targets[0], excluded), start=1):
            console.print(f"{i}. {' -> '.join(p)}")
        return
    for target in targets:
        console.print(f"[bold]{target}[/]")
        candidates = enumerate_paths(bundle, target, excluded)
        for i, p in enumerate(candidates, start=1):
            suffix = (
                "   [dim](shortest — used by default)[/]" if i == 1 and len(candidates) > 1 else ""
            )
            console.print(f"  {i}. {' -> '.join(p)}{suffix}")


def _report_selection(out_path, spec, selection, bundle) -> None:
    """Explain a multi-node template: what's in it, in what order, and what to watch."""
    console.print(f"[green]Wrote[/] {out_path}  [dim]({len(spec.nodes)} sheets)[/]")
    console.print(
        "\n[bold]Fill order[/] [dim](parents before children; sheets at the same "
        "indent are independent)[/]"
    )
    for nt in spec.nodes:
        console.print("  " * (spec.depth.get(nt.node, 0) + 1) + nt.sheet_name)

    table = Table(title="\nPaths used", title_justify="left", header_style="bold")
    table.add_column("Node")
    table.add_column("Path")
    for resolution in selection.resolutions:
        table.add_row(resolution.target, " -> ".join(resolution.path))
    console.print(table)

    for resolution in selection.ambiguous:
        console.print(
            f"\n[yellow]Note:[/] '{resolution.target}' can be reached "
            f"{len(resolution.candidates)} ways; the shortest was used "
            f"({' -> '.join(resolution.path)}).\n"
            f"  To pick another, re-run with --path {resolution.target}=2."
        )

    # A required parent that isn't in the workbook means the submission would be
    # incomplete — worth saying plainly rather than leaving them to find out.
    included = set(spec.node_order)
    for node_name in spec.node_order:
        for link in bundle.links(node_name):
            if link.required and link.target_type not in included:
                console.print(
                    f"\n[yellow]Note:[/] '{node_name}' links to "
                    f"'{link.target_type}', which is not in this template.\n"
                    f"  Ask your data administrator, or add the sheet with "
                    f"--include-node {link.target_type}."
                )

    if selection.skipped:
        console.print(
            f"\n[dim]Skipped {len(selection.skipped)} node(s) excluded by "
            f"--exclude-node: {', '.join(selection.skipped)}.[/]"
        )


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
    schema: str = typer.Argument(
        ..., help="Path or http(s):// URL to the Gen3 JSON schema bundle."
    ),
    target_node: Optional[str] = typer.Argument(
        None,
        help="The node you want to submit data for. Omit it if you use --category or --node.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        rich_help_panel="Output",
        help="Where to write the .xlsx (default: derived from what you selected).",
    ),
    rows: int = typer.Option(
        5000,
        "--rows",
        rich_help_panel="Output",
        help="Number of blank data rows to provision per sheet.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        rich_help_panel="Output",
        help="Overwrite the output file if it already exists.",
    ),
    category: Optional[str] = typer.Option(
        None,
        "--category",
        rich_help_panel="Node selection",
        help="Include every node in this schema category (e.g. --category clinical). "
        "See `g3mt categories SCHEMA`.",
    ),
    node: List[str] = typer.Option(
        [],
        "--node",
        rich_help_panel="Node selection",
        help="Include this node and its ancestors. Repeatable: --node subject --node sample.",
    ),
    path: List[str] = typer.Option(
        [],
        "--path",
        rich_help_panel="Path selection",
        help="Choose among multiple paths: a number (e.g. 2) or a node chain "
        "(e.g. subject,visit,sample). With more than one target, say which node it "
        "applies to: --path sample=2. Repeatable.",
    ),
    list_paths: bool = typer.Option(
        False,
        "--list-paths",
        rich_help_panel="Path selection",
        help="Print the numbered paths to each selected node and exit.",
    ),
    include_node: List[str] = typer.Option(
        [],
        "--include-node",
        rich_help_panel="Node & column filters",
        help="Re-include a node excluded by default (e.g. --include-node project).",
    ),
    exclude_node: List[str] = typer.Option(
        [],
        "--exclude-node",
        rich_help_panel="Node & column filters",
        help="Exclude an extra node from the template.",
    ),
    exclude_column: List[str] = typer.Option(
        [],
        "--exclude-column",
        rich_help_panel="Node & column filters",
        help="Exclude an extra property column from every sheet.",
    ),
    no_default_excludes: bool = typer.Option(
        False,
        "--no-default-excludes",
        rich_help_panel="Node & column filters",
        help="Keep the normally-excluded nodes (program, project, "
        "core_metadata_collection, acknowledgement).",
    ),
):
    """Generate an Excel template, for one node or for many at once.

    Give a target node, or select several at once with --category / --node.
    g3mt works out every ancestor those nodes need, puts one sheet per node in
    the workbook (parents before children), and adds dropdowns for parent links
    and controlled values.
    """
    from gen3_metadata_templates.constants import DEFAULT_EXCLUDED_COLUMNS

    with _handle_errors():
        bundle = SchemaBundle(schema)
        excluded = _effective_excluded(include_node, exclude_node, no_default_excludes)

        explicit = _dedupe(([target_node] if target_node else []) + list(node))
        from_category = bundle.nodes_in_category(category) if category else []
        targets = _dedupe(explicit + from_category)
        if not targets:
            raise SelectionError(
                "Nothing selected. Give a target node, or use --category / --node.\n"
                f"  g3mt generate {schema} subject\n"
                f"  g3mt generate {schema} --category clinical\n"
                f"  g3mt generate {schema} --node subject --node sample\n"
                f"Run `g3mt categories {schema}` to see what categories exist."
            )

        # Single-target mode keeps the original strict behaviour: prompt on a
        # terminal, refuse to guess in a script. Only a multi-node selection
        # falls back to shortest-path-and-report.
        single_target_mode = not category and not node
        overrides = _parse_path_overrides(path, targets, single_target_mode)

        if list_paths:
            _print_paths(bundle, targets, excluded)
            raise typer.Exit(0)

        if single_target_mode:
            chosen = _choose_path(bundle, targets[0], overrides.get(targets[0]), excluded)
            overrides = {targets[0]: ",".join(chosen)}

        selection = resolve_selection(
            bundle,
            targets,
            excluded_nodes=excluded,
            path_overrides=overrides,
            category=category,
            strict_targets=explicit,
        )
        columns = list(DEFAULT_EXCLUDED_COLUMNS) + list(exclude_column)
        spec = build_multi_template_spec(bundle, selection, excluded_columns=columns)

        out_path = output or Path(_default_filename(category, selection.targets))
        if out_path.exists() and not force:
            err_console.print(f"[red]{out_path} already exists.[/] Use --force to overwrite.")
            raise typer.Exit(2)

        write_template(spec, out_path, data_rows=rows)

        if single_target_mode:
            console.print(
                f"[green]Wrote[/] {out_path}  "
                f"[dim]({len(spec.nodes)} sheet(s): {' -> '.join(spec.node_order)})[/]"
            )
        else:
            _report_selection(out_path, spec, selection, bundle)


@app.command()
def validate(
    workbook: Path = typer.Argument(
        ..., exists=True, dir_okay=False, help="The filled .xlsx template to check."
    ),
    schema: str = typer.Option(
        ...,
        "--schema",
        "-s",
        help="Path or http(s):// URL to the Gen3 JSON schema bundle.",
    ),
    annotate: Optional[Path] = typer.Option(
        None, "--annotate", help="Write a copy with the problem cells highlighted."
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Print the report as JSON instead of tables."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Also show the raw underlying error messages."
    ),
    path: Optional[str] = typer.Option(
        None, "--path", help="Node path, if the workbook has no g3mt metadata."
    ),
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
    schema: str = typer.Argument(
        ..., help="Path or http(s):// URL to the Gen3 JSON schema bundle."
    ),
):
    """List the nodes in a schema, with their category and links."""
    with _handle_errors():
        bundle = SchemaBundle(schema)
        table = Table(header_style="bold")
        table.add_column("Node")
        table.add_column("Category")
        table.add_column("Links to")
        for node in bundle.node_names:
            targets = ", ".join(sorted({link.target_type for link in bundle.links(node)}))
            table.add_row(node, bundle.category(node) or "[dim]-[/]", targets or "[dim]-[/]")
        console.print(table)


@app.command()
def categories(
    schema: str = typer.Argument(
        ..., help="Path or http(s):// URL to the Gen3 JSON schema bundle."
    ),
    show_nodes: bool = typer.Option(
        True, "--nodes/--no-nodes", help="List the node names in each category."
    ),
):
    """List the categories in a schema, with how many nodes each contains.

    A category groups related nodes (for example every clinical node). You can
    generate a template for a whole category in one command.
    """
    with _handle_errors():
        bundle = SchemaBundle(schema)
        grouped = bundle.nodes_by_category()

        table = Table(header_style="bold")
        table.add_column("Category")
        table.add_column("Nodes", justify="right")
        if show_nodes:
            table.add_column("Node names")

        for name, members in grouped.items():
            row = [name, str(len(members))]
            if show_nodes:
                row.append(", ".join(members))
            table.add_row(*row)

        uncategorised = bundle.uncategorised_nodes()
        if uncategorised:
            row = ["[dim](no category)[/]", str(len(uncategorised))]
            if show_nodes:
                row.append("[dim]" + ", ".join(uncategorised) + "[/]")
            table.add_row(*row)

        console.print(table)
        if grouped:
            example = "clinical" if "clinical" in grouped else next(iter(grouped))
            console.print(
                "\n[dim]Generate a template for a whole category:[/]\n"
                f"  g3mt generate {schema} --category {example}"
            )


@app.command()
def paths(
    schema: str = typer.Argument(
        ..., help="Path or http(s):// URL to the Gen3 JSON schema bundle."
    ),
    target_node: str = typer.Argument(..., help="The node to enumerate paths to."),
):
    """Show the numbered paths from the root to a target node."""
    with _handle_errors():
        bundle = SchemaBundle(schema)
        for i, p in enumerate(
            enumerate_paths(bundle, target_node, DEFAULT_EXCLUDED_NODES), start=1
        ):
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
            if _state["debug"]:
                # Show the full traceback for diagnosis, but keep exit code 2.
                err_console.print_exception()
                raise typer.Exit(2)
            err_console.print(f"[red]Error:[/] {exc}")
            err_console.print("[dim]Re-run with --debug to see the full traceback.[/]")
            raise typer.Exit(2)
        return False


def main() -> None:
    app()


if __name__ == "__main__":
    main()
