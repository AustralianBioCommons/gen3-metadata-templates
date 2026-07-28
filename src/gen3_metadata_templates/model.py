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
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from gen3_metadata_templates.constants import (
    DEFAULT_EXCLUDED_COLUMNS,
    DEFAULT_EXCLUDED_NODES,
    PRIMARY_KEY,
)
from gen3_metadata_templates.schema import LinkInfo, SchemaBundle
from gen3_metadata_templates.selection import NodeSelection
from gen3_metadata_templates.workbook.naming import fk_header, sheet_names


class ColumnKind(str, Enum):
    """What role a column plays, which decides how it is written and read."""

    PK = "pk"  # this node's own submitter_id
    LINK = "link"  # a foreign key to a parent node's submitter_id
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

    schema_path: str  # the full source the schema was loaded from (local path or URL)
    target_node: str  # primary target (target_nodes[0]); kept for the workbook metadata
    path: List[str]  # the primary target's path; kept for the workbook metadata
    nodes: List[NodeTemplate]  # parents-first; the authoritative sheet order
    schema_version: Optional[str] = None  # _dict_version from the schema, if declared

    # A template may cover several targets at once (e.g. a whole category).
    target_nodes: List[str] = field(default_factory=list)
    paths: Dict[str, List[str]] = field(default_factory=dict)  # target -> path used
    depth: Dict[str, int] = field(default_factory=dict)  # node -> level, for the fill tree
    category: Optional[str] = None  # set when a category drove the selection

    def __post_init__(self) -> None:
        # Allow a single-target construction (the 2.2.0 shape) to produce a
        # coherent spec without the caller having to fill in the newer fields.
        if not self.target_nodes:
            self.target_nodes = [self.target_node]
        if not self.paths:
            self.paths = {self.target_node: list(self.path)}
        if not self.depth:
            # A single-target spec's nodes form a chain, so position == level.
            self.depth = {nt.node: i for i, nt in enumerate(self.nodes)}

    @property
    def node_order(self) -> List[str]:
        """The sheet order, as node names. Derived from ``nodes`` so it can't drift."""
        return [nt.node for nt in self.nodes]

    @property
    def is_multi_target(self) -> bool:
        return len(self.target_nodes) > 1

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
    node_index: Dict[str, int],
    required_props: set,
) -> List[ColumnSpec]:
    """Build ordered ColumnSpecs for a node's links that stay within the template.

    Only links whose target is one of the template's own nodes become columns (a
    link to a parent that isn't in the workbook is dropped — there would be no
    sheet to point at). Columns are ordered by the parent's position in the
    sheet order, so parents that come first appear first.
    """
    included = [link for link in links if link.target_type in node_index]

    # Detect target-type collisions so headers can be disambiguated.
    target_counts: Dict[str, int] = {}
    for link in included:
        target_counts[link.target_type] = target_counts.get(link.target_type, 0) + 1

    included.sort(key=lambda link: node_index[link.target_type])

    columns: List[ColumnSpec] = []
    for link in included:
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


def build_spec_for_nodes(
    bundle: SchemaBundle,
    ordered_nodes: Sequence[str],
    *,
    target_nodes: Sequence[str] = (),
    paths: Optional[Mapping[str, Sequence[str]]] = None,
    depth: Optional[Mapping[str, int]] = None,
    category: Optional[str] = None,
    excluded_columns: Sequence[str] = DEFAULT_EXCLUDED_COLUMNS,
) -> TemplateSpec:
    """Build a spec from an explicit, already-ordered node list.

    ``ordered_nodes`` is taken **verbatim**: no exclusion filtering and no
    re-ordering. This is the single place columns are derived, which is what
    lets validation rebuild the exact spec a workbook was written from.

    :param target_nodes: the nodes the user actually asked for (the rest are
        ancestors that came along). Defaults to the last node, matching the
        single-target case.
    :param excluded_columns: property names stripped from every sheet.
    """
    excluded_col_set = set(excluded_columns)
    included_nodes = list(ordered_nodes)
    node_index = {node: i for i, node in enumerate(included_nodes)}
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

        # 2. Link (foreign-key) columns, ordered by parent position in the sheets.
        columns.extend(_link_columns(links, node_index, required))

        # 3. Remaining properties: required first (alphabetical), then optional.
        plain_props = [
            name
            for name in properties
            if name != PRIMARY_KEY and name not in link_names and name not in excluded_col_set
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

    targets = [t for t in target_nodes] or ([included_nodes[-1]] if included_nodes else [])
    path_map = {t: list(p) for t, p in (paths or {}).items()}
    primary = targets[0] if targets else ""

    return TemplateSpec(
        schema_path=bundle.schema_path,
        target_node=primary,
        path=path_map.get(primary, list(included_nodes)),
        nodes=node_templates,
        schema_version=bundle.schema_version,
        target_nodes=targets,
        paths=path_map or {primary: list(included_nodes)},
        depth=dict(depth) if depth else {},
        category=category,
    )


def build_template_spec(
    bundle: SchemaBundle,
    target_node: str,
    path: Sequence[str],
    *,
    excluded_nodes: Sequence[str] = DEFAULT_EXCLUDED_NODES,
    excluded_columns: Sequence[str] = DEFAULT_EXCLUDED_COLUMNS,
) -> TemplateSpec:
    """Assemble the template plan for one target reached along one path.

    This is the single-path entry point and its behaviour is unchanged: the path
    is filtered by ``excluded_nodes`` and used as the sheet order.

    :param path: the chosen node path (root -> target), possibly including
        excluded nodes for display.
    :param excluded_nodes: nodes that get no sheet.
    :param excluded_columns: property names stripped from every sheet.
    """
    excluded_node_set = {n for n in excluded_nodes}
    included = [n for n in path if n not in excluded_node_set]

    spec = build_spec_for_nodes(
        bundle,
        included,
        target_nodes=[target_node],
        paths={target_node: list(path)},
        excluded_columns=excluded_columns,
    )
    # Preserve the caller's target/path verbatim, including any excluded nodes
    # the path ran through — the workbook metadata records them for display.
    spec.target_node = target_node
    spec.path = list(path)
    return spec


def build_multi_template_spec(
    bundle: SchemaBundle,
    selection: NodeSelection,
    *,
    excluded_columns: Sequence[str] = DEFAULT_EXCLUDED_COLUMNS,
) -> TemplateSpec:
    """Assemble the template plan for a resolved multi-node selection.

    The selection has already unioned the targets' ancestor paths, dropped
    excluded nodes, and ordered the result parents-first, so it is used as-is.
    """
    return build_spec_for_nodes(
        bundle,
        selection.nodes,
        target_nodes=selection.targets,
        paths={r.target: r.path for r in selection.resolutions},
        depth=selection.depth,
        category=selection.category,
        excluded_columns=excluded_columns,
    )
