# gen3-metadata-templates

Turn a Gen3 schema into friendly Excel submission templates, then validate the
filled-in workbooks — with every error pinned to the exact sheet, row, and
column, in plain English.

This tool is for anyone who needs to submit metadata that fits a Gen3 data model
but isn't expected to know linked-data theory. Generated workbooks use dropdowns
for controlled values and for parent links, so most mistakes can't be made in
the first place; the rest are caught on validation and explained clearly.

## Where to start

| If you want to… | Read |
|---|---|
| Get from a schema to a validated file fast | [Quickstart](quickstart.md) |
| Understand nodes, links, and paths first | [Concepts](concepts.md) |
| Learn every option when generating | [Generating templates](generating-templates.md) |
| Know how to fill a workbook in correctly | [Filling in a template](filling-templates.md) |
| Understand validation output | [Validating](validating.md) |
| Look up a command or flag | [CLI reference](cli-reference.md) |
| Call the tool from Python | [Library API](library-api.md) |
| Fix a problem | [Troubleshooting](troubleshooting.md) |

## Install

```bash
pipx install gen3-metadata-templates
```

This installs the `g3mt` command. (You can also `pip install
gen3-metadata-templates` into any environment.)

## The three-step workflow

```bash
# 1. Generate a template for the node you want to submit
g3mt generate schema.json sample -o sample_template.xlsx

# 2. Fill sample_template.xlsx in Excel (start with the Instructions sheet)

# 3. Validate it
g3mt validate sample_template.xlsx --schema schema.json --annotate checked.xlsx
```

See the [Quickstart](quickstart.md) for a fully worked version of this.
