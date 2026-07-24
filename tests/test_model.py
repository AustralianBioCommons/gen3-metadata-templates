"""Tests for :mod:`gen3_metadata_templates.model`.

``build_template_spec`` is where a schema becomes concrete columns. Because the
writer, the Dictionary sheet, and the reader all consume this output, these
tests lock down column ordering, foreign-key headers, enum extraction, required
flags, and the handling of subgroup links and excluded nodes.
"""

from __future__ import annotations

from gen3_metadata_templates.constants import DEFAULT_EXCLUDED_NODES
from gen3_metadata_templates.model import ColumnKind, build_template_spec


def _headers(node_template):
    return [c.header for c in node_template.columns]


def test_column_order_pk_then_links_then_required_then_optional(mini_bundle):
    """Columns follow a fixed, submitter-friendly order.

    Putting submitter_id first, then the parent links, then required fields,
    then optional ones, means the columns a user *must* fill are grouped on the
    left where they will see them first.
    """
    spec = build_template_spec(mini_bundle, "sample", ["subject", "visit", "sample"])
    sample = spec.node_template("sample")
    headers = _headers(sample)

    assert headers[0] == "submitter_id"
    # Links come next, ordered by parent position in the path.
    assert headers[1] == "subject.submitter_id"
    assert headers[2] == "visit.submitter_id"
    # sample_type is required, project_id is optional -> required comes first.
    assert headers.index("sample_type") < headers.index("project_id")


def test_foreign_key_header_from_target_type(mini_bundle):
    """The link column is named after the parent it points to, not the link name."""
    spec = build_template_spec(mini_bundle, "visit", ["subject", "visit"])
    visit = spec.node_template("visit")
    fk = visit.column_by_header("subject.submitter_id")
    assert fk is not None
    assert fk.kind is ColumnKind.LINK
    assert fk.link_target == "subject"


def test_enum_values_are_real_not_the_word_enum(mini_bundle):
    """Enum columns must carry their actual allowed values.

    The old extractor collapsed every enum to the literal string "enum", which
    is useless for building a dropdown. Here the real choices must survive.
    """
    spec = build_template_spec(mini_bundle, "subject", ["subject"])
    subject = spec.node_template("subject")
    sex = subject.column_by_prop("sex")
    assert sex.data_type == "enum"
    assert sex.enum == ("Male", "Female", "Unknown")


def test_subgroup_link_becomes_a_column(mini_bundle):
    """A link declared inside a subgroup still produces a foreign-key column.

    ``assay_file`` attaches to ``sample`` via a subgroup link. The template for
    the sample->assay_file path must include that FK column; the old code
    crashed here.
    """
    spec = build_template_spec(mini_bundle, "assay_file", ["subject", "sample", "assay_file"])
    assay = spec.node_template("assay_file")
    assert assay.column_by_header("sample.submitter_id") is not None


def test_excluded_node_gets_no_sheet(mini_bundle):
    """Excluded nodes must not appear as node templates.

    core_metadata_collection is excluded by default, so even though assay_file
    links to it, no core_metadata_collection sheet should be produced.
    """
    spec = build_template_spec(
        mini_bundle,
        "assay_file",
        ["subject", "sample", "assay_file"],
        excluded_nodes=DEFAULT_EXCLUDED_NODES,
    )
    nodes = [n.node for n in spec.nodes]
    assert "core_metadata_collection" not in nodes


def test_excluded_link_target_produces_no_fk_column(mini_bundle):
    """A link to an excluded/off-path parent must not become a column.

    assay_file's link to core_metadata_collection (excluded) should be dropped,
    otherwise the sheet would have a column pointing at a sheet that doesn't
    exist.
    """
    spec = build_template_spec(
        mini_bundle,
        "assay_file",
        ["subject", "sample", "assay_file"],
        excluded_nodes=DEFAULT_EXCLUDED_NODES,
    )
    assay = spec.node_template("assay_file")
    assert assay.column_by_header("core_metadata_collection.submitter_id") is None


def test_required_link_marked_required(mini_bundle):
    """A link listed in the node's ``required`` array is a required column.

    ``sample`` requires its ``subjects`` link, so that FK column must be flagged
    required even though the link's own ``required`` field is false.
    """
    spec = build_template_spec(mini_bundle, "sample", ["subject", "sample"])
    sample = spec.node_template("sample")
    fk = sample.column_by_header("subject.submitter_id")
    assert fk.required is True


def test_excluded_columns_are_dropped(mini_bundle):
    """System/injected properties named in the exclude list never appear."""
    spec = build_template_spec(mini_bundle, "subject", ["subject"])
    subject = spec.node_template("subject")
    headers = _headers(subject)
    assert "type" not in headers
    assert "state" not in headers
    assert "created_datetime" not in headers
