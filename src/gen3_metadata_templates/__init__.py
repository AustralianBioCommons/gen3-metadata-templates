"""gen3_metadata_templates: generate and validate Gen3 metadata submission templates."""

from __future__ import annotations

__version__ = "2.0.0"

from gen3_metadata_templates.errors import (
    AmbiguousPathError,
    G3mtError,
    SchemaError,
    UnknownNodeError,
    WorkbookFormatError,
)
from gen3_metadata_templates.model import (
    ColumnKind,
    ColumnSpec,
    NodeTemplate,
    TemplateSpec,
    build_template_spec,
)
from gen3_metadata_templates.paths import enumerate_paths, resolve_path
from gen3_metadata_templates.schema import LinkInfo, SchemaBundle
from gen3_metadata_templates.workbook.writer import write_template

__all__ = [
    "__version__",
    "G3mtError",
    "SchemaError",
    "UnknownNodeError",
    "AmbiguousPathError",
    "WorkbookFormatError",
    "SchemaBundle",
    "LinkInfo",
    "build_template_spec",
    "TemplateSpec",
    "NodeTemplate",
    "ColumnSpec",
    "ColumnKind",
    "enumerate_paths",
    "resolve_path",
    "write_template",
]
