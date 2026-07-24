"""Enumerating and choosing node paths.

A Gen3 schema is a directed graph, so a target node can be reachable by more
than one chain of parents. The submitter must pick which chain their template
covers (it decides which sheets appear). This module enumerates the candidate
paths and resolves a chosen one, keeping the interactive prompt itself out of
the library via an injectable ``chooser`` callback.
"""

from __future__ import annotations

import contextlib
import io
from typing import Callable, List, Optional, Sequence

from gen3_validator.dict import group_paths_by_destination

from gen3_metadata_templates.errors import AmbiguousPathError, UnknownNodeError
from gen3_metadata_templates.schema import SchemaBundle

# A chooser is given the candidate paths and returns the index of the chosen one.
Chooser = Callable[[List[List[str]]], int]


def enumerate_paths(
    bundle: SchemaBundle,
    target_node: str,
    excluded_nodes: Sequence[str] = (),
) -> List[List[str]]:
    """Return every acyclic path from a root down to ``target_node``.

    Each path is a list of node names from the graph root to the target. Paths
    are sorted by (length, then node names) so the numbering a user sees is
    stable across runs.

    :raises UnknownNodeError: if the target node is not reachable / not present.
    """
    if not bundle.has_node(target_node):
        raise UnknownNodeError(f"Node '{target_node}' does not exist in the schema.")

    edges = bundle.edges(excluded_nodes)

    # group_paths_by_destination prints the root nodes to stdout as a side
    # effect; suppress that so library callers (and the CLI's own output) stay
    # clean. Edges are already excluded-node-filtered, so ignore_nodes=[].
    with contextlib.redirect_stdout(io.StringIO()):
        grouped = group_paths_by_destination(edges, ignore_nodes=[])

    path_infos = grouped.get(target_node, [])
    paths = [list(info.path) for info in path_infos]

    if not paths:
        # Reachable-as-a-node but no path means it's a root itself (no parents)
        # or every route was excluded. A single-node "path" is still valid.
        raise UnknownNodeError(
            f"No path leads to '{target_node}'. It may be a root node, or its "
            f"only parents were excluded."
        )

    paths.sort(key=lambda p: (len(p), p))
    return paths


def resolve_path(
    paths: List[List[str]],
    path_arg: Optional[str] = None,
    chooser: Optional[Chooser] = None,
) -> List[str]:
    """Pick one path from the candidates.

    Resolution order:

    1. If only one path exists, return it.
    2. If ``path_arg`` is given, interpret it as either a 1-based index
       (``"2"``) or a comma-separated node chain (``"program,project,subject"``)
       and match it against the candidates.
    3. Otherwise, if a ``chooser`` was supplied, ask it.
    4. Otherwise raise :class:`AmbiguousPathError`.

    :raises AmbiguousPathError: multiple paths and no way to choose.
    :raises ValueError: ``path_arg`` does not match any candidate.
    """
    if not paths:
        raise ValueError("No candidate paths to resolve.")
    if len(paths) == 1:
        return paths[0]

    if path_arg is not None:
        return _match_path_arg(paths, path_arg)

    if chooser is not None:
        index = chooser(paths)
        if not 0 <= index < len(paths):
            raise ValueError(f"Chooser returned out-of-range index {index}.")
        return paths[index]

    target = paths[0][-1]
    raise AmbiguousPathError(target, paths)


def _match_path_arg(paths: List[List[str]], path_arg: str) -> List[str]:
    arg = path_arg.strip()

    # Numeric: a 1-based index into the candidate list.
    if arg.isdigit():
        idx = int(arg) - 1
        if not 0 <= idx < len(paths):
            raise ValueError(f"--path {arg} is out of range (choose 1..{len(paths)}).")
        return paths[idx]

    # Otherwise treat as a comma-separated node chain and match exactly.
    wanted = [node.strip() for node in arg.split(",") if node.strip()]
    for path in paths:
        if path == wanted:
            return path
    raise ValueError(
        f"--path '{path_arg}' does not match any candidate path. "
        f"Use `g3mt paths` to see the options."
    )
