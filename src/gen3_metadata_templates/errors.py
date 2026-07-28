"""Exception types for gen3_metadata_templates.

Every error the tool raises deliberately derives from :class:`G3mtError` so the
CLI can catch that single base and exit with code ``2`` (usage/input error),
keeping validation-failure exits (code ``1``) distinct from "you gave me
something I can't work with".
"""

from __future__ import annotations

import difflib
from typing import Dict, List


class G3mtError(Exception):
    """Base class for all expected, user-facing errors.

    The CLI maps any subclass to exit code 2. Unexpected exceptions are allowed
    to propagate so they surface as real tracebacks/bug reports.
    """


class SchemaError(G3mtError):
    """The Gen3 schema could not be read or resolved."""


class UnknownNodeError(G3mtError):
    """The requested target node does not exist in the schema."""


class UnknownCategoryError(G3mtError):
    """No node in the schema declares the requested category.

    Carries what *is* available so the message can list the real categories and
    suggest a close match for a typo.
    """

    def __init__(self, category: str, available: Dict[str, int]):
        self.category = category
        self.available = available
        lines = [f"No nodes have category '{category}'."]

        close = difflib.get_close_matches(category.lower(), list(available), n=1, cutoff=0.6)
        if close:
            lines[0] += f" Did you mean '{close[0]}'?"

        if available:
            listed = ", ".join(f"{name} ({count})" for name, count in sorted(available.items()))
            lines.append(f"Available categories: {listed}.")
        else:
            lines.append("This schema declares no categories at all.")
        lines.append("Run `g3mt categories <schema>` to see the nodes in each.")
        super().__init__("\n".join(lines))


class AmbiguousPathError(G3mtError):
    """A target node is reachable by more than one path and none was chosen.

    Carries the candidate paths so the caller (CLI) can print a numbered list
    telling the user how to disambiguate with ``--path``.
    """

    def __init__(self, target_node: str, paths: List[List[str]]):
        self.target_node = target_node
        self.paths = paths
        joined = "\n".join(f"  {i}. {' -> '.join(p)}" for i, p in enumerate(paths, start=1))
        super().__init__(
            f"Node '{target_node}' is reachable by {len(paths)} paths:\n{joined}\n"
            f"Re-run with --path N (or a comma-separated node list) to choose one."
        )


class WorkbookFormatError(G3mtError):
    """The uploaded workbook is not a recognisable g3mt template."""
