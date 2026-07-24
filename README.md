# gen3-metadata-templates

[![CI](https://github.com/AustralianBioCommons/gen3-metadata-templates/actions/workflows/build.yml/badge.svg)](https://github.com/AustralianBioCommons/gen3-metadata-templates/actions/workflows/build.yml)
[![PyPI version](https://img.shields.io/pypi/v/gen3-metadata-templates.svg)](https://pypi.org/project/gen3-metadata-templates/)
[![Python versions](https://img.shields.io/pypi/pyversions/gen3-metadata-templates.svg)](https://pypi.org/project/gen3-metadata-templates/)

Turn a Gen3 schema into friendly Excel submission templates, then validate the
filled-in workbooks — with every error pinned to the exact sheet, row, and
column, in plain English.

## Documentation

- **[Quickstart](docs/quickstart.md)** — the shortest path from a schema to a
  validated workbook.
- **[Concepts](docs/concepts.md)** — nodes, links, paths, and `submitter_id`, for
  readers new to Gen3.
- **[Generating templates](docs/generating-templates.md)** — path selection,
  node/column filtering, and what every part of the workbook means.
- **[Filling in a template](docs/filling-templates.md)** — how linking,
  one-to-many, and multi-value cells work.
- **[Validating](docs/validating.md)** — the error types, the annotated copy,
  and exit codes.
- **[CLI reference](docs/cli-reference.md)** — every command and flag.
- **[Library API](docs/library-api.md)** — using the core from Python.
- **[Troubleshooting](docs/troubleshooting.md)** — common problems and fixes.

## Install

```bash
pipx install gen3-metadata-templates      # installs the `g3mt` command

g3mt generate schema.json sample -o sample_template.xlsx
# ...fill sample_template.xlsx in Excel...
g3mt validate sample_template.xlsx --schema schema.json --annotate checked.xlsx
```

## Why this exists

Submitting metadata to a Gen3 data commons means producing records that conform
to a graph-shaped data model: nodes (subject, sample, file, …) linked
parent-to-child, each with typed, sometimes-controlled properties. That is hard
for people who aren't fluent in linked data — and mistakes are usually only
discovered late, as opaque errors.

`g3mt` closes that gap from both ends:

- **Generation** produces a workbook a non-specialist can fill in confidently —
  parent links and controlled values are **dropdowns**, so most errors can't be
  made in the first place.
- **Validation** catches whatever still slips through and reports it as
  *"Sheet subject, cell C4: 'ten' isn't a whole number"* rather than a stack
  trace.

## Input and output

| | |
|---|---|
| **Input (generate)** | A Gen3 JSON schema bundle (a single `.json` file of node definitions) + the name of the node you want to submit. |
| **Output (generate)** | An `.xlsx` workbook: one sheet per node on the path to your target, with dropdowns, guidance, and reference sheets. |
| **Input (validate)** | Your filled `.xlsx` workbook + the same schema. |
| **Output (validate)** | A console report grouped by sheet (and optionally a highlighted copy of the workbook or a JSON report). Exit code `0` = clean, `1` = problems found, `2` = usage error. |

## Key features

- **One sheet per node, in fill order** — parents before children, so links
  always resolve.
- **Cross-sheet link dropdowns** — a `subject.submitter_id` column on the sample
  sheet is a dropdown of the IDs you entered on the subject sheet. Reusing a
  parent ID across child rows is all "one-to-many" requires — no theory needed.
- **Controlled-value dropdowns** — enum and boolean fields become dropdowns.
- **Self-documenting workbooks** — required vs optional headers, a type/required
  hint row, per-column description comments, plus an **Instructions** sheet and a
  full **Dictionary** sheet.
- **Path selection** — when a node is reachable by more than one chain of
  parents, you choose which one the template covers.
- **Precise, plain-English validation** — errors located to the cell, rephrased
  for non-developers, with an optional highlighted copy of your file.
- **Use it as a CLI or a Python library** — the CLI is a thin shell over an
  importable core.

## Requirements

- Python ≥ 3.9.5
- `gen3-validator` ≥ 2.1 (installed automatically)

## Development

```bash
git clone https://github.com/AustralianBioCommons/gen3-metadata-templates.git
cd gen3-metadata-templates
pip install poetry
poetry install
poetry run pytest -vv
```

Before pushing, run the same checks CI does:

```bash
poetry run ruff check .          # lint
poetry run ruff format --check . # formatting
poetry run pytest -vv            # tests
```

To preview the documentation site locally:

```bash
poetry install --with docs
poetry run mkdocs serve      # then open http://127.0.0.1:8000
```

## Continuous integration & releases

- **CI** (`.github/workflows/build.yml`) runs on every push and pull request to
  `main`: Ruff lint + format check, the test suite on Python 3.9–3.12, a
  `g3mt --help` smoke test, and a strict docs build.
- **Publishing** (`.github/workflows/publish_pypi.yml`) runs when a GitHub
  Release is published: it verifies the release tag matches the package version,
  then builds and publishes to PyPI. It needs a `PYPI_API_KEY` repository secret.
- **TestPyPI** (`.github/workflows/publish_testpypi.yml`) can be triggered
  manually from the Actions tab to publish a pre-release; it needs a
  `TESTPYPI_API_KEY` secret.

To cut a release:

```bash
poetry version <major|minor|patch>       # bump the version in pyproject.toml
git commit -am "chore: release vX.Y.Z"
git tag vX.Y.Z && git push --tags
gh release create vX.Y.Z --generate-notes # publishing the release runs the workflow
```

## A note on 2.0

Version 2.0 is a full rewrite. The old Python API
(`generate_xlsx_template`, `make_node_template_pd`, `PropExtractor`) has been
replaced by the library and `g3mt` CLI documented here.

## License

Apache 2.0 — see [LICENSE](LICENSE).
