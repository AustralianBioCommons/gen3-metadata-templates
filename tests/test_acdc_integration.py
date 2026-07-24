"""Integration smoke tests against the real 34-node ACDC schema.

The mini schema is deliberately small; these tests guard against regressions on
a full, real-world Gen3 dictionary — deep paths, many nodes, real enums — that
the hand-built fixture can't represent. They intentionally assert only broad,
stable properties so they don't turn brittle as the example schema evolves.
"""

from __future__ import annotations

import openpyxl

from gen3_metadata_templates import (
    SchemaBundle,
    build_template_spec,
    enumerate_paths,
    resolve_path,
    validate_workbook,
    write_template,
)
from gen3_metadata_templates.constants import DEFAULT_EXCLUDED_NODES


def test_generate_deep_node_writes_expected_sheets(acdc_schema_path, tmp_path):
    """A deep data-file node should produce a multi-sheet workbook in path order.

    ``lipidomics_file`` sits several links below the root, so its template should
    contain a sheet for each ancestor on the chosen path plus the guide sheets —
    proving generation scales beyond the toy fixture.
    """
    bundle = SchemaBundle(acdc_schema_path)
    paths = enumerate_paths(bundle, "lipidomics_file", DEFAULT_EXCLUDED_NODES)
    chosen = resolve_path(paths, path_arg="1")
    spec = build_template_spec(bundle, "lipidomics_file", chosen)

    out = tmp_path / "lipidomics_file.xlsx"
    write_template(spec, out, data_rows=50)

    names = openpyxl.load_workbook(out).sheetnames
    assert "lipidomics_file" in names
    for node in chosen:
        if node not in DEFAULT_EXCLUDED_NODES:
            assert node in names


def test_empty_generated_template_validates_clean(acdc_schema_path, tmp_path):
    """A freshly generated (unfilled) template must validate with no errors.

    With no data rows there is nothing to violate the schema, so validation
    should pass — a good end-to-end check that generate and validate agree on
    the workbook format for a real schema.
    """
    bundle = SchemaBundle(acdc_schema_path)
    chosen = resolve_path(
        enumerate_paths(bundle, "demographic", DEFAULT_EXCLUDED_NODES), path_arg="1"
    )
    spec = build_template_spec(bundle, "demographic", chosen)
    out = tmp_path / "demographic.xlsx"
    write_template(spec, out, data_rows=20)

    report = validate_workbook(out, acdc_schema_path)
    assert report.ok, [f.message for f in report.findings]
