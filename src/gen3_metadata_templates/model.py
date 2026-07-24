"""The internal template data model.

``build_template_spec`` turns a resolved schema plus a chosen node path into a
:class:`TemplateSpec`: an ordered list of :class:`NodeTemplate`, each an ordered
list of :class:`ColumnSpec`. This single structure is consumed by the writer
(to lay out sheets), the Dictionary sheet (one row per column), and the reader
(to map headers back to properties) — so all three are guaranteed to agree on
what the columns are.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from gen3_metadata_templates.constants import (
    DEFAULT_EXCLUDED_COLUMNS,
    DEFAULT_EXCLUDED_NODES,
    PRIMARY_KEY,
)
from gen3_metadata_templates.schema import LinkInfo, SchemaBundle
from gen3_metadata_templates.workbook.naming import fk_header, sheet_names


class ColumnKind(str, Enum):
    """What role a column plays, which decides how it is written and read."""

    PK = "pk"          # this node's own submitter_id
    LINK = "link"      # a foreign key to a parent node's submitter_id
    PROPERTY = "property"


@dataclass(frozen=True)
class ColumnSpec:
    """A single column in a node sheet.

    ``prop_name`` is the schema property key (for a link, the link name such as
    ``subjects``). ``data_type`` is normalised for display/coercion:
    string/integer/number/boolean/array/enum. ``enum`` holds the real allowed
    values (never the literal string "enum"). ``is_multi`` marks columns whose
    cell may carry a ``;``-separated list (array properties and to-many links).
    """

    header: str
    prop_name: str
    kind: ColumnKind
    data_type: str
    required: bool
    description: str = ""
    enum: Optional[Tuple[str, ...]] = None
    pattern: Optional[str] = None
    link_target: Optional[str] = None
    link_multiplicity: Optional[str] = None
    is_multi: bool = False


@dataclass
class NodeTemplate:
    """One node's worth of columns, plus its sheet name."""

    node: str
    sheet_name: str
    description: str
    columns: List[ColumnSpec] = field(default_factory=list)

    def column_by_header(self, header: str) -> Optional[ColumnSpec]:
        return next((c for c in self.columns if c.header == header), None)

    def column_by_prop(self, prop: str) -> Optional[ColumnSpec]:
        return next((c for c in self.columns if c.prop_name == prop), None)


@dataclass
class TemplateSpec:
    """The full plan for a template: which nodes, in what order, with what columns."""

    schema_path: str
    target_node: str
    path: List[str]              # chosen path (may include excluded nodes, for display)
    nodes: List[NodeTemplate]    # in path order, excluded nodes removed

    def node_template(self, node: str) -> Optional[NodeTemplate]:
        return next((n for n in self.nodes if n.node == node), None)


def _collect_enum(prop: dict) -> Optional[Tuple[str, ...]]:
    """Pull allowed values out of a resolved property.

    Handles a top-level ``enum``, an array's ``items.enum``, and enums nested
    inside ``oneOf``/``anyOf`` branches (some Gen3 definitions express controlled
    values that way).
    """
    if isinstance(prop.get("enum"), list):
        return tuple(str(v) for v in prop["enum"])

    items = prop.get("items")
    if isinstance(items, dict) and isinstance(items.get("enum"), list):
        return tuple(str(v) for v in items["enum"])

    values: List[str] = []
    for branch in (prop.get("oneOf") or []) + (prop.get("anyOf") or []):
        if isinstance(branch, dict) and isinstance(branch.get("enum"), list):
            values.extend(str(v) for v in branch["enum"])
    return tuple(values) if values else None


def _normalise_type(type_value) -> str:
    """Collapse a JSON-schema ``type`` value to a single word.

    ``["string", "null"]`` becomes ``string``; a plain string passes through.
    """
    if isinstance(type_value, list):
        non_null = [t for t in type_value if t != "null"]
        return non_null[0] if non_null else "string"
    return str(type_value)


def _derive_property_column(prop_name: str, prop: dict, required: bool) -> ColumnSpec:
    """Build a ColumnSpec for a non-link, non-PK property."""
    enum = _collect_enum(prop)
    raw_type = prop.get("type")
    is_multi = False

    if raw_type is not None:
        data_type = _normalise_type(raw_type)
        if data_type == "array":
            is_multi = True
    elif enum is not None:
        data_type = "enum"
    else:
        data_type = "string"

    description = prop.get("description", "")
    if not description and isinstance(prop.get("term"), dict):
        description = prop["term"].get("description", "")

    return ColumnSpec(
        header=prop_name,
        prop_name=prop_name,
        kind=ColumnKind.PROPERTY,
        data_type=data_type,
        required=required,
        description=description or "",
        enum=enum,
        pattern=prop.get("pattern"),
        is_multi=is_multi,
    )


def _link_columns(
    links: Sequence[LinkInfo],
    path_index: Dict[str, int],
    required_props: set,
) -> List[ColumnSpec]:
    """Build ordered ColumnSpecs for a node's links that stay within the path.

    Only links whose target appears in the chosen path become columns (a link to
    an off-path or excluded parent is dropped). Columns are ordered by the
    parent's position in the path so parents that come first appear first.
    """
    on_path = [link for link in links if link.target_type in path_index]

    # Detect target-type collisions so headers can be disambiguated.
    target_counts: Dict[str, int] = {}
    for link in on_path:
        target_counts[link.target_type] = target_counts.get(link.target_type, 0) + 1

    on_path.sort(key=lambda link: path_index[link.target_type])

    columns: List[ColumnSpec] = []
    for link in on_path:
        collision = target_counts[link.target_type] > 1
        columns.append(
            ColumnSpec(
                header=fk_header(link, collision=collision),
                prop_name=link.name,
                kind=ColumnKind.LINK,
                data_type="string",
                required=link.required or link.name in required_props,
                description=(
                    f"Link to a {link.target_type}. Enter a submitter_id from the "
                    f"'{link.target_type}' sheet."
                ),
                link_target=link.target_type,
                link_multiplicity=link.multiplicity,
                is_multi=link.is_multi,
            )
        )
    return columns


def build_template_spec(
    bundle: SchemaBundle,
    target_node: str,
    path: Sequence[str],
    *,
    excluded_nodes: Sequence[str] = DEFAULT_EXCLUDED_NODES,
    excluded_columns: Sequence[str] = DEFAULT_EXCLUDED_COLUMNS,
) -> TemplateSpec:
    """Assemble the full template plan for a chosen path.

    :param path: the chosen node path (root -> target), possibly including
        excluded nodes for display.
    :param excluded_nodes: nodes that get no sheet.
    :param excluded_columns: property names stripped from every sheet.
    """
    excluded_node_set = {n for n in excluded_nodes}
    excluded_col_set = set(excluded_columns)

    included_nodes = [n for n in path if n not in excluded_node_set]
    path_index = {node: i for i, node in enumerate(included_nodes)}
    sheet_map = sheet_names(included_nodes)

    node_templates: List[NodeTemplate] = []
    for node in included_nodes:
        resolved = bundle.resolved(node)
        properties: dict = resolved.get("properties", {})
        required = set(resolved.get("required", []))
        links = bundle.links(node)
        link_names = {link.name for link in links}

        columns: List[ColumnSpec] = []

        # 1. Primary key.
        if PRIMARY_KEY in properties:
            columns.append(
                ColumnSpec(
                    header=PRIMARY_KEY,
                    prop_name=PRIMARY_KEY,
                    kind=ColumnKind.PK,
                    data_type="string",
                    required=True,
                    description=(
                        "Your own unique identifier for this row. Reuse the same "
                        "value on child sheets to link records together."
                    ),
                )
            )

        # 2. Link (foreign-key) columns, ordered by parent position in the path.
        columns.extend(_link_columns(links, path_index, required))

        # 3. Remaining properties: required first (alphabetical), then optional.
        plain_props = [
            name
            for name in properties
            if name != PRIMARY_KEY
            and name not in link_names
            and name not in excluded_col_set
        ]
        required_plain = sorted(p for p in plain_props if p in required)
        optional_plain = sorted(p for p in plain_props if p not in required)
        for name in required_plain + optional_plain:
            columns.append(
                _derive_property_column(name, properties[name], required=name in required)
            )

        node_templates.append(
            NodeTemplate(
                node=node,
                sheet_name=sheet_map[node],
                description=resolved.get("description", ""),
                columns=columns,
            )
        )

    return TemplateSpec(
        schema_path=bundle.schema_path,
        target_node=target_node,
        path=list(path),
        nodes=node_templates,
    )
