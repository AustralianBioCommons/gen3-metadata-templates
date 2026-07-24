"""Tests for :mod:`gen3_metadata_templates.workbook.writer`.

The writer's output is what a submitter actually opens, so these tests generate
a real workbook and re-open it with openpyxl to confirm the structure: sheet
order, headers and hint rows, the guide/metadata sheets, cross-sheet link
dropdowns, and enum dropdowns. Getting the dropdowns right is the feature that
makes linked-data submission approachable, so they are checked explicitly.
"""

from __future__ import annotations

import openpyxl
import pytest

from gen3_metadata_templates import build_template_spec, write_template
from gen3_metadata_templates.constants import (
    DICTIONARY_SHEET,
    INSTRUCTIONS_SHEET,
    META_SHEET,
)


@pytest.fixture()
def sample_workbook(mini_bundle, tmp_path):
    """Generate a template for the subject->visit->sample path and return its path."""
    spec = build_template_spec(mini_bundle, "sample", ["subject", "visit", "sample"])
    out = tmp_path / "sample_template.xlsx"
    write_template(spec, out, data_rows=50)
    return out, spec


def test_sheets_are_in_path_order_with_guides(sample_workbook):
    """Node sheets appear in fill order, wrapped by the guide sheets.

    Instructions must come first (it's the first thing a user should read) and
    the node sheets must be in path order so a submitter naturally fills parents
    before children.
    """
    path, _ = sample_workbook
    wb = openpyxl.load_workbook(path)
    names = wb.sheetnames
    assert names[0] == INSTRUCTIONS_SHEET
    assert names.index("subject") < names.index("visit") < names.index("sample")
    assert DICTIONARY_SHEET in names
    assert META_SHEET in names


def test_header_and_hint_rows(sample_workbook):
    """Row 1 holds headers; row 2 holds the type/requirement hint."""
    path, _ = sample_workbook
    wb = openpyxl.load_workbook(path)
    ws = wb["sample"]
    assert ws.cell(1, 1).value == "submitter_id"
    assert ws.cell(1, 2).value == "subject.submitter_id"
    assert "required" in ws.cell(2, 1).value


def test_foreign_key_dropdown_targets_parent_sheet(sample_workbook):
    """The FK column's dropdown pulls IDs from the parent sheet's column.

    This cross-sheet dropdown is what lets a submitter pick a real parent
    submitter_id instead of typing (and mistyping) it, so it must reference the
    parent's named range.
    """
    path, _ = sample_workbook
    wb = openpyxl.load_workbook(path)
    ws = wb["sample"]
    sources = {dv.formula1 for dv in ws.data_validations.dataValidation}
    assert "ids_subject" in sources
    assert "ids_visit" in sources
    # And the defined name actually points at the subject sheet's column A.
    assert "subject" in str(wb.defined_names["ids_subject"].value)


def test_enum_dropdown_lists_allowed_values(sample_workbook):
    """An enum column offers exactly its allowed values as a dropdown."""
    path, _ = sample_workbook
    wb = openpyxl.load_workbook(path)
    ws = wb["sample"]
    enum_formulas = [
        dv.formula1
        for dv in ws.data_validations.dataValidation
        if "Blood" in str(dv.formula1)
    ]
    assert enum_formulas, "expected a dropdown containing the sample_type values"
    assert "Tissue" in enum_formulas[0] and "Saliva" in enum_formulas[0]


def test_dictionary_has_one_row_per_column(sample_workbook):
    """The Dictionary sheet documents every column across every node sheet.

    It's the submitter's reference for what each field means, so it must have a
    row for each ColumnSpec (plus the header row).
    """
    path, spec = sample_workbook
    wb = openpyxl.load_workbook(path)
    ws = wb[DICTIONARY_SHEET]
    total_columns = sum(len(nt.columns) for nt in spec.nodes)
    assert ws.max_row == total_columns + 1  # + header row


def test_meta_sheet_records_target_and_path(sample_workbook):
    """The hidden metadata sheet lets validate recover the schema/target/path."""
    path, _ = sample_workbook
    wb = openpyxl.load_workbook(path)
    ws = wb[META_SHEET]
    meta = {ws.cell(r, 1).value: ws.cell(r, 2).value for r in range(1, ws.max_row + 1)}
    assert meta["target_node"] == "sample"
    assert meta["path"] == "subject,visit,sample"
