# Concepts

A little vocabulary makes the rest of the documentation (and the tool's output)
much easier to follow. If you already work with Gen3 schemas, you can skip to
[Generating templates](generating-templates.md).

## A schema is a graph

A Gen3 **schema** describes a data model as a graph. The pieces are:

- **Nodes** — the *types* of thing you can submit: `subject`, `sample`,
  `sequencing_file`, and so on. Each node has a set of **properties**.
- **Links** — the parent/child relationships between nodes. A `sample` links to
  a `subject`; a file links to a `sample`. Data flows downward: parents are
  submitted before their children.

You can see the nodes and their links for any schema with:

```bash
g3mt nodes schema.json
```

## Properties have types and rules

Every property on a node has a **data type** (text, whole number, decimal,
true/false, a date, or a list) and may carry extra rules:

- **Required** — the property must be filled in on every record.
- **Enum** — only a fixed set of values is allowed (e.g. `sex` is one of
  `Male`, `Female`, `Unknown`). These become dropdowns in the template.
- **Pattern** — the text must match a specific format (e.g. a consent code like
  `C001`).

The generated **Dictionary** sheet lists every property's type, whether it's
required, its description, and its allowed values.

## `submitter_id` — your handle for a row

Every submittable node has a `submitter_id`: a label **you** choose to identify
one record. It only has to be unique within its sheet, and it can be any text
you like (`subject_001`, `patientA`, …). It is the calling card for that row.

`submitter_id` does two jobs:

1. It identifies the row within its own node.
2. It's what **child rows point at** to declare their parent.

## Links and one-to-many

When a child node links to a parent, the template gives it a column named after
the parent: `subject.submitter_id` on the `sample` sheet, for example. You fill
that cell with the parent's `submitter_id`.

This is how relationships are expressed without any special syntax:

- **One parent, one child** — one sample row referencing one subject.
- **One parent, many children (one-to-many)** — several sample rows that all put
  the *same* `subject.submitter_id`. Reusing the ID is the whole mechanism.
- **A child with several parents** — separate the parents' IDs in the cell with
  a semicolon (`;`), where the schema allows it.

See [Filling in a template](filling-templates.md) for worked examples.

## Paths

Because the schema is a graph, a node can be reachable by more than one chain of
parents. Suppose a `sample` can link directly to a `subject`, or to a `subject`
via a `visit`:

```
subject -> sample
subject -> visit -> sample
```

Both are valid "paths" to `sample`. A template covers exactly one path — it
decides which sheets the workbook contains. When there's more than one, `g3mt`
asks you to choose (or you pass `--path`). List the paths to a node with:

```bash
g3mt paths schema.json sample
```

## Excluded nodes

Some nodes are almost never filled in by a submitter:

- `program` and `project` are usually created by data administrators.
- `core_metadata_collection` and `acknowledgement` are optional housekeeping.

`g3mt` leaves these four out of templates by default. You can bring any of them
back with `--include-node`, or exclude more with `--exclude-node`. See
[Generating templates](generating-templates.md#filtering-nodes-and-columns).
