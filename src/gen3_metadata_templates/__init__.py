"""gen3_metadata_templates: generate and validate Gen3 metadata submission templates."""

from __future__ import annotations

__version__ = "2.3.0"

from gen3_metadata_templates.errors import (
    AmbiguousPathError,
    CyclicGraphError,
    G3mtError,
    SchemaError,
    SelectionError,
    UnknownCategoryError,
    UnknownNodeError,
    WorkbookFormatError,
)
from gen3_metadata_templates.model import (
    ColumnKind,
    ColumnSpec,
    NodeTemplate,
    TemplateSpec,
    build_multi_template_spec,
    build_spec_for_nodes,
    build_template_spec,
)
from gen3_metadata_templates.paths import enumerate_paths, resolve_path
from gen3_metadata_templates.schema import LinkInfo, SchemaBundle
from gen3_metadata_templates.selection import (
    NodeSelection,
    TargetResolution,
    layered_topological_order,
    resolve_selection,
)
from gen3_metadata_templates.validation.report import Finding, ValidationReport
from gen3_metadata_templates.validation.runner import validate_workbook
from gen3_metadata_templates.workbook.writer import write_template

__all__ = [
    "__version__",
    "G3mtError",
    "SchemaError",
    "UnknownNodeError",
    "UnknownCategoryError",
    "AmbiguousPathError",
    "WorkbookFormatError",
    "SelectionError",
    "CyclicGraphError",
    "SchemaBundle",
    "LinkInfo",
    "build_template_spec",
    "build_multi_template_spec",
    "build_spec_for_nodes",
    "TemplateSpec",
    "NodeTemplate",
    "ColumnSpec",
    "ColumnKind",
    "enumerate_paths",
    "resolve_path",
    "resolve_selection",
    "NodeSelection",
    "TargetResolution",
    "layered_topological_order",
    "write_template",
    "validate_workbook",
    "ValidationReport",
    "Finding",
]
