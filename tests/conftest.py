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

This module also forces plain, uncoloured console output for the whole test
session — see the note by the environment setup below.
"""

from __future__ import annotations

import os

# Force rich to render without ANSI colour codes BEFORE anything imports the CLI
# (which builds its Console objects at import time). Developers commonly have
# FORCE_COLOR set in their shell, which would otherwise make rich emit escape
# sequences even under Typer's CliRunner — breaking any test that matches on
# output text or parses --json. CI happens not to set it, so this would fail
# only on some machines, which is the worst kind of flake.
os.environ.pop("FORCE_COLOR", None)
os.environ.pop("CLICOLOR_FORCE", None)
os.environ["NO_COLOR"] = "1"
os.environ["TERM"] = "dumb"

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from gen3_metadata_templates.schema import SchemaBundle  # noqa: E402

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
