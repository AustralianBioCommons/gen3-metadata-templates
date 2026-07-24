"""Tests for :mod:`gen3_metadata_templates.schema`.

``SchemaBundle`` is the tool's only doorway to the gen3_validator engine. These
tests pin the two things the rest of the package relies on: that links are
flattened correctly (including the subgroup form that previously caused
crashes), and that the parent/child edge list respects node exclusions.
"""

from __future__ import annotations

import pytest

from gen3_metadata_templates.errors import SchemaError
from gen3_metadata_templates.schema import LinkInfo, SchemaBundle


def test_node_names_excludes_internal_helpers(mini_bundle):
    """Only real, submittable nodes should be listed.

    The ``_definitions``/``_terms``/``_settings`` helper entries are schema
    machinery, not nodes a user submits data for, so they must never appear in
    ``node_names``.
    """
    names = mini_bundle.node_names
    assert "subject" in names
    assert "_definitions" not in names
    assert "_terms" not in names
    assert "_settings" not in names


def test_links_reads_multiplicity_and_required(mini_bundle):
    """A plain link must expose its target, multiplicity and required flag.

    These three fields drive foreign-key column naming, whether the cell accepts
    a list of parents, and whether the link is mandatory — so reading them off
    the schema correctly is foundational.
    """
    (link,) = mini_bundle.links("subject")
    assert link == LinkInfo(
        name="projects", target_type="project", multiplicity="many_to_one", required=True
    )
    assert link.is_multi is False


def test_links_flattens_subgroup_form(mini_bundle):
    """Subgroup links must be flattened into their individual members.

    ``assay_file`` declares its parents inside a ``subgroup`` wrapper (used when
    a node may attach to one of several parents). The old implementation raised
    a KeyError on this shape; here both members must come back as normal links.
    """
    links = mini_bundle.links("assay_file")
    targets = {link.target_type for link in links}
    assert targets == {"sample", "core_metadata_collection"}


def test_is_multi_true_for_to_many(mini_bundle):
    """A one_to_many / many_to_many link should report ``is_multi``.

    ``is_multi`` decides whether the reader splits a cell on ';' into several
    parent references, so it must track the schema's multiplicity.
    """
    fake = LinkInfo("things", "thing", "one_to_many", True)
    assert fake.is_multi is True


def test_edges_excludes_nodes(mini_bundle):
    """Excluding a node must drop every edge that touches it.

    When ``project`` is excluded, no edge into or out of it should remain — this
    is what keeps excluded nodes (and branches reachable only through them) out
    of path enumeration.
    """
    edges = mini_bundle.edges(excluded_nodes=("program", "project"))
    touched = {n for edge in edges for n in edge}
    assert "project" not in touched
    assert "program" not in touched
    assert ("subject", "sample") in edges


def test_missing_schema_file_raises_schema_error(tmp_path):
    """A non-existent schema path should raise our typed SchemaError.

    The CLI relies on every expected input problem being a ``G3mtError`` so it
    can exit with code 2 rather than dumping a traceback.
    """
    with pytest.raises(SchemaError):
        SchemaBundle(str(tmp_path / "does_not_exist.json"))


def test_resolved_unknown_node_raises(mini_bundle):
    """Asking for a node that isn't in the schema is a typed error, not None."""
    with pytest.raises(SchemaError):
        mini_bundle.resolved("no_such_node")
