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
from typing import List, Sequence, Tuple, Union

from gen3_validator.bulk import extract_links
from gen3_validator.resolve_schema import ResolveSchema

from gen3_metadata_templates.errors import SchemaError

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
