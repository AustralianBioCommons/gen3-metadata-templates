# Validating

`g3mt validate` reads a filled workbook, checks it against the schema, and tells
you exactly what to fix and where.

```bash
g3mt validate WORKBOOK --schema SCHEMA [options]
```

```bash
g3mt validate sample_template.xlsx --schema schema.json
```

You don't normally need to say which nodes the workbook contains — `g3mt`
records that when it generates the file and reads it back automatically. (If you
validate a workbook that has no `g3mt` metadata, pass `--path` to say which
nodes it holds.)

## Reading the report

A clean file:

```
╭───────────────────────────────────────────────────────╮
│ All good — validated 2 record(s), no problems found.  │
╰───────────────────────────────────────────────────────╯
```

A file with problems shows a summary and then one table per sheet:

```
╭──────────────────────────────────────────────────────╮
│ 3 problem(s) across 2 sheet(s) in 3 record(s).       │
╰──────────────────────────────────────────────────────╯

Sheet: subject
 Cell   Column   Problem
 C4     age      'ten' isn't a whole number. This column needs a whole number (e.g. 42).
 G4     sex      This value isn't one of the allowed values. Pick one of: Male, Female, Unknown.

Sheet: sample
 Cell   Column                 Problem
 B3     subject.submitter_id   'ghost' doesn't match any submitter_id on the 'subject' sheet. Check for typos, or add that row first.
```

Each row tells you the **cell** to go to, the **column** it's in, and the
**problem** in plain language.

## What gets checked

| Check | Example problem |
|---|---|
| **Type** | A word in a number column; a decimal where a whole number is required. |
| **Allowed values (enum)** | A value that isn't one of the controlled options. |
| **Required** | A required cell left empty, or a required column deleted from the sheet. |
| **Format (pattern)** | Text that doesn't match a required format (e.g. a consent code). |
| **Ranges** | A number below a minimum or above a maximum. |
| **Links** | A `parent.submitter_id` that doesn't match any row on the parent sheet. |
| **Duplicate keys** | The same `submitter_id` used on two rows of one sheet. |

Links and duplicates are things Excel itself can't catch — they're why
validating before you submit is worth the step.

## Warnings vs. problems

Some things are reported as **warnings** (printed, but they don't fail
validation): an optional column missing from a sheet, or a link that points at a
node the workbook doesn't include (so there's nothing to check it against).
Warnings don't change the exit code.

## Getting a highlighted copy

```bash
g3mt validate sample_template.xlsx --schema schema.json --annotate checked.xlsx
```

This writes `checked.xlsx`: a copy of your workbook with every problem cell
filled red and given a comment explaining the fix, plus a "Validation Errors"
summary sheet that links to each cell.

Use it to *see* what to fix, then fix the cells in your **original** file and
re-validate. `g3mt` refuses to write the annotated copy over your input file, so
your work is never overwritten.

## Other options

| Flag | Effect |
|---|---|
| `--json` | Print the report as JSON instead of tables (for scripts / other tools). |
| `-v, --verbose` | Also show the raw underlying error message beside each plain-English one. |
| `--path` | Node path, if the workbook has no `g3mt` metadata. |

## Exit codes

`validate` (and every `g3mt` command) uses standard exit codes so it fits into
scripts and CI:

| Code | Meaning |
|---|---|
| `0` | Success — the file is valid. |
| `1` | The file has validation problems to fix. |
| `2` | A usage or input error (e.g. a missing file, or an ambiguous path with no `--path`). |

```bash
if g3mt validate data.xlsx --schema schema.json; then
  echo "ready to submit"
else
  echo "fix the reported problems first"
fi
```

## Next

- [Filling in a template](filling-templates.md) — to fix what validation found.
- [Troubleshooting](troubleshooting.md) — for less obvious problems.
