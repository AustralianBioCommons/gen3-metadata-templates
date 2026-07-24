# CLI reference

Every `g3mt` command and flag. Run any command with `--help` for the same
information at the terminal.

```bash
g3mt --help
g3mt <command> --help
```

All commands use these exit codes: `0` success, `1` validation problems, `2`
usage/input error.

---

## `g3mt generate`

Generate an Excel template for a target node.

```bash
g3mt generate SCHEMA TARGET_NODE [options]
```

**Arguments**

| Argument | Description |
|---|---|
| `SCHEMA` | Path to the Gen3 JSON schema bundle. |
| `TARGET_NODE` | The node you want to submit data for. |

**Output options**

| Option | Description |
|---|---|
| `-o, --output PATH` | Where to write the `.xlsx`. Default: `<target_node>_template.xlsx`. |
| `--rows N` | Blank data rows to provision per sheet. Default: `5000`. |
| `--force` | Overwrite the output file if it already exists. |

**Path selection**

| Option | Description |
|---|---|
| `--path TEXT` | Choose among multiple paths: a number (e.g. `2`) or a node chain (e.g. `subject,visit,sample`). |
| `--list-paths` | Print the numbered paths to the target node and exit. |

**Node & column filters**

| Option | Description |
|---|---|
| `--include-node NAME` | Re-include a default-excluded node. Repeatable. |
| `--exclude-node NAME` | Exclude an extra node. Repeatable. |
| `--exclude-column NAME` | Exclude an extra property column from every sheet. Repeatable. |
| `--no-default-excludes` | Keep the normally-excluded nodes (`program`, `project`, `core_metadata_collection`, `acknowledgement`). |

**Examples**

```bash
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
| `-s, --schema FILE` | Path to the Gen3 JSON schema bundle. **Required.** |
| `--annotate PATH` | Write a copy of the workbook with problem cells highlighted. |
| `--json` | Print the report as JSON instead of tables. |
| `-v, --verbose` | Also show the raw underlying error messages. |
| `--path TEXT` | Node path, if the workbook has no `g3mt` metadata. |

**Examples**

```bash
g3mt validate sample_template.xlsx -s schema.json
g3mt validate sample_template.xlsx -s schema.json --annotate checked.xlsx
g3mt validate sample_template.xlsx -s schema.json --json
```

---

## `g3mt nodes`

List the nodes in a schema, with their links.

```bash
g3mt nodes SCHEMA
```

**Arguments**

| Argument | Description |
|---|---|
| `SCHEMA` | Path to the Gen3 JSON schema bundle. |

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
| `SCHEMA` | Path to the Gen3 JSON schema bundle. |
| `TARGET_NODE` | The node to enumerate paths to. |

---

## `g3mt version`

Print the installed `g3mt` version.

```bash
g3mt version
```
