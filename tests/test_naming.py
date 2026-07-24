"""Tests for :mod:`gen3_metadata_templates.workbook.naming`.

Headers, sheet names, and range names are derived deterministically from the
schema so the reader can rebuild them without stored state. These tests pin the
FK header convention and the 31-character sheet-name rules Excel enforces.
"""

from __future__ import annotations

from gen3_metadata_templates.schema import LinkInfo
from gen3_metadata_templates.workbook.naming import (
    enum_range,
    fk_header,
    named_range,
    sheet_names,
)


def test_fk_header_uses_target_type_not_link_name():
    """A foreign-key header names the parent *sheet*, singular.

    The link property is plural (``subjects``); the header must be
    ``subject.submitter_id`` so it points a submitter at the ``subject`` sheet.
    Deriving from ``target_type`` also sidesteps the old bug of guessing the
    singular by chopping a trailing "s".
    """
    link = LinkInfo("subjects", "subject", "many_to_one", True)
    assert fk_header(link) == "subject.submitter_id"


def test_fk_header_disambiguates_on_collision():
    """Two links to the same parent type get distinct headers.

    If a node links to the same target type twice, plain headers would collide;
    appending the link name keeps them unique and mappable back on read.
    """
    link = LinkInfo("primary_subjects", "subject", "many_to_one", True)
    assert fk_header(link, collision=True) == "subject.submitter_id#primary_subjects"


def test_named_range_is_excel_safe():
    """Range names must be free of characters Excel forbids in names."""
    assert named_range("core_metadata_collection") == "ids_core_metadata_collection"
    assert " " not in named_range("some node")


def test_enum_range_is_excel_safe():
    """Enum backing-range names combine node and property, sanitised."""
    assert enum_range("sample", "sample_type") == "enum_sample_sample_type"


def test_sheet_names_pass_through_when_short():
    """Node names within Excel's 31-char limit are used verbatim."""
    mapping = sheet_names(["subject", "sample", "visit"])
    assert mapping == {"subject": "subject", "sample": "sample", "visit": "visit"}


def test_sheet_names_truncate_long_names():
    """Names longer than 31 chars are shortened but kept unique.

    Excel refuses sheet names over 31 characters, so the tool must truncate.
    Two names that share a long prefix must still map to different sheets, or
    data would be written to the wrong tab.
    """
    long_a = "extremely_long_node_name_number_one"
    long_b = "extremely_long_node_name_number_two"
    mapping = sheet_names([long_a, long_b])
    assert all(len(name) <= 31 for name in mapping.values())
    assert mapping[long_a] != mapping[long_b]
