# Generating templates

`g3mt generate` turns a schema and a target node into an Excel workbook. This
page covers choosing a path, filtering nodes and columns, and what every part of
the generated workbook means.

```bash
g3mt generate SCHEMA TARGET_NODE [options]
```

The simplest form:

```bash
g3mt generate schema.json sample -o sample_template.xlsx
```

writes one sheet for each node on the path from the schema's root down to
`sample`, plus guide sheets.

## Choosing a path

A node can be reachable by more than one chain of parents. When it is, the
template can only cover one of them (the choice decides which sheets you get).

List the options:

```bash
g3mt paths schema.json sample
```

```
1. subject -> sample
2. subject -> visit -> sample
```

Then choose one. There are three ways:

- **Interactively.** Run `generate` without `--path`; if you're at a terminal,
  `g3mt` prints the numbered list and prompts you. Pressing Enter takes the
  shortest path (option 1).
- **By number.** `--path 2`
- **By node chain.** `--path subject,visit,sample`

```bash
g3mt generate schema.json sample --path 2 -o sample_template.xlsx
```

If a script runs `generate` on an ambiguous node with no `--path` and no
terminal attached, `g3mt` prints the options and exits with code `2` rather than
guessing — so choose explicitly in automation.

`--list-paths` prints the numbered paths and exits without generating anything
(handy in scripts).

## Filtering nodes and columns

By default, four nodes are **excluded** from every template because submitters
rarely fill them in:

`program`, `project`, `core_metadata_collection`, `acknowledgement`

You can change that:

| Flag | Effect |
|---|---|
| `--include-node NAME` | Bring a default-excluded node back into the template. Repeatable. |
| `--exclude-node NAME` | Exclude an additional node. Repeatable. |
| `--exclude-column NAME` | Drop a property column from every sheet. Repeatable. |
| `--no-default-excludes` | Keep all four normally-excluded nodes. |

```bash
# Include project, but drop the acknowledgement node
g3mt generate schema.json sample --include-node project --exclude-node acknowledgement
```

A set of Gen3 system properties (`type`, `id`, `state`, `object_id`,
`file_state`, `error_type`, `ga4gh_drs_uri`, `created_datetime`,
`updated_datetime`) is always excluded — these are managed by Gen3, not
submitters. `--exclude-column` adds to that list.

## Other options

| Flag | Effect |
|---|---|
| `-o, --output PATH` | Where to write the file. Default: `<target_node>_template.xlsx`. |
| `--rows N` | Number of blank data rows provisioned per sheet. Default: 5000. |
| `--force` | Overwrite the output file if it already exists. |

If you need more than `--rows` rows, regenerate with a larger value — the data
area is sized at generation time.

## Anatomy of a generated workbook

The workbook has three kinds of sheet.

### Node sheets

One per node, in fill order (parents first). On each:

- **Row 1 — headers.** Required columns have **dark blue** headers; optional
  columns are **light**. Hover any header for a comment with its description,
  type, and (for links) which sheet to copy IDs from.
- **Row 2 — the hint row.** A short, locked reminder of each column's type and
  whether it's required (e.g. `integer — required`,
  `link to 'subject' — required`).
- **Row 3 onward — your data.**

Column order is deliberate: `submitter_id` first, then link (parent) columns,
then required properties, then optional properties — so the fields you must fill
are on the left.

**Dropdowns** appear automatically:

- **Link columns** (`subject.submitter_id`) list the `submitter_id` values from
  the parent sheet.
- **Enum columns** list their allowed values.
- **Boolean columns** offer `TRUE` / `FALSE`.

The link dropdown is a *warning*, not a hard block — you're allowed to type an
ID for a parent row you haven't added yet. Validation is what enforces that the
reference actually exists.

### Instructions sheet

The first tab. A plain-language guide written for *this* template: the fill
order, what `submitter_id` means, how the link columns work (with a worked
example), the `;` multi-value rule, and the exact command to validate the file.

### Dictionary sheet

A complete reference: one row per column across every node sheet, listing the
sheet, node, column, type, whether it's required, the description, the allowed
values (for enums), and what it links to.

There are also two hidden sheets (`_g3mt` and `_lists`) that the tool uses to
record how the workbook was generated and to back long dropdowns. You can ignore
them; don't delete them, as `validate` reads `_g3mt` to recover the schema and
path automatically.

## Next

- [Filling in a template](filling-templates.md)
- [Validating](validating.md)
