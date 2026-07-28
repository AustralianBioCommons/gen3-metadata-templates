# Troubleshooting

Common problems and how to resolve them. If your issue isn't here, run the
command again with `--help`, or open an issue on the project repository.

!!! tip "See the full error"
    When a message isn't enough to explain a failure, re-run the command with
    the global `--debug` flag (placed before the command) to get the full
    traceback and verbose engine logs:

    ```bash
    g3mt --debug generate schema.json sample
    ```

## Generating

### "Node 'X' does not exist in the schema"

The target node name is misspelled or isn't in this schema. List the available
nodes:

```bash
g3mt nodes schema.json
```

Node names are case-sensitive and use the schema's own spelling (e.g.
`unaligned_reads_file`, not `Unaligned Reads File`).

### "Node 'X' has multiple paths" / it's asking me to choose

The node can be reached by more than one chain of parents, and the template can
only cover one. See the options and pick one:

```bash
g3mt paths schema.json X
g3mt generate schema.json X --path 2
```

In a script with no terminal attached, you must pass `--path` — `g3mt` won't
guess. See [Choosing a path](generating-templates.md#choosing-a-path).

### My template only has one sheet

If nothing in the schema links *into* the node you asked for, the template is
just that one sheet. That happens when:

- the node sits at the top of the graph (a root, such as `subject` once the
  administrative nodes are excluded) — this is expected and correct; or
- every route to it runs through a node you excluded. If you excluded a node
  that's on the only path, bring it back with `--include-node`.

Check what the tool found with `g3mt paths schema.json X`.

### "<file> already exists"

The output file is already there. Use `--force` to overwrite it, or choose a
different `-o` path.

### A required parent node isn't in my template

`program`, `project`, `core_metadata_collection`, and `acknowledgement` are
excluded by default. If you need one of them as a sheet, add
`--include-node <name>`.

## Filling in

### The link dropdown won't let me pick a parent that isn't there yet

That's expected — you can still type the ID. The link dropdown is a convenience,
not a lock; it only lists parents you've already entered. As long as you add the
parent row (with that `submitter_id`) before you submit, validation will pass.

### Excel changed my value (dropped a leading zero, turned it into a date)

String columns in the template are formatted as text to prevent this. If it
still happens, format the cell as **Text** in Excel before typing, or prefix the
entry appropriately. Then re-check with `validate`.

### I've run out of rows

Templates provision a fixed number of rows (5000 by default). Regenerate with a
larger value:

```bash
g3mt generate schema.json sample --rows 20000 -o sample_template.xlsx
```

## Validating

### "This cell can't be empty — 'X' is required"

A required field is blank. Fill the named cell. If instead a whole required
**column** was deleted from the sheet, the message says the column is missing —
regenerate the template and copy your data across rather than hand-editing
headers.

### "'X' doesn't match any submitter_id on the 'Y' sheet"

A link points at a parent that doesn't exist. Either:

- there's a typo in the `parent.submitter_id` cell, or
- you haven't added the parent row (with that `submitter_id`) on the `Y` sheet.

Fix the typo or add the missing parent, then re-validate.

### "Duplicate submitter_id 'X'"

Two rows on the same sheet share a `submitter_id`. Each row needs a unique one —
change one of them.

### "This workbook has no g3mt metadata"

You're validating a workbook that wasn't produced by `g3mt` (or its hidden
`_g3mt` sheet was deleted), so the node path can't be recovered automatically.
Pass the path explicitly:

```bash
g3mt validate data.xlsx --schema schema.json --path subject,sample
```

### The annotated copy is missing some of my formatting

The annotated file is a **review aid** — it highlights the problem cells and
adds comments, but may not preserve every bit of the original's styling. Keep
filling in your original workbook; use the annotated copy only to see what to
fix.

## Installing

### `g3mt: command not found` after install

If you installed with `pipx`, make sure pipx's bin directory is on your `PATH`
(`pipx ensurepath`, then open a new terminal). If you installed with `pip` into
a virtual environment, activate that environment first.

### Schema won't load

The schema must be a single JSON **bundle** — one file (or one URL) containing
all the node definitions. A folder of individual YAML files is not read directly;
export/convert it to one JSON bundle first.

### Loading a schema from a URL fails

You can pass an `http(s)://` URL instead of a local path, but it must point at
the **raw JSON** of the bundle. A common mistake is linking a GitHub *blob* page
(the HTML view) instead of the raw file — the tool reports that the content
"is not valid JSON". Use the `raw.githubusercontent.com` URL (or click **Raw**
on GitHub and copy that link). Other causes: no network access, or a private
repository the request isn't authorised to read.
