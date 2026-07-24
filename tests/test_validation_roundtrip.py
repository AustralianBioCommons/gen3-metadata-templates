"""End-to-end validation tests: generate a template, fill it, validate it.

This is the flagship test for the whole tool. It proves the pieces fit together:
a workbook produced by the writer can be read back, validated against the same
schema, and — crucially — that real mistakes are reported at the exact cell the
user needs to fix. A clean fill must pass; a deliberately broken fill must
produce precisely the expected findings and nothing spurious.
"""

from __future__ import annotations

import openpyxl
import pytest

from gen3_metadata_templates import build_template_spec, validate_workbook, write_template
from gen3_metadata_templates.workbook.annotate import write_annotated_copy


def _set_row(wb, sheet, row, **values):
    ws = wb[sheet]
    header_to_col = {ws.cell(1, c).value: c for c in range(1, ws.max_column + 1)}
    for header, value in values.items():
        ws.cell(row, header_to_col[header]).value = value


@pytest.fixture()
def template_path(mini_bundle, tmp_path):
    """A freshly generated (empty) template for the subject->sample path."""
    spec = build_template_spec(mini_bundle, "sample", ["subject", "sample"])
    out = tmp_path / "roundtrip.xlsx"
    write_template(spec, out, data_rows=20)
    return out, str(mini_bundle.schema_path)


def test_valid_fill_passes(template_path):
    """A correctly filled workbook must validate with zero findings.

    If a clean submission produced spurious errors, users would lose trust in
    the tool immediately, so this is the most important guarantee.
    """
    path, schema = template_path
    wb = openpyxl.load_workbook(path)
    _set_row(wb, "subject", 3, submitter_id="subj_1", subject_id="S1", age=42, sex="Male")
    _set_row(
        wb,
        "sample",
        3,
        submitter_id="samp_1",
        **{"subject.submitter_id": "subj_1"},
        sample_id="X1",
        sample_type="Blood",
    )
    wb.save(path)

    report = validate_workbook(path, schema)
    assert report.ok
    assert report.findings == []


def test_broken_fill_reports_each_problem_at_the_right_cell(template_path):
    """Each planted error must surface as a finding located at its exact cell.

    The fill below plants five distinct mistakes; validation must find all five,
    each mapped to the cell and validator we expect — this is what lets a user
    fix "sheet subject, cell C4" rather than hunt through the file.
    """
    path, schema = template_path
    wb = openpyxl.load_workbook(path)
    # Row 3: valid baseline so the sample link has a real parent to match.
    _set_row(wb, "subject", 3, submitter_id="subj_1", subject_id="S1", age=30, sex="Female")
    # Row 4: duplicate submitter_id, non-integer age, invalid enum.
    _set_row(wb, "subject", 4, submitter_id="subj_1", subject_id="S2", age="ten", sex="Alien")
    # Sample row: dangling parent link and a missing required enum (sample_type).
    _set_row(
        wb, "sample", 3, submitter_id="samp_1", **{"subject.submitter_id": "ghost"}, sample_id="X1"
    )
    wb.save(path)

    report = validate_workbook(path, schema)
    assert not report.ok

    located = {(f.sheet, f.cell.a1 if f.cell else None): f.validator for f in report.findings}

    assert located.get(("subject", "C4")) == "type"  # age "ten"
    assert located.get(("subject", "G4")) == "enum"  # sex "Alien"
    assert located.get(("subject", "A4")) == "duplicate"  # repeated submitter_id
    assert located.get(("sample", "B3")) == "link"  # dangling subject link
    # Columns: A submitter_id, B subject.submitter_id, C sample_id, D sample_type.
    assert located.get(("sample", "D3")) == "required"  # empty sample_type


def test_annotated_copy_highlights_bad_cells(template_path, tmp_path):
    """The annotated workbook must fill each bad cell and attach a comment.

    Spreadsheet-native users fix errors fastest when they can open a copy and see
    the red cells, so the annotation must actually land on the flagged cells.
    """
    path, schema = template_path
    wb = openpyxl.load_workbook(path)
    _set_row(wb, "subject", 3, submitter_id="subj_1", subject_id="S1", age="oops", sex="Male")
    _set_row(
        wb,
        "sample",
        3,
        submitter_id="samp_1",
        **{"subject.submitter_id": "subj_1"},
        sample_id="X1",
        sample_type="Blood",
    )
    wb.save(path)

    report = validate_workbook(path, schema)
    annotated = tmp_path / "annotated.xlsx"
    write_annotated_copy(path, report, annotated)

    check = openpyxl.load_workbook(annotated)
    bad_cell = check["subject"]["C3"]
    assert bad_cell.fill.fgColor.rgb.endswith("FFC7CE")
    assert bad_cell.comment is not None
    assert "Validation Errors" in check.sheetnames


def test_annotate_refuses_to_overwrite_input(template_path):
    """Annotating over the input file would destroy the user's work — refuse it."""
    from gen3_metadata_templates.errors import G3mtError

    path, schema = template_path
    report = validate_workbook(path, schema)
    with pytest.raises(G3mtError):
        write_annotated_copy(path, report, path)
