"""A thin wrapper around gen3_validator that isolates the rest of the package
from the schema engine's API.

Everything the tool needs from a Gen3 schema flows through :class:`SchemaBundle`:
resolved node schemas (for property types), the parent/child edge list (for
path ordering), and link descriptors enriched with multiplicity/required (for
building foreign-key columns and dropdowns). If gen3_validator's API shifts, this
module is the only place that has to change.
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from gen3_validator.bulk import extract_links
from gen3_validator.resolve_schema import ResolveSchema

from gen3_metadata_templates.errors import SchemaError, UnknownCategoryError

# How long to wait when downloading a schema from a URL, in seconds.
_URL_TIMEOUT = 30


def _is_url(schema_path: str) -> bool:
    """True if the schema location is an http(s) URL rather than a local path."""
    return schema_path.startswith(("http://", "https://"))


def _download_schema(url: str) -> bytes:
    """Fetch a schema bundle from an http(s) URL, validating that it's JSON.

    :raises SchemaError: on any network error, non-200 response, or if the
        downloaded content isn't valid JSON.
    """
    try:
        with urllib.request.urlopen(url, timeout=_URL_TIMEOUT) as response:  # noqa: S310 - scheme checked above
            data = response.read()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise SchemaError(f"Could not download schema from '{url}': {exc}") from exc

    try:
        json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SchemaError(
            f"The content at '{url}' is not valid JSON (is it the right link to a "
            f"Gen3 schema bundle?): {exc}"
        ) from exc
    return data


@dataclass(frozen=True)
class LinkInfo:
    """A parent relationship as seen from the child node.

    ``name`` is the property key that appears in the data (e.g. ``subjects``),
    ``target_type`` is the parent node id (e.g. ``subject``). ``multiplicity``
    (e.g. ``many_to_one``) tells us whether a child may reference many parents,
    which decides whether the foreign-key cell accepts a ``;``-separated list.
    ``required`` is whether the link must be present.
    """

    name: str
    target_type: str
    multiplicity: str
    required: bool

    @property
    def is_multi(self) -> bool:
        """True if a single record may reference more than one parent."""
        return self.multiplicity in ("many_to_many", "one_to_many")


def _iter_raw_link_members(raw_links: Sequence[dict]):
    """Yield each plain link dict, unwrapping any ``subgroup`` containers.

    Gen3 links are either a flat list of link dicts or wrapped in a
    ``{"subgroup": [...]}`` container (used when a node may attach to one of
    several parents). This flattens both forms identically to
    ``gen3_validator.bulk.extract_links``, but keeps every field so we can read
    ``multiplicity`` and ``required`` off each member.
    """
    for entry in raw_links or []:
        if not isinstance(entry, dict):
            continue
        members = entry["subgroup"] if "subgroup" in entry else [entry]
        for member in members:
            if isinstance(member, dict) and member.get("name") and member.get("target_type"):
                yield member


class SchemaBundle:
    """Loads and resolves a Gen3 schema bundle once, then answers questions about it.

    ``schema_path`` may be a local file path or an ``http(s)://`` URL pointing at
    a Gen3 schema bundle (e.g. a raw file on GitHub). URLs are downloaded to a
    temporary file, resolved, and cleaned up.
    """

    def __init__(self, schema_path: Union[str, Path]):
        self.schema_path = str(schema_path)
        self._category_map: Optional[Dict[str, List[str]]] = None
        local_path, is_temp = self._materialise(self.schema_path)
        try:
            self._resolver = ResolveSchema(local_path)
            self._resolver.resolve_schema()
        except SchemaError:
            raise
        except Exception as exc:  # noqa: BLE001 - re-raise as our typed error
            raise SchemaError(f"Could not resolve schema '{self.schema_path}': {exc}") from exc
        finally:
            if is_temp:
                try:
                    os.unlink(local_path)
                except OSError:
                    pass

    @staticmethod
    def _materialise(schema_path: str) -> Tuple[str, bool]:
        """Return a local file path for the schema, downloading it if it's a URL.

        :returns: ``(local_path, is_temp)`` where ``is_temp`` marks a temporary
            file the caller should delete once the schema has been read.
        """
        if _is_url(schema_path):
            data = _download_schema(schema_path)
            handle = tempfile.NamedTemporaryFile(
                prefix="g3mt_schema_", suffix=".json", delete=False
            )
            try:
                handle.write(data)
            finally:
                handle.close()
            return handle.name, True

        if not Path(schema_path).is_file():
            raise SchemaError(f"Schema file not found: {schema_path}")
        return schema_path, False

    @staticmethod
    def _strip_yaml(node: str) -> str:
        return node[:-5] if node.endswith(".yaml") else node

    @property
    def node_names(self) -> List[str]:
        """All submittable node ids (without the ``.yaml`` suffix), sorted.

        Excludes the internal ``_definitions``/``_terms``/``_settings`` helpers.
        """
        names = [
            self._strip_yaml(node.get("id", ""))
            for node in self._resolver.schema_list_resolved
            if node.get("id")
        ]
        return sorted(names)

    def has_node(self, node: str) -> bool:
        return self._strip_yaml(node) in set(self.node_names)

    @property
    def schema_version(self) -> Optional[str]:
        """The dictionary version declared in ``_settings.yaml`` (``_dict_version``).

        Returns ``None`` if the bundle doesn't declare one, so callers can treat
        "no version" as simply unknown rather than an error.
        """
        settings = self._resolver.schema.get("_settings.yaml") or {}
        version = settings.get("_dict_version")
        return str(version) if version else None

    # --- categories -------------------------------------------------------
    #
    # Gen3 nodes declare a ``category`` ("clinical", "data_file", ...). Grouping
    # by it is what lets someone ask for "every clinical sheet" without having
    # to know the individual node names.

    def category(self, node: str) -> Optional[str]:
        """The node's declared ``category``, or None if it doesn't declare one."""
        value = self.resolved(node).get("category")
        return str(value) if value else None

    def _categories(self) -> Dict[str, List[str]]:
        """Build (once) the category -> sorted node names map."""
        if self._category_map is None:
            grouped: Dict[str, List[str]] = {}
            for node in self.node_names:
                name = self.category(node)
                if name:
                    grouped.setdefault(name, []).append(node)
            self._category_map = {k: sorted(v) for k, v in grouped.items()}
        return self._category_map

    def categories(self) -> List[str]:
        """Every distinct category in the schema, sorted, in the schema's own spelling."""
        return sorted(self._categories())

    def nodes_by_category(self) -> Dict[str, List[str]]:
        """Map each category to its sorted node names.

        Nodes that declare no category are omitted; see :meth:`uncategorised_nodes`.
        """
        return {name: list(nodes) for name, nodes in sorted(self._categories().items())}

    def uncategorised_nodes(self) -> List[str]:
        """Sorted nodes that declare no category at all."""
        return sorted(n for n in self.node_names if not self.category(n))

    def nodes_in_category(self, category: str) -> List[str]:
        """Sorted node names in ``category``, matched case-insensitively.

        :raises UnknownCategoryError: if no node declares that category. The error
            lists what is available and suggests a close match for a typo.
        """
        wanted = category.strip().lower()
        grouped = self._categories()

        matches = [name for name in grouped if name.lower() == wanted]
        if len(matches) > 1:
            raise SchemaError(
                f"This schema declares more than one spelling of '{category}': "
                f"{', '.join(sorted(matches))}. Use the exact spelling you want."
            )
        if not matches:
            counts = {name: len(nodes) for name, nodes in grouped.items()}
            raise UnknownCategoryError(category, counts)
        return list(grouped[matches[0]])

    def resolved(self, node: str) -> dict:
        """Return the fully ref-resolved schema for one node.

        :raises SchemaError: if the node is not in the schema.
        """
        result = self._resolver.return_resolved_schema(node)
        if result is None:
            raise SchemaError(f"Node '{node}' not found in schema.")
        return result

    def _raw_node(self, node: str) -> dict:
        """The raw (unresolved) node schema, keyed by ``<id>.yaml``."""
        key = self._strip_yaml(node) + ".yaml"
        raw = self._resolver.schema.get(key)
        if raw is None:
            raise SchemaError(f"Node '{node}' not found in schema.")
        return raw

    def links(self, node: str) -> List[LinkInfo]:
        """Parent links for a node, flattened across subgroups.

        Uses ``gen3_validator.bulk.extract_links`` as the authoritative source of
        which ``(name, target_type)`` pairs exist (it is the only subgroup-safe
        flattener), then re-walks the raw links to attach ``multiplicity`` and
        ``required`` to each.
        """
        raw = self._raw_node(node)
        pairs = {(link["name"], link["target_type"]) for link in extract_links(raw)}
        infos = []
        for member in _iter_raw_link_members(raw.get("links", [])):
            key = (member["name"], member["target_type"])
            if key in pairs:
                infos.append(
                    LinkInfo(
                        name=member["name"],
                        target_type=member["target_type"],
                        multiplicity=member.get("multiplicity", "many_to_one"),
                        required=bool(member.get("required", False)),
                    )
                )
        return infos

    def required_props(self, node: str) -> List[str]:
        """The node's declared ``required`` property names."""
        return list(self.resolved(node).get("required", []))

    def edges(self, excluded_nodes: Sequence[str] = ()) -> List[Tuple[str, str]]:
        """All ``(parent, child)`` edges in the schema graph.

        Excluded nodes are dropped from the edge list entirely, which is what
        removes them (and unreachable branches through them) from path
        enumeration.
        """
        excluded = {self._strip_yaml(n) for n in excluded_nodes}
        result: List[Tuple[str, str]] = []
        for child in self.node_names:
            if child in excluded:
                continue
            for link in self.links(child):
                parent = link.target_type
                if parent in excluded:
                    continue
                result.append((parent, child))
        return result
