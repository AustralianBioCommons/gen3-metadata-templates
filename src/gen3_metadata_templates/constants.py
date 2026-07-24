"""Shared constants for gen3_metadata_templates.

These values define the default behaviour of template generation and validation:
which nodes/columns are dropped by default, where the header/hint/data rows sit
inside each Excel sheet, and the special sheet names the tool reserves.
"""

from __future__ import annotations

# Nodes that submitters almost never fill in themselves. `program` and `project`
# are created by data administrators; `core_metadata_collection` and
# `acknowledgement` are optional Gen3 housekeeping nodes. Users can re-include any
# of these with `--include-node`.
DEFAULT_EXCLUDED_NODES = (
    "program",
    "project",
    "core_metadata_collection",
    "acknowledgement",
)

# Gen3 system/injected properties that a submitter should never populate by hand.
# These are stripped from every generated sheet unless `--no-default-excludes`.
DEFAULT_EXCLUDED_COLUMNS = (
    "type",
    "id",
    "state",
    "object_id",
    "file_state",
    "error_type",
    "ga4gh_drs_uri",
    "created_datetime",
    "updated_datetime",
)

# Number of blank data rows pre-provisioned (and unlocked) on each node sheet.
DEFAULT_DATA_ROWS = 5000

# Row layout inside every node sheet (1-indexed, matching Excel/openpyxl).
HEADER_ROW = 1  # column headers
HINT_ROW = 2  # type + required/optional hint, locked
FIRST_DATA_ROW = 3  # first row a submitter types into

# Reserved sheet names.
INSTRUCTIONS_SHEET = "Instructions"
DICTIONARY_SHEET = "Dictionary"
META_SHEET = "_g3mt"  # hidden machine-readable metadata
LISTS_SHEET = "_lists"  # hidden backing store for long enum dropdowns

# Excel caps a worksheet name at 31 characters.
MAX_SHEET_NAME_LEN = 31

# Excel rejects an inline data-validation list whose joined text exceeds 255
# characters; longer enums are written to LISTS_SHEET and referenced by name.
MAX_INLINE_LIST_LEN = 255

# Separator used inside a single cell for to-many links and array-valued
# properties (e.g. "id_a; id_b; id_c").
LIST_SPLIT_CHAR = ";"

# The primary-key property every submittable Gen3 node carries.
PRIMARY_KEY = "submitter_id"
