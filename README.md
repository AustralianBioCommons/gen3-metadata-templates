# gen3-metadata-templates

Generate friendly Excel submission templates from a Gen3 schema, then validate
the filled-in workbooks — with every error pinned to the exact sheet, row, and
column, in plain English.

The tool is built for people who need to submit metadata that fits a Gen3 data
model but aren't expected to know linked-data theory. Generated workbooks use
dropdowns for controlled values and for parent links, so most mistakes can't be
made in the first place; the ones that slip through are caught on validation and
explained clearly.

## Install

```bash
pipx install gen3-metadata-templates      # installs the `g3mt` command
```

(or `pip install gen3-metadata-templates` into an environment of your choice.)

## Quickstart

```bash
# 1. Generate a template for the node you want to submit (e.g. "sample")
g3mt generate schema.json sample -o sample_template.xlsx

# 2. Open sample_template.xlsx, read the Instructions sheet, and fill it in.

# 3. Validate your filled file
g3mt validate sample_template.xlsx --schema schema.json --annotate checked.xlsx
```

`validate` prints a report grouped by sheet and exits `0` if the file is clean,
`1` if there are problems to fix. With `--annotate`, it also writes a copy of
your workbook with the problem cells highlighted and commented.

## What's in a generated template

- **One sheet per node**, ordered so you fill parents before children.
- **`submitter_id`** on every sheet is your own unique label for each row.
- **Link columns** like `subject.submitter_id` connect a row to a row on the
  `subject` sheet — pick the parent from the dropdown. Reusing the same
  parent `submitter_id` on several child rows is how one-to-many relationships
  are expressed. To reference more than one parent in a single cell, separate
  the values with `;`.
- **Dropdowns** for controlled (enum) values and TRUE/FALSE fields.
- **Required columns** have dark headers; optional ones are light. The grey hint
  row under each header shows the type and whether it's required.
- An **Instructions** sheet (how it all works) and a **Dictionary** sheet
  (every column's type, description, and allowed values).

## Choosing a path

A node can be reachable by more than one chain of parents. When that happens,
`generate` shows the options and asks you to choose (or pass `--path`):

```bash
g3mt paths schema.json sample          # list the numbered paths
g3mt generate schema.json sample --path 2
g3mt generate schema.json sample --path subject,visit,sample
```

By default `program`, `project`, `core_metadata_collection`, and
`acknowledgement` are left out of templates (they're usually not submitted by
hand). Re-include any of them with `--include-node`, or drop more with
`--exclude-node` / `--exclude-column`.

## Command reference

| Command | What it does |
|---|---|
| `g3mt generate SCHEMA TARGET_NODE` | Write an Excel template for a node. |
| `g3mt validate WORKBOOK -s SCHEMA` | Check a filled template; `--annotate`, `--json`, `--verbose`. |
| `g3mt nodes SCHEMA` | List the schema's nodes and their links. |
| `g3mt paths SCHEMA TARGET_NODE` | Show the numbered paths to a node. |

Run any command with `--help` for the full options.

## Using it as a library

The CLI is a thin shell; everything is importable.

```python
from gen3_metadata_templates import (
    SchemaBundle, build_template_spec, write_template, validate_workbook,
)

bundle = SchemaBundle("schema.json")
spec = build_template_spec(bundle, "sample", ["subject", "sample"])
write_template(spec, "sample_template.xlsx")

report = validate_workbook("sample_template.xlsx", "schema.json")
print(report.ok, [f"{f.location}: {f.message}" for f in report.findings])
```

## Development

```bash
git clone https://github.com/AustralianBioCommons/gen3-metadata-templates.git
cd gen3-metadata-templates
pip install poetry
poetry install
poetry run pytest -vv
```

## Note on 2.0

Version 2.0 is a full rewrite. The old Python API (`generate_xlsx_template`,
`make_node_template_pd`, `PropExtractor`) has been replaced by the library and
`g3mt` CLI described above. It requires `gen3-validator >= 2.1`.
