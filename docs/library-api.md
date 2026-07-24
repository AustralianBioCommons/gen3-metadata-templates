# Library API

The `g3mt` CLI is a thin shell over an importable Python library. If you're
building a UI, a pipeline, or another tool, use the library directly — nothing is
hidden behind the CLI.

Everything below is importable from the top-level package:

```python
from gen3_metadata_templates import (
    SchemaBundle,
    build_template_spec,
    write_template,
    validate_workbook,
    enumerate_paths,
    resolve_path,
)
```

## The pieces

The library is organised around a few objects:

- **`SchemaBundle`** — loads and resolves a Gen3 schema, and answers questions
  about it (nodes, links, edges).
- **`TemplateSpec`** — the plan for a template: which nodes, in what order, with
  what columns. Produced by `build_template_spec`; consumed by the writer and
  the validator, so they always agree.
- **`ValidationReport`** — the result of validating a workbook: a list of
  `Finding` objects plus warnings.

## Generate a template

```python
from gen3_metadata_templates import SchemaBundle, build_template_spec, write_template

bundle = SchemaBundle("schema.json")

spec = build_template_spec(bundle, "sample", ["subject", "sample"])
write_template(spec, "sample_template.xlsx")
```

`build_template_spec(bundle, target_node, path, *, excluded_nodes=..., excluded_columns=...)`
returns a `TemplateSpec`. The `path` is the chosen node path from root to target
— you can build it yourself, or discover it with the path helpers below.

`write_template(spec, output_path, *, data_rows=5000, protect_headers=True)`
writes the `.xlsx`.

## Discover and choose a path

```python
from gen3_metadata_templates import enumerate_paths, resolve_path
from gen3_metadata_templates.constants import DEFAULT_EXCLUDED_NODES

paths = enumerate_paths(bundle, "sample", DEFAULT_EXCLUDED_NODES)
# e.g. [['subject', 'sample'], ['subject', 'visit', 'sample']]

# Pick one: by index, by node chain, or with your own chooser callback.
path = resolve_path(paths, path_arg="2")
path = resolve_path(paths, chooser=lambda candidates: 0)  # e.g. a UI picker
```

`resolve_path` returns the single path immediately when there's only one
candidate. When there are several and you give it neither a `path_arg` nor a
`chooser`, it raises `AmbiguousPathError` (which carries the candidate paths).
The `chooser` parameter is how a UI injects its own selection step without the
library depending on any UI.

## Validate a workbook

```python
from gen3_metadata_templates import validate_workbook

report = validate_workbook("sample_template.xlsx", "schema.json")

if report.ok:
    print("valid")
else:
    for f in report.findings:
        print(f"{f.location}: {f.message}")
```

`validate_workbook(workbook_path, schema_path, *, path_arg=None, chooser=None, ...)`
returns a `ValidationReport`.

### `ValidationReport`

| Attribute | Description |
|---|---|
| `ok` | `True` if there are no findings. |
| `findings` | A list of `Finding` objects. |
| `warnings` | A list of non-fatal warning strings. |
| `node_counts` | `{node: (records_checked, findings)}`. |

### `Finding`

| Attribute | Description |
|---|---|
| `node` / `sheet` | The node and sheet the problem is on. |
| `cell` | A `CellRef` (has `.a1`, `.sheet`, `.row`) or `None`. |
| `location` | `"sheet!A1"` when the cell is known, else the sheet name. |
| `header` | The column header, when known. |
| `validator` | The kind of problem (`type`, `enum`, `required`, `link`, `duplicate`, …). |
| `message` | The plain-English explanation. |
| `raw_message` | The original underlying error message. |

### JSON and rich output

```python
from gen3_metadata_templates.validation.report import to_json, render_console
from rich.console import Console

data = to_json(report)  # plain dict, JSON-serialisable
render_console(report, Console())  # the same tables the CLI prints
```

## Annotate a workbook

```python
from gen3_metadata_templates.workbook.annotate import write_annotated_copy

write_annotated_copy("sample_template.xlsx", report, "checked.xlsx")
```

Writes a copy with problem cells highlighted and commented. It raises if the
output path equals the input path (so you can't destroy the original).

## Errors

All expected, user-facing errors derive from `G3mtError`, so you can catch that
one base:

```python
from gen3_metadata_templates import G3mtError, SchemaError, UnknownNodeError, AmbiguousPathError

try:
    bundle = SchemaBundle("schema.json")
    ...
except G3mtError as exc:
    print(f"input problem: {exc}")
```

`SchemaError` (bad/unreadable schema), `UnknownNodeError` (no such target node),
`AmbiguousPathError` (multiple paths, none chosen), and `WorkbookFormatError`
(unrecognisable workbook) are the specific subtypes.

## Inspecting a schema

```python
bundle = SchemaBundle("schema.json")

bundle.node_names  # sorted list of node ids
bundle.links("sample")  # list of LinkInfo(name, target_type, multiplicity, required)
bundle.required_props("sample")
bundle.resolved("sample")  # the fully ref-resolved node schema dict
```
