"""Generate a self-explanatory Excel workbook from a :class:`TemplateSpec`.

Each node becomes a sheet with styled headers, a locked hint row, description
comments, enum dropdowns, and cross-sheet dropdowns for parent links. Two guide
sheets (Instructions, Dictionary) and two hidden sheets (metadata, enum backing
lists) round out the workbook. The writer is the only place that knows the
xlsxwriter API; everything it needs comes from the ColumnSpec model.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

import xlsxwriter

from gen3_metadata_templates import __version__
from gen3_metadata_templates.constants import (
    DEFAULT_DATA_ROWS,
    DICTIONARY_SHEET,
    INSTRUCTIONS_SHEET,
    LIST_SPLIT_CHAR,
    LISTS_SHEET,
    MAX_INLINE_LIST_LEN,
    META_SHEET,
)
from gen3_metadata_templates.model import ColumnKind, ColumnSpec, NodeTemplate, TemplateSpec
from gen3_metadata_templates.workbook.naming import enum_range, named_range


def write_template(
    spec: TemplateSpec,
    output_path: Union[str, Path],
    *,
    data_rows: int = DEFAULT_DATA_ROWS,
    protect_headers: bool = True,
) -> None:
    """Write ``spec`` to an .xlsx workbook at ``output_path``.

    :param data_rows: number of blank, unlocked rows provisioned per node sheet.
    :param protect_headers: lock the header and hint rows so they can't be edited.
    """
    workbook = xlsxwriter.Workbook(str(output_path), {"strings_to_numbers": False})
    fmts = _build_formats(workbook)

    _write_instructions(workbook, spec, fmts)

    lists_sheet = workbook.add_worksheet(LISTS_SHEET)
    lists_sheet.hide()
    lists_state = {"col": 0}  # next free column on the lists sheet

    for node_template in spec.nodes:
        _write_node_sheet(
            workbook,
            node_template,
            spec,
            fmts,
            data_rows,
            protect_headers,
            lists_sheet,
            lists_state,
        )

    _write_dictionary(workbook, spec, fmts)
    _write_meta(workbook, spec, fmts, data_rows)

    workbook.close()


def _build_formats(workbook) -> dict:
    """Create the reusable cell formats once."""
    return {
        "header_required": workbook.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#1F4E78",
                "border": 1,
                "text_wrap": True,
                "valign": "vcenter",
                "locked": True,
            }
        ),
        "header_optional": workbook.add_format(
            {
                "bold": True,
                "font_color": "#1F4E78",
                "bg_color": "#D6DCE4",
                "border": 1,
                "text_wrap": True,
                "valign": "vcenter",
                "locked": True,
            }
        ),
        "hint": workbook.add_format(
            {
                "italic": True,
                "font_size": 9,
                "font_color": "#606060",
                "bg_color": "#F2F2F2",
                "border": 1,
                "locked": True,
            }
        ),
        "data_text": workbook.add_format({"num_format": "@", "locked": False}),
        "data_general": workbook.add_format({"locked": False}),
        "title": workbook.add_format({"bold": True, "font_size": 16}),
        "subtitle": workbook.add_format({"bold": True, "font_size": 12, "font_color": "#1F4E78"}),
        "wrap": workbook.add_format({"text_wrap": True, "valign": "top"}),
        "meta_key": workbook.add_format({"bold": True}),
        "dict_header": workbook.add_format(
            {"bold": True, "font_color": "#FFFFFF", "bg_color": "#1F4E78", "border": 1}
        ),
        "dict_cell": workbook.add_format({"border": 1, "text_wrap": True, "valign": "top"}),
    }


def _hint_text(col: ColumnSpec) -> str:
    """The short type/requirement hint shown under a header."""
    requirement = "required" if col.required else "optional"
    if col.kind is ColumnKind.LINK:
        base = f"link to '{col.link_target}'"
        if col.is_multi:
            base += f'; separate multiple with "{LIST_SPLIT_CHAR}"'
        return f"{base} — {requirement}"
    if col.data_type == "enum":
        return f"pick from list — {requirement}"
    if col.is_multi:
        return f'list, separate with "{LIST_SPLIT_CHAR}" — {requirement}'
    return f"{col.data_type} — {requirement}"


def _comment_text(col: ColumnSpec, spec: TemplateSpec) -> str:
    """The hover comment attached to a header cell."""
    lines: List[str] = []
    if col.description:
        lines.append(col.description)
    lines.append(f"Type: {col.data_type}")
    lines.append("Required" if col.required else "Optional")
    if col.kind is ColumnKind.LINK:
        sheet = _sheet_for_node(spec, col.link_target)
        lines.append(f"Enter a submitter_id from the '{sheet}' sheet.")
    if col.enum:
        lines.append("Allowed: " + ", ".join(col.enum))
    return "\n".join(lines)


def _sheet_for_node(spec: TemplateSpec, node: Optional[str]) -> str:
    nt = spec.node_template(node) if node else None
    return nt.sheet_name if nt else (node or "")


def _write_node_sheet(
    workbook,
    node_template: NodeTemplate,
    spec: TemplateSpec,
    fmts: dict,
    data_rows: int,
    protect_headers: bool,
    lists_sheet,
    lists_state: dict,
) -> None:
    sheet = workbook.add_worksheet(node_template.sheet_name)
    first_data_row = 2  # 0-indexed row 2 == Excel row 3
    last_data_row = first_data_row + data_rows - 1

    for col_idx, col in enumerate(node_template.columns):
        header_fmt = fmts["header_required"] if col.required else fmts["header_optional"]
        sheet.write(0, col_idx, col.header, header_fmt)
        sheet.write(1, col_idx, _hint_text(col), fmts["hint"])
        sheet.write_comment(0, col_idx, _comment_text(col, spec), {"x_scale": 2.2, "y_scale": 1.6})

        # Column width + default (unlocked) data format so submitters can type.
        width = min(max(len(col.header) + 2, 14), 40)
        data_fmt = (
            fmts["data_general"] if col.data_type in ("integer", "number") else fmts["data_text"]
        )
        sheet.set_column(col_idx, col_idx, width, data_fmt)

        _apply_validation(
            workbook,
            sheet,
            col,
            col_idx,
            first_data_row,
            last_data_row,
            spec,
            lists_sheet,
            lists_state,
        )

    # A workbook-scoped name pointing at this sheet's submitter_id column, so
    # child sheets can build cross-sheet dropdowns from it.
    pk_end = first_data_row + data_rows
    workbook.define_name(
        named_range(node_template.node),
        f"='{node_template.sheet_name}'!$A${first_data_row + 1}:$A${pk_end}",
    )

    sheet.freeze_panes(2, 1)
    sheet.autofilter(0, 0, 0, max(len(node_template.columns) - 1, 0))
    if protect_headers:
        sheet.protect()


def _apply_validation(
    workbook,
    sheet,
    col: ColumnSpec,
    col_idx: int,
    first_row: int,
    last_row: int,
    spec: TemplateSpec,
    lists_sheet,
    lists_state: dict,
) -> None:
    """Attach an Excel dropdown to a column where it makes sense."""
    # Foreign-key column -> pick from the parent sheet's submitter_id column.
    if col.kind is ColumnKind.LINK and not col.is_multi:
        parent_nt = spec.node_template(col.link_target)
        if parent_nt is not None:
            parent_sheet = parent_nt.sheet_name
            sheet.data_validation(
                first_row,
                col_idx,
                last_row,
                col_idx,
                {
                    "validate": "list",
                    "source": f"={named_range(col.link_target)}",
                    "error_type": "warning",
                    "error_title": "Unknown ID",
                    "error_message": (
                        f"Pick a submitter_id from the '{parent_sheet}' sheet, or type "
                        f"it if you will add that row later."
                    ),
                },
            )
        return

    # Boolean -> TRUE/FALSE.
    if col.data_type == "boolean":
        sheet.data_validation(
            first_row,
            col_idx,
            last_row,
            col_idx,
            {
                "validate": "list",
                "source": ["TRUE", "FALSE"],
            },
        )
        return

    # Enum (single value only) -> dropdown of allowed values.
    if col.enum and not col.is_multi:
        joined = ",".join(col.enum)
        if len(joined) <= MAX_INLINE_LIST_LEN:
            source = list(col.enum)
        else:
            source = _write_enum_list(lists_sheet, lists_state, workbook, col)
        sheet.data_validation(
            first_row,
            col_idx,
            last_row,
            col_idx,
            {
                "validate": "list",
                "source": source,
                "error_type": "stop",
                "error_title": "Not an allowed value",
                "error_message": "Choose one of the values from the dropdown.",
            },
        )


def _write_enum_list(lists_sheet, lists_state: dict, workbook, col: ColumnSpec) -> str:
    """Write a long enum's values down a hidden column and return its range name.

    Excel rejects an inline dropdown list longer than 255 characters, so long
    enums live on a hidden sheet and are referenced by a defined name.
    """
    col_idx = lists_state["col"]
    for row_idx, value in enumerate(col.enum):
        lists_sheet.write(row_idx, col_idx, value)
    letter = _col_letter(col_idx)
    name = enum_range(col.prop_name, col.header)
    workbook.define_name(name, f"='{LISTS_SHEET}'!${letter}$1:${letter}${len(col.enum)}")
    lists_state["col"] += 1
    return f"={name}"


def _col_letter(index: int) -> str:
    """0-indexed column number -> Excel column letter(s)."""
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _write_instructions(workbook, spec: TemplateSpec, fmts: dict) -> None:
    sheet = workbook.add_worksheet(INSTRUCTIONS_SHEET)
    sheet.hide_gridlines(2)
    sheet.set_column(0, 0, 100)
    order = " -> ".join(nt.sheet_name for nt in spec.nodes)
    lines = [
        ("How to fill in this template", fmts["title"]),
        ("", fmts["wrap"]),
        (f"This workbook was generated for the '{spec.target_node}' node.", fmts["wrap"]),
        (f"Fill the sheets in this order (parents before children): {order}", fmts["wrap"]),
        ("", fmts["wrap"]),
        ("submitter_id", fmts["subtitle"]),
        (
            "On every sheet, 'submitter_id' is your own unique label for each row "
            "(any text you like, but unique within the sheet).",
            fmts["wrap"],
        ),
        ("", fmts["wrap"]),
        ("Linking rows to their parent", fmts["subtitle"]),
        (
            "A column named like 'subject.submitter_id' links this row to a row on "
            "the 'subject' sheet. Type (or pick from the dropdown) the submitter_id "
            "you used on that sheet. To attach several rows to the same parent, "
            "reuse the same submitter_id — that is how one-to-many relationships "
            "are expressed.",
            fmts["wrap"],
        ),
        (
            f"To reference more than one parent in a single cell, separate the "
            f'submitter_ids with "{LIST_SPLIT_CHAR}".',
            fmts["wrap"],
        ),
        ("", fmts["wrap"]),
        ("Required vs optional", fmts["subtitle"]),
        (
            "Dark blue headers are required; light headers are optional. The grey "
            "hint row under each header tells you the type and whether it is required.",
            fmts["wrap"],
        ),
        ("", fmts["wrap"]),
        ("Do not edit the header row or the hint row.", fmts["wrap"]),
        ("", fmts["wrap"]),
        ("When you are done, validate your file with:", fmts["subtitle"]),
        ("    g3mt validate <this_file>.xlsx --schema <schema.json>", fmts["wrap"]),
    ]
    for row_idx, (text, fmt) in enumerate(lines):
        sheet.write(row_idx, 0, text, fmt)


def _write_dictionary(workbook, spec: TemplateSpec, fmts: dict) -> None:
    sheet = workbook.add_worksheet(DICTIONARY_SHEET)
    headers = [
        "Sheet",
        "Node",
        "Column",
        "Type",
        "Required",
        "Description",
        "Allowed values",
        "Links to",
    ]
    widths = [18, 18, 24, 10, 10, 50, 40, 16]
    for col_idx, (head, width) in enumerate(zip(headers, widths)):
        sheet.write(0, col_idx, head, fmts["dict_header"])
        sheet.set_column(col_idx, col_idx, width)

    row_idx = 1
    for nt in spec.nodes:
        for col in nt.columns:
            values = [
                nt.sheet_name,
                nt.node,
                col.header,
                col.data_type,
                "yes" if col.required else "no",
                col.description,
                ", ".join(col.enum) if col.enum else "",
                col.link_target or "",
            ]
            for col_i, value in enumerate(values):
                sheet.write(row_idx, col_i, value, fmts["dict_cell"])
            row_idx += 1

    sheet.freeze_panes(1, 0)
    sheet.autofilter(0, 0, 0, len(headers) - 1)


def _write_meta(workbook, spec: TemplateSpec, fmts: dict, data_rows: int) -> None:
    """Hidden sheet recording how the workbook was generated, so validate can
    recover the schema/target/path automatically."""
    sheet = workbook.add_worksheet(META_SHEET)
    sheet.hide()
    rows = [
        ("g3mt_version", __version__),
        ("schema_file", Path(spec.schema_path).name),
        ("target_node", spec.target_node),
        ("path", ",".join(spec.path)),
        ("data_rows", str(data_rows)),
    ]
    for row_idx, (key, value) in enumerate(rows):
        sheet.write(row_idx, 0, key, fmts["meta_key"])
        sheet.write(row_idx, 1, value)

    # Node -> sheet mapping, so the reader never has to reverse a truncation.
    start = len(rows) + 1
    sheet.write(start, 0, "node", fmts["meta_key"])
    sheet.write(start, 1, "sheet", fmts["meta_key"])
    for offset, nt in enumerate(spec.nodes, start=start + 1):
        sheet.write(offset, 0, nt.node)
        sheet.write(offset, 1, nt.sheet_name)
