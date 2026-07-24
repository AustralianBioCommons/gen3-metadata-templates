"""Shared pytest fixtures.

The ``mini_schema.json`` bundle is a small, hand-written Gen3 schema built
specifically to exercise the tricky cases the tool must handle:

* ``sample`` is reachable by **two** paths (subject -> sample, and
  subject -> visit -> sample), so path-choosing logic can be tested.
* ``assay_file`` uses a **subgroup** link (the wrapped form that the old code
  crashed on), attaching to either ``sample`` or ``core_metadata_collection``.
* ``subject`` carries an **enum** (sex), an **integer** (age), a **pattern**
  (consent_code) and an **array** (aliases) property, covering the property
  shapes the writer and reader treat specially.

Resolving a schema is not free, so the bundle is resolved once per test session.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gen3_metadata_templates.schema import SchemaBundle

FIXTURE_DIR = Path(__file__).parent / "fixtures"
MINI_SCHEMA_PATH = FIXTURE_DIR / "mini_schema.json"
ACDC_SCHEMA_PATH = (
    Path(__file__).parent.parent / "examples" / "schema" / "json" / "acdc_schema.json"
)


@pytest.fixture(scope="session")
def mini_schema_path() -> str:
    """Filesystem path to the hand-built mini schema bundle."""
    return str(MINI_SCHEMA_PATH)


@pytest.fixture(scope="session")
def mini_bundle() -> SchemaBundle:
    """A resolved :class:`SchemaBundle` for the mini schema (session-scoped)."""
    return SchemaBundle(str(MINI_SCHEMA_PATH))


@pytest.fixture(scope="session")
def acdc_schema_path() -> str:
    """Filesystem path to the real 34-node ACDC schema (integration tests)."""
    return str(ACDC_SCHEMA_PATH)
