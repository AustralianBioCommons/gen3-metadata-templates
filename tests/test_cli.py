"""Tests for the ``g3mt`` command-line interface.

These drive the CLI the way a user would (via Typer's test runner) to confirm
the command surface behaves: templates get written, ambiguity is refused with a
helpful message in a non-interactive run, and the exit codes that scripts rely
on (0 clean, 1 problems, 2 usage error) are correct.
"""

from __future__ import annotations

import json

import openpyxl
from typer.testing import CliRunner

from gen3_metadata_templates.cli import app

runner = CliRunner()


def test_generate_writes_a_workbook(mini_schema_path, tmp_path):
    """`g3mt generate` with an unambiguous path writes the .xlsx and exits 0."""
    out = tmp_path / "visit.xlsx"
    result = runner.invoke(app, ["generate", mini_schema_path, "visit", "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "visit" in openpyxl.load_workbook(out).sheetnames


def test_generate_ambiguous_without_path_exits_2(mini_schema_path, tmp_path):
    """An ambiguous target with no --path fails clearly in a non-interactive run.

    The runner provides no TTY, so the CLI must not hang on a prompt; it should
    print the numbered options and exit 2 so a script knows to pass --path.
    """
    out = tmp_path / "sample.xlsx"
    result = runner.invoke(app, ["generate", mini_schema_path, "sample", "-o", str(out)])
    assert result.exit_code == 2
    assert "multiple paths" in result.output.lower()


def test_generate_with_path_index(mini_schema_path, tmp_path):
    """Passing --path resolves the ambiguity and writes the chosen sheets."""
    out = tmp_path / "sample.xlsx"
    result = runner.invoke(
        app, ["generate", mini_schema_path, "sample", "--path", "2", "-o", str(out)]
    )
    assert result.exit_code == 0
    names = openpyxl.load_workbook(out).sheetnames
    assert "visit" in names  # path 2 is subject -> visit -> sample


def test_list_paths_prints_and_exits_zero(mini_schema_path):
    """`--list-paths` shows the numbered options without generating anything."""
    result = runner.invoke(app, ["generate", mini_schema_path, "sample", "--list-paths"])
    assert result.exit_code == 0
    assert "1." in result.output and "2." in result.output


def test_validate_clean_workbook_exits_zero(mini_schema_path, tmp_path):
    """A generated (empty) template has no rows, so validation is clean (exit 0)."""
    out = tmp_path / "empty.xlsx"
    runner.invoke(app, ["generate", mini_schema_path, "visit", "-o", str(out)])
    result = runner.invoke(app, ["validate", str(out), "-s", mini_schema_path])
    assert result.exit_code == 0
    assert "all good" in result.output.lower()


def test_validate_reports_problems_exits_one(mini_schema_path, tmp_path):
    """A workbook with a bad value exits 1 and names the problem.

    Exit 1 (distinct from usage errors) is how CI or a script can tell "the file
    has fixable problems" apart from "you called me wrong".
    """
    out = tmp_path / "bad.xlsx"
    runner.invoke(app, ["generate", mini_schema_path, "visit", "-o", str(out)])
    wb = openpyxl.load_workbook(out)
    ws = wb["visit"]
    header = {ws.cell(1, c).value: c for c in range(1, ws.max_column + 1)}
    ws.cell(3, header["submitter_id"]).value = "v1"
    ws.cell(3, header["visit_id"]).value = "V1"
    ws.cell(3, header["subject.submitter_id"]).value = "ghost"  # dangling link
    wb.save(out)

    result = runner.invoke(app, ["validate", str(out), "-s", mini_schema_path])
    assert result.exit_code == 1
    assert "problem" in result.output.lower()


def test_validate_json_output_is_parseable(mini_schema_path, tmp_path):
    """`--json` emits machine-readable output for scripting / a future UI."""
    out = tmp_path / "empty.xlsx"
    runner.invoke(app, ["generate", mini_schema_path, "visit", "-o", str(out)])
    result = runner.invoke(app, ["validate", str(out), "-s", mini_schema_path, "--json"])
    payload = json.loads(result.output)
    assert payload["ok"] is True
