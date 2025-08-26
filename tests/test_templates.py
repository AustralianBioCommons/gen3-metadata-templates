import pytest
import pandas as pd
from gen3_metadata_templates import templates

# --- Fixtures and Dummy Classes ---

class DummyResolver:
    """Minimal mock for resolver object used in templates.py."""
    def __init__(self, node_links=None, resolved_schema=None, node_pairs=None):
        self._node_links = node_links or {}
        self._resolved_schema = resolved_schema or {}
        self._node_pairs = node_pairs or []

    def get_node_link(self, node_yaml):
        # Returns (node, links)
        return (node_yaml, self._node_links.get(node_yaml.replace('.yaml', ''), []))

    def return_resolved_schema(self, node):
        return self._resolved_schema.get(node, {})

    def get_all_node_pairs(self):
        return self._node_pairs

@pytest.fixture
def fixture_dummy_resolver():
    node_links = {
        "testnode": [
            {"name": "related_items"},
            {"name": "samples"}
        ]
    }
    resolved_schema = {
        "testnode": {
            "properties": {
                "submitter_id": {"type": "string"},
                "related_items": {"type": "array"},
                "samples": {"type": "array"},
                "other_prop": {"type": "integer"},
            }
        }
    }
    node_pairs = [
        ("program", "project"),
        ("project", "testnode"),
    ]
    return DummyResolver(node_links=node_links, resolved_schema=resolved_schema, node_pairs=node_pairs)

@pytest.fixture
def fixture_dummy_df():
    data = {
        "prop_name": ["submitter_id", "related_items", "samples", "other_prop"],
        "node_name": ["testnode"] * 4,
        "type": ["string", "array", "array", "integer"],
    }
    return pd.DataFrame(data)

def test_is_link_array_true(fixture_dummy_resolver):
    node = "testnode"
    prop = "related_items"
    assert templates._is_link_array(fixture_dummy_resolver, node, prop) is True

def test_is_link_array_false(fixture_dummy_resolver):
    node = "testnode"
    prop = "notalink"
    assert templates._is_link_array(fixture_dummy_resolver, node, prop) is False

def test_is_link_array_program_skips(fixture_dummy_resolver, caplog):
    node = "program"
    prop = "anything"
    with caplog.at_level("INFO"):
        assert templates._is_link_array(fixture_dummy_resolver, node, prop) is False
        assert "Skipping link array check for program" in caplog.text

def test_get_ordered_columns(fixture_dummy_df, fixture_dummy_resolver):
    df = fixture_dummy_df
    resolver = fixture_dummy_resolver
    expected_cols = [
        "testnode-submitter_id", "related_item-submitter_id", "sample-submitter_id", "other_prop"
    ]
    expected_idx = [0, 1, 2, 3]
    out_cols, out_idx = templates._get_ordered_columns(df, resolver, exclude_columns=[])
    assert out_cols == expected_cols
    assert out_idx == expected_idx

def test_get_ordered_columns_exclude(fixture_dummy_df, fixture_dummy_resolver):
    df = fixture_dummy_df
    resolver = fixture_dummy_resolver
    exclude = ["other_prop"]
    out_cols, _ = templates._get_ordered_columns(df, resolver, exclude_columns=exclude)
    assert "other_prop" not in out_cols

def test_format_node_xlsx(fixture_dummy_df, fixture_dummy_resolver):
    df = fixture_dummy_df
    resolver = fixture_dummy_resolver
    expected_cols = [
        "testnode-submitter_id", "related_item-submitter_id", "sample-submitter_id", "other_prop"
    ]
    df_out = templates._format_node_xlsx(df, resolver, exclude_columns=[])
    assert list(df_out.columns) == expected_cols

def test_make_node_template_pd(monkeypatch, fixture_dummy_resolver):
    class DummyProp:
        def __init__(self, name):
            self.prop_name = name
            self.node_name = "testnode"
            self.type = "string"
    monkeypatch.setattr(
        templates, "PropExtractor",
        lambda schema: type("PE", (), {
            "extract_properties": lambda self: [
                DummyProp("submitter_id"),
                DummyProp("related_items"),
                DummyProp("samples"),
                DummyProp("other_prop")
            ]
        })()
    )
    # Pass exclude_columns as an empty list to avoid NoneType error
    df = templates.make_node_template_pd(fixture_dummy_resolver, "testnode", exclude_columns=[])
    assert isinstance(df, pd.DataFrame)
    assert "testnode-submitter_id" in df.columns

def test_pd_to_xlsx_mem(fixture_dummy_df):
    df = fixture_dummy_df
    xlsx_bytes = templates.pd_to_xlsx_mem(df, "Sheet1")
    assert isinstance(xlsx_bytes, bytes)
    assert xlsx_bytes[:2] == b'PK'

def test_combine_xlsx_sheets(tmp_path):
    df1 = pd.DataFrame({"a": [1, 2]})
    df2 = pd.DataFrame({"b": [3, 4]})
    bytes1 = templates.pd_to_xlsx_mem(df1, "Sheet1")
    bytes2 = templates.pd_to_xlsx_mem(df2, "Sheet2")
    out_file = tmp_path / "combined.xlsx"
    templates.combine_xlsx_sheets({"Sheet1": bytes1, "Sheet2": bytes2}, str(out_file))
    assert out_file.exists()
    assert out_file.stat().st_size > 0

def test_generate_xlsx_template(monkeypatch, tmp_path, fixture_dummy_resolver):
    class DummyProp:
        def __init__(self, name):
            self.prop_name = name
            self.node_name = "testnode"
            self.type = "string"
    monkeypatch.setattr(
        templates, "PropExtractor",
        lambda schema: type("PE", (), {
            "extract_properties": lambda self: [
                DummyProp("submitter_id"),
                DummyProp("related_items"),
                DummyProp("samples"),
                DummyProp("other_prop")
            ]
        })()
    )
    monkeypatch.setattr(
        templates, "get_min_node_path",
        lambda edges, target_node: type("Path", (), {"path": ["testnode"]})()
    )
    out_file = tmp_path / "template.xlsx"
    templates.generate_xlsx_template(fixture_dummy_resolver, "testnode", str(out_file))
    assert out_file.exists()
    assert out_file.stat().st_size > 0