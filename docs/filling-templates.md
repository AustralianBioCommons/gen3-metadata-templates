# Filling in a template

This page covers the parts of filling in a workbook that trip people up:
`submitter_id`, linking rows, one-to-many relationships, and multi-value cells.
Open the **Instructions** sheet in your generated file alongside this — it's
tailored to your specific template.

## Golden rules

1. **Fill the sheets in order**, left tab to right. They're arranged so parents
   come before children.
2. **Give every row a unique `submitter_id`** on its own sheet.
3. **Link children to parents** by putting the parent's `submitter_id` in the
   `parent.submitter_id` column.
4. **Don't edit the header row (row 1) or the hint row (row 2).** Type your data
   from row 3 down.

## submitter_id

The `submitter_id` column is your own label for each row. It can be any text
(`subject_001`, `bloodA`, …) as long as it's **unique within that sheet**.
Reusing a value on two rows of the same sheet is an error (validation reports a
duplicate).

## Linking rows to a parent

A column named like `subject.submitter_id` means "which subject does this row
belong to?". Put the subject's `submitter_id` there — pick it from the dropdown
to avoid typos.

**`subject` sheet**

| submitter_id | subject_id |
|--------------|------------|
| subj_1       | S1         |
| subj_2       | S2         |

**`sample` sheet**

| submitter_id | subject.submitter_id | sample_type |
|--------------|----------------------|-------------|
| samp_1       | subj_1               | Blood       |
| samp_2       | subj_2               | Tissue      |

`samp_1` belongs to `subj_1`; `samp_2` belongs to `subj_2`.

## One-to-many: many children, one parent

To attach several children to the same parent, add a row for each child and
**reuse the same parent `submitter_id`**. There's nothing else to it.

**`sample` sheet** — three samples, all from `subj_1`:

| submitter_id | subject.submitter_id | sample_type |
|--------------|----------------------|-------------|
| samp_1       | subj_1               | Blood       |
| samp_2       | subj_1               | Tissue      |
| samp_3       | subj_1               | Saliva      |

## Multiple parents in one cell

Some links allow a single record to reference **more than one** parent. Where
the schema permits it, put several `submitter_id` values in the one cell,
separated by a semicolon (`;`):

| submitter_id | subject.submitter_id |
|--------------|----------------------|
| pool_1       | subj_1; subj_2; subj_3 |

The hint row tells you when a column accepts multiple values. (Columns that
accept a list don't get a single-select dropdown, since a dropdown can only pick
one value.)

## Lists in a property (not a link)

The same `;` rule applies to array-valued *properties*. For example, an
`aliases` column that holds several alternative identifiers:

| submitter_id | aliases            |
|--------------|--------------------|
| subj_1       | S1; S-01; SUBJ0001 |

## Types: what to type

| Type shown in the hint row | What to enter |
|---|---|
| `string` / text | Any text. |
| `integer` | A whole number, e.g. `42`. |
| `number` | A number, decimals allowed, e.g. `3.14`. |
| `boolean` | `TRUE` or `FALSE` (use the dropdown). |
| `enum` / "pick from list" | One of the dropdown values. |
| `array` / "list" | One or more values separated by `;`. |
| a date | An ISO date, e.g. `2024-01-31`. |

Leave a cell **blank** if you have no value and the column is optional. Blank
required cells are reported by validation.

## Adding more rows

The template comes with a fixed number of blank, ready-to-fill rows (5000 by
default). If you need more, regenerate the template with a larger `--rows`
value — see [Generating templates](generating-templates.md#other-options).

## When you're done

Save the file (keep it as `.xlsx`) and validate it:

```bash
g3mt validate your_file.xlsx --schema schema.json
```

See [Validating](validating.md) for what the output means.
