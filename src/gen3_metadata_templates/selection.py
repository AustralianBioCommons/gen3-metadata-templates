"""Turning a set of wanted nodes into an ordered node list for one template.

A template can cover several target nodes at once — every clinical node, say.
Each target brings its own chain of ancestors, and those chains overlap. This
module unions them and orders the result parents-first, so the workbook's sheets
can be filled top to bottom without ever referring to a parent that doesn't
exist yet.

The ordering deliberately does **not** reuse ``gen3_validator.dict.get_node_order``:
that helper drops nodes that appear in no edge, silently discards cycles, forces
``core_metadata_collection`` last, and orders siblings by the schema file's key
order — so re-serialising a schema could reshuffle sheet order that is already
baked into workbooks people have filled in.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from gen3_metadata_templates.errors import CyclicGraphError, SelectionError
from gen3_metadata_templates.paths import enumerate_paths, resolve_path
from gen3_metadata_templates.schema import SchemaBundle


@dataclass(frozen=True)
class TargetResolution:
    """How one requested target node was turned into a concrete path.

    ``candidates`` keeps every path that was available so the CLI can tell the
    user "this node could be reached another way" instead of silently choosing.
    """

    target: str
    path: List[str]
    candidates: List[List[str]]
    chosen_by: str  # "only" | "shortest" | "override"

    @property
    def had_alternatives(self) -> bool:
        return len(self.candidates) > 1


@dataclass
class NodeSelection:
    """The resolved node set for a template: what's in it, in what order, and why."""

    targets: List[str]  # requested targets, deduped, in request order
    nodes: List[str]  # the union, excluded removed, parents before children
    depth: Dict[str, int]  # node -> level; 0 means no parent inside the set
    resolutions: List[TargetResolution] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)  # dropped by --exclude-node
    category: Optional[str] = None  # set when a category drove the selection

    @property
    def ambiguous(self) -> List[TargetResolution]:
        """Targets that could have been reached another way."""
        return [r for r in self.resolutions if r.had_alternatives]

    def resolution(self, target: str) -> Optional[TargetResolution]:
        return next((r for r in self.resolutions if r.target == target), None)


def layered_topological_order(
    nodes: Iterable[str],
    edges: Iterable[Tuple[str, str]],
) -> Tuple[List[str], Dict[str, int]]:
    """Order ``nodes`` parents-first, grouped by level, alphabetical within a level.

    ``depth`` is the *longest* distance from a node with no parent in the set, so
    a child is always deeper than every one of its parents. Sorting by
    ``(depth, name)`` is therefore always a valid parents-first order, and it
    groups nodes into levels — which is what makes the fill-order tree in the
    Instructions sheet readable.

    The result depends only on the node and edge *sets*, never on the order they
    arrive in, so the same schema always produces the same sheet order.

    Self-links (a node listed as its own parent) are ignored; a node cannot
    depend on itself.

    :returns: ``(ordered_nodes, depth_by_node)``
    :raises CyclicGraphError: if the nodes link to each other in a loop.
    """
    node_set = set(nodes)
    edge_set = {(p, c) for p, c in edges if p in node_set and c in node_set and p != c}

    in_degree: Dict[str, int] = {n: 0 for n in node_set}
    children: Dict[str, set] = defaultdict(set)
    for parent, child in edge_set:
        if child not in children[parent]:
            children[parent].add(child)
            in_degree[child] += 1

    depth: Dict[str, int] = {n: 0 for n in node_set if in_degree[n] == 0}
    queue = deque(sorted(depth))
    while queue:
        node = queue.popleft()
        for child in sorted(children[node]):
            depth[child] = max(depth.get(child, 0), depth[node] + 1)
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(depth) != len(node_set):
        raise CyclicGraphError(sorted(node_set - set(depth)))

    return sorted(node_set, key=lambda n: (depth[n], n)), depth


def resolve_selection(
    bundle: SchemaBundle,
    targets: Sequence[str],
    *,
    excluded_nodes: Sequence[str] = (),
    path_overrides: Optional[Mapping[str, str]] = None,
    category: Optional[str] = None,
    strict_targets: Sequence[str] = (),
) -> NodeSelection:
    """Union the ancestor paths of every target and order the result.

    Each target is resolved to a single path: an explicit override if given,
    otherwise the only path, otherwise the shortest. This never prompts — where
    a target could have been reached another way, that is recorded on its
    :class:`TargetResolution` for the caller to report.

    :param strict_targets: the targets the user named explicitly. Excluding one
        of these is an error (they asked for it and to drop it); excluding a
        node that merely came along with a category is silently skipped.
    :raises SelectionError: nothing to select, or an explicit target was excluded.
    :raises UnknownNodeError: a target isn't in the schema.
    :raises CyclicGraphError: the selected nodes link to each other in a loop.
    """
    excluded = {n for n in excluded_nodes}
    strict = {n for n in strict_targets}
    overrides = dict(path_overrides or {})

    wanted: List[str] = []
    for target in targets:
        name = (target or "").strip()
        if name and name not in wanted:
            wanted.append(name)
    if not wanted:
        raise SelectionError("No target nodes were given.")

    for name in wanted:
        if not bundle.has_node(name):
            from gen3_metadata_templates.errors import UnknownNodeError

            raise UnknownNodeError(f"Node '{name}' does not exist in the schema.")

    kept: List[str] = []
    skipped: List[str] = []
    for name in wanted:
        if name in excluded:
            if name in strict:
                raise SelectionError(
                    f"You selected '{name}' but also excluded it with --exclude-node. "
                    f"Drop one or the other."
                )
            skipped.append(name)
        else:
            kept.append(name)

    if not kept:
        where = f"category '{category}'" if category else "your selection"
        raise SelectionError(
            f"Every node in {where} was excluded, so there is nothing to generate."
        )

    resolutions: List[TargetResolution] = []
    for name in kept:
        candidates = enumerate_paths(bundle, name, excluded_nodes)
        override = overrides.get(name)
        if override is not None:
            path = resolve_path(candidates, path_arg=override)
            chosen_by = "override"
        elif len(candidates) == 1:
            path = candidates[0]
            chosen_by = "only"
        else:
            # enumerate_paths sorts by (length, names), so [0] is the shortest
            # and ties break alphabetically — deterministic across runs.
            path = candidates[0]
            chosen_by = "shortest"
        resolutions.append(
            TargetResolution(
                target=name, path=list(path), candidates=candidates, chosen_by=chosen_by
            )
        )

    union = {node for r in resolutions for node in r.path} - excluded
    edges = [(p, c) for p, c in bundle.edges(excluded_nodes) if p in union and c in union]
    ordered, depth = layered_topological_order(union, edges)

    return NodeSelection(
        targets=kept,
        nodes=ordered,
        depth=depth,
        resolutions=resolutions,
        skipped=skipped,
        category=category,
    )
