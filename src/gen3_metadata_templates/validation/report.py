"""The result of validating a workbook: findings, warnings, and how to show them."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from gen3_metadata_templates.workbook.reader import CellRef


@dataclass(frozen=True)
class Finding:
    """One problem found in the workbook, located as precisely as possible."""

    node: str
    sheet: str
    message: str  # friendly, user-facing
    raw_message: str  # original engine message (shown with --verbose)
    validator: str  # "type", "enum", "required", "link", "duplicate", ...
    cell: Optional[CellRef] = None  # exact cell, when known
    header: Optional[str] = None  # the column header, when known

    @property
    def location(self) -> str:
        if self.cell is not None:
            return f"{self.sheet}!{self.cell.a1}"
        return self.sheet


@dataclass
class ValidationReport:
    """Everything validation produced, ready to render or serialise."""

    findings: List[Finding] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    node_counts: Dict[str, Tuple[int, int]] = field(
        default_factory=dict
    )  # node -> (records, findings)

    @property
    def ok(self) -> bool:
        return not self.findings


def to_json(report: ValidationReport) -> dict:
    """A plain-dict form of the report for --json output or a future UI."""
    return {
        "ok": report.ok,
        "findings": [
            {
                "node": f.node,
                "sheet": f.sheet,
                "cell": f.cell.a1 if f.cell else None,
                "location": f.location,
                "header": f.header,
                "validator": f.validator,
                "message": f.message,
                "raw_message": f.raw_message,
            }
            for f in report.findings
        ],
        "warnings": report.warnings,
        "node_counts": {
            node: {"records": r, "findings": n} for node, (r, n) in report.node_counts.items()
        },
    }


def render_console(report: ValidationReport, console, verbose: bool = False) -> None:
    """Render the report to a rich Console: a summary, per-sheet tables, warnings."""
    from rich.panel import Panel
    from rich.table import Table

    total = len(report.findings)
    records = sum(r for r, _ in report.node_counts.values())

    if report.ok:
        console.print(
            Panel.fit(
                f"[bold green]All good[/] — validated {records} record(s), no problems found.",
                border_style="green",
            )
        )
    else:
        sheets = len({f.sheet for f in report.findings})
        console.print(
            Panel.fit(
                f"[bold red]{total} problem(s)[/] across {sheets} sheet(s) in {records} record(s).",
                border_style="red",
            )
        )

    # Group findings by sheet, preserving first-seen sheet order.
    by_sheet: Dict[str, List[Finding]] = {}
    for finding in report.findings:
        by_sheet.setdefault(finding.sheet, []).append(finding)

    for sheet, findings in by_sheet.items():
        table = Table(title=f"Sheet: {sheet}", title_justify="left", header_style="bold")
        table.add_column("Cell", style="cyan", no_wrap=True)
        table.add_column("Column")
        table.add_column("Problem")
        if verbose:
            table.add_column("Detail", style="dim")
        for finding in findings:
            cell = finding.cell.a1 if finding.cell else "-"
            row = [cell, finding.header or "-", finding.message]
            if verbose:
                row.append(finding.raw_message)
            table.add_row(*row)
        console.print(table)

    for warning in report.warnings:
        console.print(f"[yellow]![/] {warning}")

    if not report.ok:
        console.print(
            "\n[dim]Tip: re-run with --annotate fixed.xlsx to get a copy with the "
            "problem cells highlighted.[/]"
        )
