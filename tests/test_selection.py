"""Tests for :mod:`gen3_metadata_templates.selection`.

This module is what turns "give me every clinical sheet" into a concrete,
ordered list of nodes. Everything downstream — sheet order, the fill-order tree,
which foreign-key columns exist — is built on its output, so these tests pin the
ordering guarantees hard.

Real Gen3 dictionaries are not always tidy: clinical nodes sit at different
depths in different dictionaries, some nodes are reachable more than one way,
and a malformed schema can even contain a loop. The fixtures used here exist
specifically to cover those shapes; see ``tests/conftest.py``.
"""

from __future__ import annotations

import random

import pytest

from gen3_metadata_templates.constants import DEFAULT_EXCLUDED_NODES
from gen3_metadata_templates.errors import (
    CyclicGraphError,
    SelectionError,
    UnknownNodeError,
)
from gen3_metadata_templates.selection import layered_topological_order, resolve_selection

# --- ordering primitive ---------------------------------------------------


def test_order_puts_parents_before_children():
    """A child must never be ordered before one of its parents.

    This is the whole point of the ordering: a submitter fills sheets top to
    bottom, and a child sheet can only reference a parent row that already
    exists.
    """
    order, _ = layered_topological_order(
        ["sample", "subject", "visit"],
        [("subject", "visit"), ("visit", "sample")],
    )
    assert order == ["subject", "visit", "sample"]


def test_order_is_alphabetical_within_a_level():
    """Independent nodes are ordered by name, so the result is predictable.

    ``a``, ``b`` and ``c`` all hang off ``r`` and don't depend on each other.
    Any order would be valid, so we fix one — otherwise sheet order could drift
    between runs for no reason.
    """
    order, _ = layered_topological_order(["r", "c", "a", "b"], [("r", "b"), ("r", "a"), ("r", "c")])
    assert order == ["r", "a", "b", "c"]


def test_order_includes_a_node_with_no_edges():
    """A node that links to nothing still gets a place in the order.

    Some dictionaries have standalone nodes. Dropping them would silently omit a
    sheet the user explicitly asked for.
    """
    order, depth = layered_topological_order(["b", "a"], [])
    assert order == ["a", "b"]
    assert depth == {"a": 0, "b": 0}


def test_order_is_deterministic_under_shuffled_input():
    """The same nodes and edges always give the same order, however they arrive.

    Sheet order is written into the workbook and recorded in its metadata, so it
    must depend only on the schema's content — never on dictionary iteration
    order or the order a file happened to be serialised in.
    """
    nodes = ["subject", "visit", "sample", "assay", "extra"]
    edges = [("subject", "visit"), ("visit", "sample"), ("sample", "assay")]
    expected, _ = layered_topological_order(nodes, edges)

    for _ in range(20):
        shuffled_nodes = random.sample(nodes, len(nodes))
        shuffled_edges = random.sample(edges, len(edges))
        assert layered_topological_order(shuffled_nodes, shuffled_edges)[0] == expected


def test_depth_is_the_longest_distance_not_the_shortest():
    """A node sits below *every* parent, not just its nearest one.

    ``c`` hangs off both ``a`` (one hop) and ``b`` (two hops). Using the shortest
    distance would place ``c`` at the same level as ``b`` and could order it
    before its own parent. Taking the longest distance guarantees it comes after.
    """
    order, depth = layered_topological_order(["a", "b", "c"], [("a", "b"), ("a", "c"), ("b", "c")])
    assert depth["c"] == 2
    assert order.index("c") > order.index("b")


def test_order_ignores_a_self_link():
    """A node listed as its own parent doesn't deadlock the ordering.

    A malformed dictionary can contain ``z -> z``. A node can't depend on
    itself, so the edge is ignored rather than treated as an unsatisfiable
    dependency (which would look like a cycle).
    """
    order, depth = layered_topological_order(["z"], [("z", "z")])
    assert order == ["z"]
    assert depth == {"z": 0}


def test_order_raises_on_a_cycle():
    """Nodes that link in a loop cannot be ordered, and we say so plainly.

    Silently dropping them (as the schema engine's own sort does) would produce
    a template quietly missing sheets. The message names the nodes and frames it
    as a schema problem so nobody wastes time rewording their command.
    """
    with pytest.raises(CyclicGraphError) as exc:
        layered_topological_order(["a", "b"], [("a", "b"), ("b", "a")])
    message = str(exc.value)
    assert "a" in message and "b" in message
    assert "schema" in message.lower()


# --- expected node sets and paths on realistic clinical shapes -------------


def test_clinical_hub_selection_has_the_expected_nodes_and_order(clinical_hub_bundle):
    """The common clinical shape resolves to exactly the expected sheets.

    This fixture mirrors a real dictionary: measurement nodes hang off a
    ``clinical_descriptor`` hub, which hangs off ``subject``. Asking for the
    clinical category must produce those five sheets, parents first, and must
    leave out ``sample`` (which is biospecimen, not clinical) even though it
    also hangs off the hub.
    """
    selection = resolve_selection(
        clinical_hub_bundle,
        clinical_hub_bundle.nodes_in_category("clinical"),
        excluded_nodes=DEFAULT_EXCLUDED_NODES,
        category="clinical",
    )
    assert selection.nodes == [
        "subject",
        "clinical_descriptor",
        "blood_pressure_test",
        "demographic",
        "medical_history",
    ]
    assert "sample" not in selection.nodes


def test_clinical_hub_paths_and_depths_are_exact(clinical_hub_bundle):
    """Each target records the exact chain of parents it was reached through.

    The recorded path is what tells a submitter the order to fill things in, and
    the depth is what indents the fill-order tree, so both are pinned exactly.
    """
    selection = resolve_selection(
        clinical_hub_bundle,
        clinical_hub_bundle.nodes_in_category("clinical"),
        excluded_nodes=DEFAULT_EXCLUDED_NODES,
    )
    assert selection.resolution("demographic").path == [
        "subject",
        "clinical_descriptor",
        "demographic",
    ]
    assert selection.depth == {
        "subject": 0,
        "clinical_descriptor": 1,
        "blood_pressure_test": 2,
        "demographic": 2,
        "medical_history": 2,
    }


def test_clinical_nodes_at_mixed_depths_are_ordered_correctly(clinical_flat_bundle):
    """Not every dictionary hangs all clinical nodes off one hub.

    Here one measurement hangs off ``subject`` directly while another sits below
    a hub, plus there's a standalone clinical node with no links at all. The
    ordering must place each at its own correct level rather than assuming a
    uniform two-level shape.
    """
    selection = resolve_selection(
        clinical_flat_bundle,
        clinical_flat_bundle.nodes_in_category("clinical"),
        excluded_nodes=DEFAULT_EXCLUDED_NODES,
        category="clinical",
    )
    assert selection.depth == {
        "standalone": 0,
        "subject": 0,
        "direct_measure": 1,
        "visit_hub": 1,
        "deep_measure": 2,
    }
    # Parents still come before children despite the uneven shape.
    assert selection.nodes.index("visit_hub") < selection.nodes.index("deep_measure")
    assert selection.nodes.index("subject") < selection.nodes.index("direct_measure")


def test_a_disconnected_node_still_gets_a_sheet(clinical_flat_bundle):
    """A clinical node linked to nothing is still included when asked for."""
    selection = resolve_selection(
        clinical_flat_bundle,
        clinical_flat_bundle.nodes_in_category("clinical"),
        excluded_nodes=DEFAULT_EXCLUDED_NODES,
    )
    assert "standalone" in selection.nodes
    assert selection.resolution("standalone").path == ["standalone"]


def test_union_merges_shared_ancestors(mini_bundle):
    """Two targets sharing an ancestor produce one sheet for it, not two.

    ``visit`` and ``sample`` both descend from ``subject``. The workbook must
    contain a single ``subject`` sheet.
    """
    selection = resolve_selection(
        mini_bundle, ["visit", "sample"], excluded_nodes=DEFAULT_EXCLUDED_NODES
    )
    assert selection.nodes.count("subject") == 1
    assert set(selection.nodes) == {"subject", "visit", "sample"}


def test_targets_are_deduped_preserving_request_order(mini_bundle):
    """Asking for the same node twice doesn't duplicate anything."""
    selection = resolve_selection(
        mini_bundle, ["sample", "visit", "sample"], excluded_nodes=DEFAULT_EXCLUDED_NODES
    )
    assert selection.targets == ["sample", "visit"]


# --- ambiguity ------------------------------------------------------------


def test_ambiguous_target_uses_the_shortest_path_and_records_the_rest(mini_bundle):
    """With several routes we take the shortest, but remember the alternatives.

    Prompting once per target would mean a wall of questions when someone asks
    for a whole category. Instead the shortest route is used and the fact that
    there was a choice is recorded, so the CLI can mention it and offer an
    override.
    """
    selection = resolve_selection(mini_bundle, ["sample"], excluded_nodes=DEFAULT_EXCLUDED_NODES)
    resolution = selection.resolution("sample")
    assert resolution.path == ["subject", "sample"]
    assert resolution.chosen_by == "shortest"
    assert resolution.had_alternatives
    assert len(resolution.candidates) == 2
    assert selection.ambiguous == [resolution]


def test_equal_length_paths_resolve_alphabetically_and_stably(ambiguous_bundle):
    """When two routes are the same length, the tie is broken predictably.

    ``d`` can be reached via ``b`` or via ``c`` in exactly the same number of
    steps. Without a defined tie-break the chosen sheets could differ between
    runs, so the alphabetically-first chain always wins.
    """
    first = resolve_selection(ambiguous_bundle, ["d"], excluded_nodes=DEFAULT_EXCLUDED_NODES)
    resolution = first.resolution("d")
    assert resolution.path == ["a", "b", "d"]
    assert len(resolution.candidates) == 2

    for _ in range(5):
        again = resolve_selection(ambiguous_bundle, ["d"], excluded_nodes=DEFAULT_EXCLUDED_NODES)
        assert again.resolution("d").path == resolution.path
        assert again.nodes == first.nodes


def test_path_override_by_index_selects_a_different_route(mini_bundle):
    """An explicit override wins over the shortest-path default."""
    selection = resolve_selection(
        mini_bundle,
        ["sample"],
        excluded_nodes=DEFAULT_EXCLUDED_NODES,
        path_overrides={"sample": "2"},
    )
    assert selection.resolution("sample").chosen_by == "override"
    assert "visit" in selection.nodes


def test_path_override_by_node_chain_selects_a_different_route(mini_bundle):
    """An override can name the chain instead of its number."""
    selection = resolve_selection(
        mini_bundle,
        ["sample"],
        excluded_nodes=DEFAULT_EXCLUDED_NODES,
        path_overrides={"sample": "subject,visit,sample"},
    )
    assert selection.resolution("sample").path == ["subject", "visit", "sample"]


def test_path_override_that_matches_nothing_is_rejected(mini_bundle):
    """A bogus override fails loudly rather than falling back to a guess."""
    with pytest.raises(ValueError):
        resolve_selection(
            mini_bundle,
            ["sample"],
            excluded_nodes=DEFAULT_EXCLUDED_NODES,
            path_overrides={"sample": "subject,nonsense,sample"},
        )


def test_ambiguity_inside_a_category_never_raises(mini_bundle):
    """Selecting a whole category must not fail just because a route was ambiguous.

    The single-target command still refuses to guess, but a category selection
    would be unusable if one ambiguous member could abort the whole thing.
    """
    selection = resolve_selection(
        mini_bundle,
        ["sample", "visit"],
        excluded_nodes=DEFAULT_EXCLUDED_NODES,
        category="pretend",
    )
    assert selection.nodes


# --- cycles and malformed graphs on a real bundle --------------------------


def test_selecting_nodes_in_a_loop_raises(cyclic_bundle):
    """A loop between two selected nodes is reported, not silently truncated."""
    with pytest.raises(CyclicGraphError) as exc:
        resolve_selection(cyclic_bundle, ["x", "y"], excluded_nodes=DEFAULT_EXCLUDED_NODES)
    assert "x" in str(exc.value) and "y" in str(exc.value)


def test_a_self_referencing_node_is_selectable(cyclic_bundle):
    """A node that links to itself still produces a usable single sheet."""
    selection = resolve_selection(cyclic_bundle, ["z"], excluded_nodes=DEFAULT_EXCLUDED_NODES)
    assert selection.nodes == ["z"]


def test_a_loop_elsewhere_in_the_schema_is_harmless(cyclic_bundle):
    """A cycle the selection never touches must not break an unrelated template.

    Edges are restricted to the selected nodes before ordering, so a broken
    corner of a dictionary doesn't stop someone generating a template from a
    healthy part of it.
    """
    selection = resolve_selection(
        cyclic_bundle, ["clean_child"], excluded_nodes=DEFAULT_EXCLUDED_NODES
    )
    assert selection.nodes == ["clean_root", "clean_child"]


# --- selection rules ------------------------------------------------------


def test_root_node_selection_is_a_single_node(mini_bundle):
    """A node with no parents gives a one-sheet template rather than an error."""
    selection = resolve_selection(mini_bundle, ["subject"], excluded_nodes=DEFAULT_EXCLUDED_NODES)
    assert selection.nodes == ["subject"]


def test_unknown_target_raises(mini_bundle):
    """A misspelled node name is a clear, typed error."""
    with pytest.raises(UnknownNodeError):
        resolve_selection(mini_bundle, ["not_a_node"], excluded_nodes=DEFAULT_EXCLUDED_NODES)


def test_explicitly_selected_node_that_is_also_excluded_raises(mini_bundle):
    """Asking for a node and excluding it in the same breath is contradictory.

    Silently honouring one over the other would give the user a workbook that
    isn't what they asked for, so we make them resolve the contradiction.
    """
    with pytest.raises(SelectionError) as exc:
        resolve_selection(
            mini_bundle,
            ["sample"],
            excluded_nodes=("sample",),
            strict_targets=("sample",),
        )
    assert "sample" in str(exc.value)


def test_category_member_that_is_excluded_is_skipped_not_fatal(mini_bundle):
    """Excluding one member of a category trims it instead of failing.

    The user didn't name that node individually — it just came along with the
    category — so honouring the exclusion and reporting it is the helpful
    behaviour.
    """
    selection = resolve_selection(
        mini_bundle,
        ["sample", "visit"],
        excluded_nodes=("sample",),
        category="pretend",
    )
    assert selection.skipped == ["sample"]
    assert "sample" not in selection.nodes
    assert "visit" in selection.nodes


def test_everything_excluded_raises(mini_bundle):
    """If nothing survives the exclusions there's no template to write."""
    with pytest.raises(SelectionError) as exc:
        resolve_selection(mini_bundle, ["sample"], excluded_nodes=("sample",), category="pretend")
    assert "pretend" in str(exc.value)


def test_no_targets_raises(mini_bundle):
    """An empty selection is a usage error, not an empty workbook."""
    with pytest.raises(SelectionError):
        resolve_selection(mini_bundle, [], excluded_nodes=DEFAULT_EXCLUDED_NODES)
