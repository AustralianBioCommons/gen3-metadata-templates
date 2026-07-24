"""Orchestrate validation of a filled workbook.

Pulls the pieces together: load the schema, recover (or resolve) the node path,
parse the workbook, then run gen3_validator's per-object schema checks and
cross-node link checks, plus a duplicate-key check. Every raw error is mapped
back to the cell it came from and rephrased for a non-developer.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Union

from gen3_validator.bulk import build_identifier_index, extract_links, validate_record_links
from gen3_validator.validate import validate_list_dict

from gen3_metadata_templates.constants import (
    DEFAULT_EXCLUDED_COLUMNS,
    DEFAULT_EXCLUDED_NODES,
    PRIMARY_KEY,
)
from gen3_metadata_templates.model import NodeTemplate, TemplateSpec, build_template_spec
from gen3_metadata_templates.paths import Chooser, enumerate_paths, resolve_path
from gen3_metadata_templates.schema import SchemaBundle
from gen3_metadata_templates.validation.messages import friendly_message
from gen3_metadata_templates.validation.report import Finding, ValidationReport
from gen3_metadata_templates.workbook.reader import ParsedWorkbook, read_meta, read_workbook


def validate_workbook(
    workbook_path: Union[str, Path],
    schema_path: Union[str, Path],
    *,
    path_arg: Optional[str] = None,
    chooser: Optional[Chooser] = None,
    excluded_nodes: Sequence[str] = DEFAULT_EXCLUDED_NODES,
    excluded_columns: Sequence[str] = DEFAULT_EXCLUDED_COLUMNS,
) -> ValidationReport:
    """Validate ``workbook_path`` against ``schema_path`` and return a report."""
    bundle = SchemaBundle(schema_path)

    path = _recover_path(
        bundle, workbook_path, path_arg, chooser, excluded_nodes
    )
    spec = build_template_spec(
        bundle,
        path[-1],
        path,
        excluded_nodes=excluded_nodes,
        excluded_columns=excluded_columns,
    )
    parsed = read_workbook(workbook_path, spec)

    report = ValidationReport(warnings=list(parsed.warnings))
    excluded_set = set(excluded_nodes)

    for node_template in spec.nodes:
        _validate_node(bundle, node_template, spec, parsed, report, excluded_set)

    return report


def _recover_path(
    bundle, workbook_path, path_arg, chooser, excluded_nodes
) -> List[str]:
    """Use the workbook's own metadata to pick the path when possible."""
    meta = read_meta(workbook_path)
    if meta and meta.get("path"):
        recorded = [n for n in str(meta["path"]).split(",") if n]
        if recorded:
            return recorded
        target = meta.get("target_node")
    else:
        target = None

    if target is None:
        # No usable metadata: fall back to the explicit --path node chain.
        if path_arg and "," in path_arg:
            return [n.strip() for n in path_arg.split(",") if n.strip()]
        raise _needs_target()

    paths = enumerate_paths(bundle, target, excluded_nodes)
    return resolve_path(paths, path_arg=path_arg, chooser=chooser)


def _needs_target():
    from gen3_metadata_templates.errors import WorkbookFormatError

    return WorkbookFormatError(
        "This workbook has no g3mt metadata, so the node path can't be recovered. "
        "Re-run with --path node1,node2,... to say which nodes it contains."
    )


def _validation_schema(bundle: SchemaBundle, node_template: NodeTemplate,
                       parsed: ParsedWorkbook, excluded_set: set) -> dict:
    """A copy of the resolved schema with 'required' trimmed to fillable columns.

    A property is only kept as required if the template has a column for it that
    is actually present in the sheet. This prevents guaranteed failures on links
    to excluded parents (whose column was intentionally dropped) and on required
    columns the user deleted (those are reported once, at sheet level, instead).
    """
    resolved = bundle.resolved(node_template.node)
    template_props = {c.prop_name for c in node_template.columns}
    missing = set(parsed.missing_columns.get(node_template.node, []))

    keep = []
    for prop in resolved.get("required", []):
        if prop == "type":
            keep.append(prop)
        elif prop in template_props and prop not in missing:
            keep.append(prop)

    trimmed = dict(resolved)
    trimmed["required"] = keep
    return trimmed


def _validate_node(bundle, node_template, spec, parsed, report, excluded_set) -> None:
    node = node_template.node
    records = parsed.records.get(node, [])
    findings_before = len(report.findings)

    # 1. Missing required columns -> one sheet-level finding each.
    _report_missing_required_columns(node_template, parsed, report)

    # 2. Per-object schema validation.
    schema = _validation_schema(bundle, node_template, parsed, excluded_set)
    for error in validate_list_dict(records, {node: schema}):
        report.findings.append(_to_finding(error, node_template, parsed))

    # 3. Cross-node referential integrity (link targets exist).
    _validate_links(bundle, node_template, spec, parsed, report, excluded_set)

    # 4. Duplicate submitter_id within the sheet.
    _report_duplicate_keys(node_template, parsed, report)

    report.node_counts[node] = (len(records), len(report.findings) - findings_before)


def _report_missing_required_columns(node_template, parsed, report) -> None:
    missing = parsed.missing_columns.get(node_template.node, [])
    for prop in missing:
        col = node_template.column_by_prop(prop)
        if col is None:
            continue
        if col.required:
            report.findings.append(
                Finding(
                    node=node_template.node,
                    sheet=node_template.sheet_name,
                    message=f"The required column '{col.header}' is missing from this sheet.",
                    raw_message=f"required column '{col.header}' absent",
                    validator="missing_column",
                    header=col.header,
                )
            )
        else:
            report.warnings.append(
                f"Optional column '{col.header}' is missing from sheet "
                f"'{node_template.sheet_name}'."
            )


def _validate_links(bundle, node_template, spec, parsed, report, excluded_set) -> None:
    node = node_template.node
    records = parsed.records.get(node, [])
    if not records:
        return

    # Only check links whose parent sheet is part of this template.
    on_path_targets = {nt.node for nt in spec.nodes}
    links = [
        link
        for link in extract_links(bundle.resolved(node))
        if link["target_type"] in on_path_targets
    ]
    if not links:
        return

    index = build_identifier_index(parsed.records)
    warned: set = set()
    for idx, record in enumerate(records):
        for error in validate_record_links(record, idx, node, links, index, warned):
            report.findings.append(_to_finding(error, node_template, parsed))

    for _, name, target in warned:
        report.warnings.append(
            f"Node '{node}' links to '{target}', which has no rows to check against."
        )


def _report_duplicate_keys(node_template, parsed, report) -> None:
    """submitter_id must be unique within a sheet; neither engine call catches this."""
    node = node_template.node
    seen: dict = {}
    for idx, record in enumerate(parsed.records.get(node, [])):
        key = record.get(PRIMARY_KEY)
        if key is None:
            continue
        if key in seen:
            report.findings.append(
                Finding(
                    node=node,
                    sheet=node_template.sheet_name,
                    message=(
                        f"Duplicate submitter_id '{key}' — it was already used on row "
                        f"{seen[key]}. Each row needs a unique submitter_id."
                    ),
                    raw_message=f"duplicate submitter_id '{key}'",
                    validator="duplicate",
                    cell=parsed.coord(node, idx, PRIMARY_KEY),
                    header=PRIMARY_KEY,
                )
            )
        else:
            excel_row = parsed.coord(node, idx, PRIMARY_KEY)
            seen[key] = excel_row.row if excel_row else idx + 1


def _to_finding(error: dict, node_template: NodeTemplate, parsed: ParsedWorkbook) -> Finding:
    node = error["node"]
    index = error.get("index")
    validator = error.get("validator", "")
    raw = error.get("validation_error", "")

    prop = _error_prop(error)
    column = node_template.column_by_prop(prop) if prop else None
    cell = parsed.coord(node, index, prop) if (prop is not None and index is not None) else None

    return Finding(
        node=node,
        sheet=node_template.sheet_name,
        message=friendly_message(error, column),
        raw_message=raw,
        validator=validator,
        cell=cell,
        header=column.header if column else None,
    )


def _error_prop(error: dict) -> Optional[str]:
    """Work out which property an error is about."""
    if error.get("validator") == "required":
        from gen3_metadata_templates.validation.messages import _required_prop

        return _required_prop(error.get("validation_error", "")) or None

    invalid_key = error.get("invalid_key")
    if not invalid_key or invalid_key == "root":
        return None
    return invalid_key.split(".")[0]
