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


@pytest.fixture(scope="session")
def acdc_bundle() -> SchemaBundle:
    """A resolved bundle for the real ACDC schema (resolving it isn't free)."""
    return SchemaBundle(str(ACDC_SCHEMA_PATH))


# --- graph-shape fixtures -------------------------------------------------
#
# Real dictionaries are not all shaped alike, and some are malformed. Each of
# these small bundles exists to prove the node-selection logic copes with one
# specific shape that the tidy mini schema doesn't cover.


@pytest.fixture(scope="session")
def clinical_hub_bundle() -> SchemaBundle:
    """The common clinical shape: measurements hang off a hub, hub hangs off subject.

    Mirrors a real Gen3 dictionary — ``subject -> clinical_descriptor ->
    {blood_pressure_test, demographic, medical_history}``, with every one of
    those in the ``clinical`` category, plus a ``sample`` node that also hangs
    off the hub but is ``biospecimen`` (so it must be left out of a clinical
    selection).
    """
    return SchemaBundle(str(FIXTURE_DIR / "clinical_hub_schema.json"))


@pytest.fixture(scope="session")
def clinical_flat_bundle() -> SchemaBundle:
    """Clinical nodes at *mixed* depths, including a root and a disconnected one.

    Not every dictionary funnels clinical data through one hub. Here one
    measurement hangs off ``subject`` directly, another sits below a hub, and a
    third links to nothing at all — so ordering can't assume a uniform shape.
    """
    return SchemaBundle(str(FIXTURE_DIR / "clinical_flat_schema.json"))


@pytest.fixture(scope="session")
def ambiguous_bundle() -> SchemaBundle:
    """Awkward but legal link shapes that make path choice non-obvious.

    Contains a diamond (two routes to ``d`` of *equal* length, forcing a
    tie-break), a node with two links to the same target type, and an exclusive
    subgroup whose members can both end up in one template.
    """
    return SchemaBundle(str(FIXTURE_DIR / "ambiguous_schema.json"))


@pytest.fixture(scope="session")
def cyclic_bundle() -> SchemaBundle:
    """A malformed dictionary: a real loop, a self-link, and a healthy branch.

    ``x`` and ``y`` link to each other, ``z`` links to itself, and
    ``clean_root -> clean_child`` is untouched by either. Proves a broken corner
    of a schema is reported clearly without breaking the healthy parts.
    """
    return SchemaBundle(str(FIXTURE_DIR / "cyclic_schema.json"))
