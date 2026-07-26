# Quickstart

This is the shortest path from a Gen3 schema to a validated workbook. It should
take about five minutes.

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

## Step 1 — List the available nodes

Start by seeing what node types the schema defines, and how they link together:

```bash
g3mt nodes schema.json
```

```
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Node       ┃ Links to         ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ subject    │ project          │
│ sample     │ subject          │
│ ...        │ ...              │
└────────────┴──────────────────┘
```

Pick the node you want to submit data for. We'll use `sample`.

## Step 2 — Choose the node path

Before generating anything, look at the **path** from the top of the graph down
to your node. This is the sequence of metadata you'll need to submit — parents
first, then their children:

```bash
g3mt paths schema.json sample
```

```
1. subject -> sample
```

Each arrow is a parent → child link. Here, to submit a `sample` you first submit
its `subject`. If a node can be reached more than one way, you'll see several
numbered paths and pick one (with `--path`) in the next step — see
[Path selection](generating-templates.md#choosing-a-path).

The path also tells you which sheets your template will have, and in what order.

## Step 3 — Generate the template

```bash
g3mt generate schema.json sample -o sample_template.xlsx
```

```
Wrote sample_template.xlsx  (2 sheet(s): subject -> sample)
```

The workbook has one sheet per node in the path you saw in Step 2, plus an
**Instructions** and a **Dictionary** sheet.

## Step 4 — Fill it in

Open `sample_template.xlsx` in Excel (or LibreOffice / Google Sheets).

1. **Read the Instructions sheet first** — it explains the layout in the context
   of your specific template.
2. **Fill the sheets top to bottom** (left tab to right). They're ordered so
   parents come before children — the same order you saw in Step 2.
3. On each sheet, put a unique label of your own in the **`submitter_id`**
   column for every row.
4. In a **link column** like `subject.submitter_id`, pick the parent's
   `submitter_id` from the dropdown.

A minimal filled example:

**`subject` sheet**

| submitter_id | subject_id | sex  | age |
|--------------|------------|------|-----|
| subj_1       | S1         | Male | 42  |

**`sample` sheet**

| submitter_id | subject.submitter_id | sample_id | sample_type |
|--------------|----------------------|-----------|-------------|
| samp_1       | subj_1               | X1        | Blood       |

Here `samp_1` is linked to `subj_1` because that ID is entered in its
`subject.submitter_id` cell. To attach a second sample to the same subject, add
another row and reuse `subj_1`.

## Step 5 — Validate

```bash
g3mt validate sample_template.xlsx --schema schema.json
```

If everything is correct:

```
╭───────────────────────────────────────────────────────╮
│ All good — validated 2 record(s), no problems found.  │
╰───────────────────────────────────────────────────────╯
```

If not, you get a table per sheet naming the exact cell and the problem:

```
Sheet: subject
 Cell   Column   Problem
 C3     age      'ten' isn't a whole number. This column needs a whole number (e.g. 42).
```

To get a copy of your workbook with the bad cells highlighted and commented:

```bash
g3mt validate sample_template.xlsx --schema schema.json --annotate checked.xlsx
```

Open `checked.xlsx`, fix the red cells in your **original** file, and re-run
validation until it's clean.

## Next steps

- [Filling in a template](filling-templates.md) — the details of linking,
  one-to-many, and multi-value cells.
- [Validating](validating.md) — every error type and what it means.
- [Generating templates](generating-templates.md) — path selection and
  node/column filtering.
