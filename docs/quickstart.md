# Quickstart

This is the shortest path from a Gen3 schema to a validated workbook.

## Install

Install `g3mt` (this is the command the tool provides):

```bash
pipx install gen3-metadata-templates
```

Check it worked:

```bash
g3mt version
```

You'll also need a **Gen3 schema bundle** — a single `.json` file containing your
node definitions. Throughout these docs it's called `schema.json`; substitute
your own path.

!!! note "Schema can be a URL too"
    Anywhere `schema.json` appears you can pass an `http(s)://` URL to a
    published bundle instead of a local file, e.g.
    `g3mt nodes https://example.com/path/to/schema.json`.

---

## The quick way: a whole category at once

Most people submitting metadata want everything of one kind — all their
**clinical** data, say. That's one command.

### 1. See what's in the schema

```bash
g3mt categories schema.json
```

```
Category               Nodes  Node names
administrative             6  acknowledgement, core_metadata_collection, program, ...
biospecimen                1  sample
clinical                   8  blood_pressure_test, clinical_descriptor, demographic,
                              exposure, lab_result, medical_history, medication, subject
data_file                  8  genomics_file, imaging_file, ...
```

### 2. Generate the template

```bash
g3mt generate schema.json --category clinical -o clinical_template.xlsx
```

```
Wrote clinical_template.xlsx  (8 sheets)

Fill order (parents before children; sheets at the same indent are independent)
  subject
    clinical_descriptor
      blood_pressure_test
      demographic
      exposure
      lab_result
      medical_history
      medication

Note: 'subject' links to 'project', which is not in this template.
  Ask your data administrator, or add the sheet with --include-node project.
```

`g3mt` worked out every node you need and put them in the order to fill them in.

### 3. Fill it in

Open the workbook and **read the Instructions sheet first** — it repeats the fill
order and explains the layout for your specific template.

- Give every row a **`submitter_id`** of your own (any text, unique on that sheet).
- Fill sheets **top to bottom**; sheets at the same indent don't depend on each other.
- In a link column like `clinical_descriptor.submitter_id`, pick the parent from
  the dropdown.
- **You don't have to fill in every sheet.** Leave out the ones you have no data
  for — an empty sheet simply isn't submitted.

**`subject`**

| submitter_id | patient_id |
|--------------|------------|
| subj_1       | P01        |

**`clinical_descriptor`** — one row per timepoint. Both rows reuse `subj_1`,
which is exactly how "this participant was seen twice" is expressed:

| submitter_id | subject.submitter_id | timepoint_label |
|--------------|----------------------|-----------------|
| cd_1         | subj_1               | baseline        |
| cd_2         | subj_1               | year_2          |

**`demographic`** — one row per timepoint, each pointing at the right one:

| submitter_id | clinical_descriptor.submitter_id | sex  |
|--------------|----------------------------------|------|
| demo_1       | cd_1                             | Male |
| demo_2       | cd_2                             | Male |

### 4. Validate

```bash
g3mt validate clinical_template.xlsx --schema schema.json
```

```
╭───────────────────────────────────────────────────────╮
│ All good — validated 5 record(s), no problems found.  │
╰───────────────────────────────────────────────────────╯
```

If something's wrong you get the exact cell and a plain explanation:

```
Sheet: demographic
 Cell   Column                            Problem
 B3     clinical_descriptor.submitter_id  'ghost' doesn't match any submitter_id on the
                                          'clinical_descriptor' sheet. Check for typos,
                                          or add that row first.
```

Add `--annotate checked.xlsx` to get a copy of your workbook with the problem
cells highlighted and commented.

**That's the whole workflow.** If a category is what you needed, you're done.

---

## Going further: choosing your own nodes

When a category isn't the right grouping — you want one specific node, or an
unusual combination — select nodes yourself.

### List the nodes

```bash
g3mt nodes schema.json
```

```
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Category    ┃ Node                ┃ Links to            ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ biospecimen │ sample              │ clinical_descriptor │
│ clinical    │ blood_pressure_test │ clinical_descriptor │
│ clinical    │ clinical_descriptor │ subject             │
│ clinical    │ subject             │ project             │
│ ...         │ ...                 │ ...                 │
└─────────────┴─────────────────────┴─────────────────────┘
```

Rows are grouped by category, so everything of one kind sits together.

### Check the path to a node

The **path** is the chain of parents down to your node — the sequence of
metadata you'll need to submit:

```bash
g3mt paths schema.json sample
```

```
1. subject -> sample
```

Each arrow is a parent → child link, so to submit a `sample` you first submit its
`subject`. If a node can be reached more than one way you'll see several numbered
paths and choose one with `--path`.

### Generate for one node, or several

```bash
# one node (and its ancestors)
g3mt generate schema.json sample -o sample_template.xlsx

# several nodes at once — their paths are merged into one workbook
g3mt generate schema.json --node subject --node sample -o study_template.xlsx

# a category plus an extra node
g3mt generate schema.json --category clinical --node imaging_file
```

With a single node, `g3mt` asks you to choose if the path is ambiguous. With
several, it takes the shortest route for each and tells you which ones had
alternatives, so a big selection never turns into a wall of questions:

```bash
g3mt generate schema.json --node sample --path sample=2   # pick route 2 for sample
```

Then fill and validate exactly as above.

## Next steps

- [Concepts](concepts.md) — nodes, links, categories, paths, and `submitter_id`.
- [Generating templates](generating-templates.md) — every selection and filter option.
- [Filling in a template](filling-templates.md) — linking, one-to-many, multi-value cells.
- [Validating](validating.md) — every error type and what it means.
