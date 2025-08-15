import pytest
from gen3_validator.resolve_schema import ResolveSchema
from gen3_metadata_templates.props import NodeProps

@pytest.fixture
def fixture_res_schema():
    resolver = ResolveSchema(schema_path="examples/schema/json/acdc_schema.json")
    resolver.resolve_schema()
    return resolver.schema_resolved['unaligned_reads_file.yaml']

def test_fixture_schema_version():
    resolver = ResolveSchema(schema_path="examples/schema/json/acdc_schema.json")
    resolver.resolve_schema()
    settings_schema = resolver.schema['_settings.yaml'] # note that version is in unresolved bundled json
    assert settings_schema['_dict_version'] == "0.4.7"

def test_init_NodeProps(fixture_res_schema):
    nodeprops = NodeProps(fixture_res_schema)
    assert fixture_res_schema == nodeprops.resolved_schema