# CLI reference

Every `g3mt` command and flag. Run any command with `--help` for the same
information at the terminal.

```bash
g3mt --help
g3mt <command> --help
```

All commands use these exit codes: `0` success, `1` validation problems, `2`
usage/input error.

**Global options** (placed before the command):

| Option | Description |
|---|---|
| `--debug` | On error, show the full Python traceback instead of a one-line message, and enable verbose (DEBUG) logging from the schema engine. Exit code is unchanged. |

```bash
g3mt --debug generate schema.json sample -o sample_template.xlsx
```

Anywhere a `SCHEMA` is expected, you can give either a **local file path** or an
**`http(s)://` URL** to a Gen3 schema bundle — for example a raw file published
on GitHub:

```bash
g3mt nodes https://raw.githubusercontent.com/AustralianBioCommons/acdc-schema-json/refs/tags/v1.2.0/dictionary/prod_dict/acdc_schema.json
```

A URL is downloaded, used, and discarded; nothing is left on disk.

---

## `g3mt generate`

Generate an Excel template, for one node or for many at once.

```bash
g3mt generate SCHEMA [TARGET_NODE] [options]
```

**Arguments**

| Argument | Description |
|---|---|
| `SCHEMA` | Path or `http(s)://` URL to the Gen3 JSON schema bundle. |
| `TARGET_NODE` | *Optional.* The node you want to submit data for. Omit it if you use `--category` or `--node`. |

**Node selection**

| Option | Description |
|---|---|
| `--category NAME` | Include every node in this schema category (e.g. `--category clinical`). |
| `--node NAME` | Include this node and its ancestors. Repeatable. |

The positional node, `--category` and `--node` compose; their node sets are
merged and ordered parents-first.

**Output options**

| Option | Description |
|---|---|
| `-o, --output PATH` | Where to write the `.xlsx`. Default: derived from the selection (see [Generating templates](generating-templates.md#default-output-filename)). |
| `--rows N` | Blank data rows to provision per sheet. Default: `5000`. |
| `--force` | Overwrite the output file if it already exists. |

**Path selection**

| Option | Description |
|---|---|
| `--path TEXT` | Choose among multiple paths: a number (e.g. `2`) or a node chain (e.g. `subject,visit,sample`). With several targets, prefix with the node: `--path sample=2`. Repeatable. |
| `--list-paths` | Print the numbered paths to each selected node and exit. |

**Node & column filters**

| Option | Description |
|---|---|
| `--include-node NAME` | Re-include a default-excluded node. Repeatable. |
| `--exclude-node NAME` | Exclude an extra node. Repeatable. |
| `--exclude-column NAME` | Exclude an extra property column from every sheet. Repeatable. |
| `--no-default-excludes` | Keep the normally-excluded nodes (`program`, `project`, `core_metadata_collection`, `acknowledgement`). |

**Examples**

```bash
g3mt generate schema.json --category clinical -o clinical_template.xlsx
g3mt generate schema.json --node subject --node sample
g3mt generate schema.json sample -o sample_template.xlsx
g3mt generate schema.json sample --path 2 --exclude-node acknowledgement
g3mt generate schema.json sample --list-paths
g3mt generate schema.json sample --include-node project --rows 1000
```

---

## `g3mt validate`

Validate a filled template and report problems by sheet, row, and column.

```bash
g3mt validate WORKBOOK --schema SCHEMA [options]
```

**Arguments**

| Argument | Description |
|---|---|
| `WORKBOOK` | The filled `.xlsx` template to check. |

**Options**

| Option | Description |
|---|---|
| `-s, --schema SCHEMA` | Path or `http(s)://` URL to the Gen3 JSON schema bundle. **Required.** |
| `--annotate PATH` | Write a copy of the workbook with problem cells highlighted. |
| `--json` | Print the report as JSON instead of tables. |
| `-v, --verbose` | Also show the raw underlying error messages. |
| `--path TEXT` | Comma-separated list of the nodes the workbook contains, if it has no `g3mt` metadata. |

**Examples**

```bash
g3mt validate sample_template.xlsx -s schema.json
g3mt validate sample_template.xlsx -s schema.json --annotate checked.xlsx
g3mt validate sample_template.xlsx -s schema.json --json
```

---

## `g3mt nodes`

List the nodes in a schema, with their category and links.

```bash
g3mt nodes SCHEMA
```

**Arguments**

| Argument | Description |
|---|---|
| `SCHEMA` | Path or `http(s)://` URL to the Gen3 JSON schema bundle. |

---

## `g3mt categories`

List the categories in a schema, with how many nodes each contains. A category
groups related nodes (for example every clinical node), and is the easiest way
to find what you want without knowing individual node names.

```bash
g3mt categories SCHEMA [--nodes | --no-nodes]
```

**Arguments**

| Argument | Description |
|---|---|
| `SCHEMA` | Path or `http(s)://` URL to the Gen3 JSON schema bundle. |

**Options**

| Option | Description |
|---|---|
| `--nodes` / `--no-nodes` | List the node names in each category. Default: `--nodes`. |

**Example**

```bash
$ g3mt categories schema.json
Category               Nodes  Node names
administrative             6  acknowledgement, core_metadata_collection, ...
biospecimen                1  sample
clinical                   8  blood_pressure_test, clinical_descriptor, demographic, ...
data_file                  8  genomics_file, imaging_file, ...
```

---

## `g3mt paths`

Show the numbered paths from the root to a target node. The numbering matches
what `generate --path N` expects.

```bash
g3mt paths SCHEMA TARGET_NODE
```

**Arguments**

| Argument | Description |
|---|---|
| `SCHEMA` | Path or `http(s)://` URL to the Gen3 JSON schema bundle. |
| `TARGET_NODE` | The node to enumerate paths to. |

---

## `g3mt version`

Print the installed `g3mt` version.

```bash
g3mt version
```
