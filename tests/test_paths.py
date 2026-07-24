"""Tests for :mod:`gen3_metadata_templates.paths`.

When a node is reachable by more than one chain of parents, the submitter must
pick which chain their template covers. These tests verify enumeration is
complete and deterministic, that a chosen path can be resolved by index or by
name, and that ambiguity is refused loudly rather than guessed.
"""

from __future__ import annotations

import pytest

from gen3_metadata_templates.constants import DEFAULT_EXCLUDED_NODES
from gen3_metadata_templates.errors import AmbiguousPathError, UnknownNodeError
from gen3_metadata_templates.paths import enumerate_paths, resolve_path


def test_enumerate_finds_all_paths_to_a_node(mini_bundle):
    """``sample`` has two distinct routes and both must be enumerated.

    In the mini schema a sample can be linked straight to a subject, or to a
    subject via a visit. A submitter needs to see both so they can choose, so
    losing either one would be a real bug.
    """
    paths = enumerate_paths(mini_bundle, "sample", DEFAULT_EXCLUDED_NODES)
    assert paths == [
        ["subject", "sample"],
        ["subject", "visit", "sample"],
    ]


def test_enumerate_is_deterministic_shortest_first(mini_bundle):
    """Paths are sorted (shortest first) so the numbering a user sees is stable.

    The CLI prints these as a numbered list and lets the user pick "path 2";
    that only works if the order is identical on every run.
    """
    a = enumerate_paths(mini_bundle, "sample", DEFAULT_EXCLUDED_NODES)
    b = enumerate_paths(mini_bundle, "sample", DEFAULT_EXCLUDED_NODES)
    assert a == b
    assert a[0] == ["subject", "sample"]


def test_enumerate_does_not_pollute_stdout(mini_bundle, capsys):
    """Enumeration must not print anything.

    The underlying gen3_validator helper prints the graph's root nodes to
    stdout; we suppress that so it can't corrupt CLI output (e.g. ``--json``).
    This test pins the redirect guard in place.
    """
    enumerate_paths(mini_bundle, "sample", DEFAULT_EXCLUDED_NODES)
    captured = capsys.readouterr()
    assert captured.out == ""


def test_unknown_node_raises(mini_bundle):
    """A target node that isn't in the schema is a typed, user-facing error."""
    with pytest.raises(UnknownNodeError):
        enumerate_paths(mini_bundle, "not_a_node", DEFAULT_EXCLUDED_NODES)


def test_resolve_path_single_candidate_returns_it(mini_bundle):
    """With only one route to a node, no choice is needed.

    ``visit`` has a single path, so ``resolve_path`` should return it without a
    ``--path`` argument or a chooser.
    """
    paths = enumerate_paths(mini_bundle, "visit", DEFAULT_EXCLUDED_NODES)
    assert len(paths) == 1
    assert resolve_path(paths) == ["subject", "visit"]


def test_resolve_path_by_index(mini_bundle):
    """A 1-based index selects the matching candidate.

    This is the scriptable, non-interactive way to pick a path (``--path 2``).
    """
    paths = enumerate_paths(mini_bundle, "sample", DEFAULT_EXCLUDED_NODES)
    assert resolve_path(paths, path_arg="2") == ["subject", "visit", "sample"]


def test_resolve_path_by_node_chain(mini_bundle):
    """A comma-separated node chain selects the exactly-matching candidate."""
    paths = enumerate_paths(mini_bundle, "sample", DEFAULT_EXCLUDED_NODES)
    assert resolve_path(paths, path_arg="subject,visit,sample") == [
        "subject",
        "visit",
        "sample",
    ]


def test_resolve_path_uses_chooser_when_ambiguous(mini_bundle):
    """When multiple paths exist and no flag is given, the injected chooser decides.

    Keeping the interactive prompt behind a callback is what lets the same
    library back both the CLI and a future Streamlit app without either owning
    the choosing logic.
    """
    paths = enumerate_paths(mini_bundle, "sample", DEFAULT_EXCLUDED_NODES)
    chosen = resolve_path(paths, chooser=lambda candidates: 1)
    assert chosen == ["subject", "visit", "sample"]


def test_resolve_path_ambiguous_without_help_raises(mini_bundle):
    """Ambiguity with no flag and no chooser must fail loudly, never guess.

    Silently picking a path would generate a template with the wrong sheets, so
    the tool refuses and tells the user how to disambiguate.
    """
    paths = enumerate_paths(mini_bundle, "sample", DEFAULT_EXCLUDED_NODES)
    with pytest.raises(AmbiguousPathError):
        resolve_path(paths)


def test_resolve_path_bad_index_raises(mini_bundle):
    """An out-of-range ``--path`` index is a clear ValueError, not a crash."""
    paths = enumerate_paths(mini_bundle, "sample", DEFAULT_EXCLUDED_NODES)
    with pytest.raises(ValueError):
        resolve_path(paths, path_arg="9")
