"""Tests for :mod:`gen3_metadata_templates.validation.messages`.

Plain-language error messages are the whole point of the validate command for a
non-developer, so each validator keyword's rewrite is checked against a
representative raw error. The assertions look for the meaningful content (the
value, the expectation) rather than exact wording, so phrasing can be improved
without breaking the tests.
"""

from __future__ import annotations

from gen3_metadata_templates.model import ColumnKind, ColumnSpec
from gen3_metadata_templates.validation.messages import friendly_message


def _col(**kwargs):
    base = dict(
        header="age", prop_name="age", kind=ColumnKind.PROPERTY,
        data_type="integer", required=False,
    )
    base.update(kwargs)
    return ColumnSpec(**base)


def test_type_error_names_value_and_expectation():
    """A type error should name the bad value and what was expected in plain words."""
    error = {
        "validator": "type",
        "validator_value": "integer",
        "validation_error": "'ten' is not of type 'integer'",
    }
    msg = friendly_message(error, _col())
    assert "ten" in msg
    assert "whole number" in msg


def test_enum_error_lists_allowed_values():
    """An enum error should tell the user which values are actually allowed."""
    error = {
        "validator": "enum",
        "validator_value": ["Male", "Female", "Unknown"],
        "validation_error": "'Alien' is not one of ['Male', 'Female', 'Unknown']",
    }
    col = _col(header="sex", prop_name="sex", data_type="enum",
               enum=("Male", "Female", "Unknown"))
    msg = friendly_message(error, col)
    assert "Male" in msg and "Female" in msg


def test_required_error_names_the_column():
    """A required-field error should say which column can't be empty."""
    error = {
        "validator": "required",
        "validation_error": "'sample_type' is a required property",
    }
    col = _col(header="sample_type", prop_name="sample_type", data_type="enum")
    msg = friendly_message(error, col)
    assert "sample_type" in msg
    assert "empty" in msg.lower()


def test_pattern_error_shows_the_format():
    """A pattern error should surface the expected format so the user can match it."""
    error = {
        "validator": "pattern",
        "validation_error": "'C1' does not match '^C[0-9]{3}$'",
    }
    col = _col(header="consent_code", prop_name="consent_code",
               data_type="string", pattern="^C[0-9]{3}$")
    msg = friendly_message(error, col)
    assert "^C[0-9]{3}$" in msg


def test_link_error_points_to_parent_sheet():
    """A dangling-link error should name the parent sheet and the missing value."""
    error = {
        "validator": "link",
        "validator_value": "subject",
        "validation_error": (
            "Link 'subjects' references subject 'ghost' (by submitter_id) "
            "but no matching record exists in subject.json"
        ),
    }
    msg = friendly_message(error, None)
    assert "ghost" in msg
    assert "subject" in msg
