"""Turn a raw validation error into a message a non-developer can act on.

gen3_validator's messages are precise but written for engineers
("'10' is not of type 'integer'"). This module rewrites them per validation
keyword into plain guidance that names the value, the expectation, and often an
example, using the column's schema info for context.
"""

from __future__ import annotations

import re
from typing import Optional

from gen3_metadata_templates.model import ColumnSpec

# Human wording + a concrete example for each JSON-schema type.
_TYPE_WORDS = {
    "integer": ("a whole number", "e.g. 42"),
    "number": ("a number", "e.g. 3.14"),
    "boolean": ("TRUE or FALSE", ""),
    "string": ("text", ""),
    "array": ("a list", 'separate values with ";"'),
}


def _extract_value(error: dict) -> str:
    """Best-effort recovery of the offending value from the raw message."""
    match = re.search(r"^'?(.*?)'? is not", error.get("validation_error", ""))
    if match and match.group(1):
        return match.group(1)
    return ""


def friendly_message(error: dict, column: Optional[ColumnSpec]) -> str:
    """Return a plain-English explanation for one validation error."""
    validator = error.get("validator")
    raw = error.get("validation_error", "")

    if validator == "type":
        wanted = error.get("validator_value", "")
        word, example = _TYPE_WORDS.get(wanted, (wanted or "a different type", ""))
        value = _extract_value(error)
        prefix = f"'{value}' is not " if value else "This value is not "
        msg = f"{prefix}{word}."
        if example:
            msg += f" This column needs {word} ({example})."
        return msg

    if validator == "enum":
        allowed = list(column.enum) if column and column.enum else error.get("validator_value", [])
        shown = ", ".join(map(str, allowed[:6]))
        more = "" if len(allowed) <= 6 else f", ... ({len(allowed) - 6} more — see the Dictionary sheet)"
        return f"This value isn't one of the allowed values. Pick one of: {shown}{more}."

    if validator == "required":
        prop = _required_prop(raw)
        header = column.header if column else prop
        return f"This cell can't be empty — '{header or prop}' is required for every row."

    if validator == "pattern":
        pattern = column.pattern if column and column.pattern else error.get("validator_value", "")
        value = _extract_value(error)
        prefix = f"'{value}' " if value else "This value "
        return f"{prefix}doesn't match the required format ({pattern})."

    if validator in ("minimum", "exclusiveMinimum"):
        return f"This number is too small — it must be at least {error.get('validator_value')}."
    if validator in ("maximum", "exclusiveMaximum"):
        return f"This number is too large — it must be at most {error.get('validator_value')}."

    if validator == "format":
        fmt = error.get("validator_value", "")
        value = _extract_value(error)
        prefix = f"'{value}' " if value else "This value "
        example = " (example: 2024-01-31)" if "date" in str(fmt) else ""
        return f"{prefix}isn't a valid {fmt}{example}."

    if validator == "link":
        target = error.get("validator_value", "the parent")
        value = _extract_link_value(raw)
        vtext = f"'{value}' " if value else "This value "
        return (
            f"{vtext}doesn't match any submitter_id on the '{target}' sheet. "
            f"Check for typos, or add that row first."
        )

    if validator == "duplicate":
        return raw  # already phrased in plain language by the runner

    # Fallback: hand back the raw message, lightly cleaned.
    return raw or "This value is invalid."


def _required_prop(raw: str) -> str:
    match = re.match(r"'([^']+)' is a required property", raw)
    return match.group(1) if match else ""


def _extract_link_value(raw: str) -> str:
    match = re.search(r"references \w+ '([^']+)'", raw)
    return match.group(1) if match else ""
