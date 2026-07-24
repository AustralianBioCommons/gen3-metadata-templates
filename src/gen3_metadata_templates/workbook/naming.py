"""Naming rules shared by the writer and reader.

Column headers, sheet names, and defined-range names are all derived
deterministically from the schema so that the reader can reconstruct exactly
what the writer produced without relying on stored metadata.
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence

from gen3_metadata_templates.constants import MAX_SHEET_NAME_LEN, PRIMARY_KEY
from gen3_metadata_templates.schema import LinkInfo


def fk_header(link: LinkInfo, collision: bool = False) -> str:
    """Build the header for a foreign-key (parent link) column.

    The header is ``<target_type>.submitter_id`` — e.g. ``subject.submitter_id``.
    Naming from the *target type* (not the link name) means the header always
    names the sheet the submitter copies IDs from, and is singular by
    construction, avoiding the old strip-trailing-"s" bug.

    When two links from the same node point at the same target type (rare but
    legal), ``collision`` disambiguates by appending the link name.
    """
    base = f"{link.target_type}.{PRIMARY_KEY}"
    if collision:
        return f"{base}#{link.name}"
    return base


def named_range(node: str) -> str:
    """Workbook-scoped defined-name holding a node's submitter_id column.

    Excel names must start with a letter/underscore and contain no spaces or
    punctuation, so the node name is sanitised and prefixed.
    """
    safe = re.sub(r"\W", "_", node)
    return f"ids_{safe}"


def enum_range(node: str, prop: str) -> str:
    """Defined-name for a long enum's backing list on the hidden lists sheet."""
    safe = re.sub(r"\W", "_", f"{node}_{prop}")
    return f"enum_{safe}"


def sheet_names(nodes: Sequence[str]) -> Dict[str, str]:
    """Map each node to a unique, Excel-legal (<=31 char) sheet name.

    Most node names fit as-is. Longer names are truncated and given a numeric
    suffix; collisions (from truncation or otherwise) are broken with an
    incrementing counter so every sheet name stays unique.
    """
    used: set = set()
    mapping: Dict[str, str] = {}
    for node in nodes:
        name = node if len(node) <= MAX_SHEET_NAME_LEN else node[: MAX_SHEET_NAME_LEN - 3] + "~01"
        if name in used:
            name = _dedupe(node, used)
        used.add(name)
        mapping[node] = name
    return mapping


def _dedupe(node: str, used: set) -> str:
    """Return a <=31-char variant of ``node`` not already in ``used``."""
    counter = 1
    while True:
        suffix = f"~{counter:02d}"
        stem = node[: MAX_SHEET_NAME_LEN - len(suffix)]
        candidate = f"{stem}{suffix}"
        if candidate not in used:
            return candidate
        counter += 1
