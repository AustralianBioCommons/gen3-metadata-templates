"""Tests for :mod:`gen3_metadata_templates.schema`.

``SchemaBundle`` is the tool's only doorway to the gen3_validator engine. These
tests pin the two things the rest of the package relies on: that links are
flattened correctly (including the subgroup form that previously caused
crashes), and that the parent/child edge list respects node exclusions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gen3_metadata_templates.errors import SchemaError, UnknownCategoryError
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


def test_schema_version_reads_dict_version(mini_bundle):
    """The dictionary version is read from ``_settings.yaml/_dict_version``.

    Recording which schema version a template came from lets us later warn when
    someone validates a file against a different version, so reading it must work.
    """
    assert mini_bundle.schema_version == "0.1.0"


def test_schema_version_is_none_when_not_declared(tmp_path, mini_schema_path):
    """A bundle that declares no version reports None rather than erroring.

    Not every bundle sets ``_dict_version``; treating "no version" as simply
    unknown keeps the version-mismatch check optional instead of a hard failure.
    """
    import json

    data = json.loads(Path(mini_schema_path).read_text())
    data["_settings.yaml"].pop("_dict_version", None)
    unversioned = tmp_path / "unversioned_schema.json"
    unversioned.write_text(json.dumps(data))

    assert SchemaBundle(str(unversioned)).schema_version is None


class _FakeResponse:
    """Minimal stand-in for the object urllib.request.urlopen returns."""

    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


def test_schema_bundle_loads_from_url(monkeypatch, mini_schema_path):
    """A schema can be loaded from an http(s) URL, not just a local file.

    Users often point at a schema published on GitHub (a raw file URL) rather
    than a local copy. The bytes are downloaded, written to a temp file, and
    resolved exactly as a local file would be. We monkeypatch the download so the
    test needs no network.
    """
    schema_bytes = Path(mini_schema_path).read_bytes()

    def fake_urlopen(url, timeout=None):
        assert url.startswith("https://")
        return _FakeResponse(schema_bytes)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    bundle = SchemaBundle("https://example.com/schema.json")
    assert "subject" in bundle.node_names
    assert bundle.schema_path == "https://example.com/schema.json"


def test_url_download_failure_raises_schema_error(monkeypatch):
    """A network/HTTP failure surfaces as our typed SchemaError, not a raw traceback.

    The CLI relies on every expected input problem being a G3mtError so it can
    exit cleanly (code 2) instead of dumping a stack trace at the user.
    """
    import urllib.error

    def boom(url, timeout=None):
        raise urllib.error.URLError("host unreachable")

    monkeypatch.setattr("urllib.request.urlopen", boom)

    with pytest.raises(SchemaError):
        SchemaBundle("https://example.com/schema.json")


def test_url_with_non_json_content_raises_schema_error(monkeypatch):
    """If a URL returns something that isn't JSON (e.g. an HTML 404 page), say so.

    Pointing at a GitHub *blob* page instead of the *raw* file is an easy
    mistake; the error should make clear the content wasn't a JSON schema.
    """

    def fake_urlopen(url, timeout=None):
        return _FakeResponse(b"<html>Not Found</html>")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(SchemaError):
        SchemaBundle("https://example.com/not-a-schema.html")


# --- categories -----------------------------------------------------------
#
# Categories are how a researcher asks for "every clinical sheet" without
# knowing the individual node names, so the grouping has to be exact.


def test_category_returns_the_declared_category(mini_bundle):
    """A node reports the category the schema gives it."""
    assert mini_bundle.category("visit") == "clinical"
    assert mini_bundle.category("sample") == "biospecimen"


def test_category_is_none_when_the_node_declares_none(mini_bundle, monkeypatch):
    """A node with no category reports None rather than raising.

    Not every Gen3 dictionary categorises every node. Treating "no category" as
    simply unknown keeps such a node usable everywhere else in the tool.
    """
    original = mini_bundle.resolved

    def without_category(node):
        data = dict(original(node))
        if node == "visit":
            data.pop("category", None)
        return data

    monkeypatch.setattr(mini_bundle, "resolved", without_category)
    assert mini_bundle.category("visit") is None


def test_nodes_by_category_groups_and_sorts(mini_bundle):
    """Every node is grouped under its category, with names sorted.

    Sorting matters because this drives both the `g3mt categories` table and the
    order targets are resolved in, and both must be identical run to run.
    """
    assert mini_bundle.nodes_by_category() == {
        "administrative": ["core_metadata_collection", "program", "project", "subject"],
        "biospecimen": ["sample"],
        "clinical": ["visit"],
        "data_file": ["assay_file"],
    }


def test_nodes_by_category_omits_internal_helpers(mini_bundle):
    """The schema's internal helper entries are never presented as nodes.

    ``_definitions``/``_terms``/``_settings`` are schema machinery, not things a
    user submits, so they must not appear in any category listing.
    """
    listed = {n for nodes in mini_bundle.nodes_by_category().values() for n in nodes}
    assert not any(n.startswith("_") for n in listed)


def test_nodes_in_category_is_case_insensitive(mini_bundle):
    """Typing --category Clinical works as well as --category clinical."""
    assert mini_bundle.nodes_in_category("Clinical") == ["visit"]


def test_unknown_category_lists_what_is_available(mini_bundle):
    """An unknown category names the real ones instead of failing blankly.

    Someone who guesses a category name should be shown the actual options
    rather than having to go and read the schema.
    """
    with pytest.raises(UnknownCategoryError) as exc:
        mini_bundle.nodes_in_category("not_a_category")
    message = str(exc.value)
    assert "clinical" in message and "data_file" in message


def test_unknown_category_suggests_a_close_match(mini_bundle):
    """A near-miss spelling gets a 'did you mean' hint."""
    with pytest.raises(UnknownCategoryError) as exc:
        mini_bundle.nodes_in_category("clincal")
    assert "Did you mean 'clinical'" in str(exc.value)
