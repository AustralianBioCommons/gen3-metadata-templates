import pytest
import pandas as pd
from gen3_metadata_templates import templates

# --- Dummy Classes and Fixtures ---

class DummyResolver:
    """
    A simple mock resolver for testing.
    """
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
def dummy_resolver():
    """
    Returns a DummyResolver with some test data.
    """
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
def dummy_df():
    """
    Returns a DataFrame similar to what the template functions expect.
    """
    data = {
        "prop_name": ["submitter_id", "related_items", "samples", "other_prop"],
        "node_name": ["testnode"] * 4,
        "type": ["string", "array", "array", "integer"],
    }
    return pd.DataFrame(data)

# --- _is_link_array ---

def test_is_link_array_true(dummy_resolver):
    """
    Checks that _is_link_array returns True for a property that is a link array.
    """
    assert templates._is_link_array(dummy_resolver, "testnode", "related_items") is True

def test_is_link_array_false(dummy_resolver):
    """
    Checks that _is_link_array returns False for a property that is not a link array.
    """
    assert templates._is_link_array(dummy_resolver, "testnode", "notalink") is False

def test_is_link_array_program_logs(dummy_resolver, caplog):
    """
    Checks that _is_link_array returns False and logs a message for the 'program' node.
    """
    with caplog.at_level("INFO"):
        result = templates._is_link_array(dummy_resolver, "program", "anything")
        assert result is False
        assert "Skipping link array check for program" in caplog.text

# --- _get_ordered_columns ---

def test_get_ordered_columns_happy_path(dummy_df, dummy_resolver):
    """
    Checks that columns are ordered and renamed as expected.
    """
    expected_cols = [
        "testnode-submitter_id", "related_item-submitter_id", "sample-submitter_id", "other_prop"
    ]
    expected_idx = [0, 1, 2, 3]
    out_cols, out_idx = templates._get_ordered_columns(dummy_df, dummy_resolver, exclude_columns=[])
    assert out_cols == expected_cols
    assert out_idx == expected_idx

def test_get_ordered_columns_exclude(dummy_df, dummy_resolver):
    """
    Checks that excluded columns are not in the output.
    """
    exclude = ["other_prop"]
    out_cols, _ = templates._get_ordered_columns(dummy_df, dummy_resolver, exclude_columns=exclude)
    assert "other_prop" not in out_cols

def test_get_ordered_columns_missing_required(dummy_resolver):
    """
    Checks that a ValueError is raised if required columns are missing.
    """
    df = pd.DataFrame({"foo": [1], "bar": [2]})
    with pytest.raises(ValueError):
        templates._get_ordered_columns(df, dummy_resolver, exclude_columns=[])

def test_get_ordered_columns_empty_df(dummy_resolver):
    """
    Checks that an Exception is raised if the DataFrame is empty.
    """
    df = pd.DataFrame(columns=["prop_name", "node_name"])
    with pytest.raises(Exception):
        templates._get_ordered_columns(df, dummy_resolver, exclude_columns=[])

# --- _format_node_xlsx ---

def test_format_node_xlsx_happy_path(dummy_df, dummy_resolver):
    """
    Checks that the output DataFrame has the correct columns and order.
    """
    expected_cols = [
        "testnode-submitter_id", "related_item-submitter_id", "sample-submitter_id", "other_prop"
    ]
    df_out = templates._format_node_xlsx(dummy_df, dummy_resolver, exclude_columns=[])
    assert list(df_out.columns) == expected_cols

def test_format_node_xlsx_error(dummy_resolver):
    """
    Checks that an error is raised if the DataFrame is missing required columns.
    """
    df = pd.DataFrame({"foo": [1], "bar": [2]})
    with pytest.raises(Exception):
        templates._format_node_xlsx(df, dummy_resolver, exclude_columns=[])

# --- make_node_template_pd ---

def test_make_node_template_pd_excluded_node(dummy_resolver):
    """
    Checks that None is returned if the node is in excluded_nodes.
    """
    result = templates.make_node_template_pd(dummy_resolver, "testnode", exclude_columns=[], excluded_nodes=["testnode"])
    assert result is None

def test_make_node_template_pd_happy_path(monkeypatch, dummy_resolver):
    """
    Checks that a DataFrame is returned with the correct columns.
    """
    class DummyProp:
        def __init__(self, name):
            self.prop_name = name
            self.node_name = "testnode"
            self.type = "string"
    # Patch PropExtractor to return dummy properties
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
    df = templates.make_node_template_pd(dummy_resolver, "testnode", exclude_columns=[])
    assert isinstance(df, pd.DataFrame)
    assert "testnode-submitter_id" in df.columns

# --- pd_to_xlsx_mem ---

def test_pd_to_xlsx_mem_returns_bytes(dummy_df):
    """
    Checks that pd_to_xlsx_mem returns bytes and the output starts with XLSX magic number.
    """
    xlsx_bytes = templates.pd_to_xlsx_mem(dummy_df, "Sheet1")
    assert isinstance(xlsx_bytes, bytes)
    assert xlsx_bytes[:2] == b'PK'

# --- combine_xlsx_sheets ---

def test_combine_xlsx_sheets_creates_file(tmp_path):
    """
    Checks that combine_xlsx_sheets creates a non-empty file.
    """
    df1 = pd.DataFrame({"a": [1, 2]})
    df2 = pd.DataFrame({"b": [3, 4]})
    bytes1 = templates.pd_to_xlsx_mem(df1, "Sheet1")
    bytes2 = templates.pd_to_xlsx_mem(df2, "Sheet2")
    out_file = tmp_path / "combined.xlsx"
    templates.combine_xlsx_sheets({"Sheet1": bytes1, "Sheet2": bytes2}, str(out_file))
    assert out_file.exists()
    assert out_file.stat().st_size > 0

def test_combine_xlsx_sheets_empty(tmp_path):
    """
    Checks that combine_xlsx_sheets works with an empty dict (should create a file).
    """
    out_file = tmp_path / "empty.xlsx"
    templates.combine_xlsx_sheets({}, str(out_file))
    assert out_file.exists()
    assert out_file.stat().st_size > 0

# --- generate_xlsx_template ---

def test_generate_xlsx_template_single_node(monkeypatch, tmp_path, dummy_resolver):
    """
    Checks that generate_xlsx_template creates a file for a single node.
    """
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
    templates.generate_xlsx_template(dummy_resolver, "testnode", str(out_file))
    assert out_file.exists()
    assert out_file.stat().st_size > 0

def test_generate_xlsx_template_multiple_nodes(monkeypatch, tmp_path, dummy_resolver):
    """
    Checks that generate_xlsx_template creates a file with multiple sheets for multiple nodes.
    """
    class DummyProp:
        def __init__(self, name):
            self.prop_name = name
            self.node_name = name
            self.type = "string"
    monkeypatch.setattr(
        templates, "PropExtractor",
        lambda schema: type("PE", (), {
            "extract_properties": lambda self: [
                DummyProp("submitter_id"),
                DummyProp("related_items"),
            ]
        })()
    )
    # Simulate two nodes
    monkeypatch.setattr(
        templates, "get_min_node_path",
        lambda edges, target_node: type("Path", (), {"path": ["node1", "node2"]})()
    )
    dummy_resolver._resolved_schema = {
        "node1": {},
        "node2": {},
    }
    out_file = tmp_path / "multi_template.xlsx"
    templates.generate_xlsx_template(dummy_resolver, "node1", str(out_file))
    assert out_file.exists()
    assert out_file.stat().st_size > 0

# --- Edge Cases and Error Handling ---

def test_format_node_xlsx_none_exclude_columns(dummy_df, dummy_resolver):
    """
    Checks that passing None for exclude_columns does not raise an error.
    """
    # This should not raise an error
    df_out = templates._format_node_xlsx(dummy_df, dummy_resolver, exclude_columns=None)
    assert isinstance(df_out, pd.DataFrame)