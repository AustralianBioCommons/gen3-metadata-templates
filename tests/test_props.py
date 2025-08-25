import pytest
from gen3_validator.resolve_schema import ResolveSchema
from gen3_metadata_templates.props import PropExtractor


@pytest.fixture
def fixture_res_schema():
    resolver = ResolveSchema(
        schema_path="examples/schema/json/acdc_schema.json"
    )
    resolver.resolve_schema()
    return resolver.schema_resolved['unaligned_reads_file.yaml']


def test_fixture_schema_version():
    resolver = ResolveSchema(
        schema_path="examples/schema/json/acdc_schema.json"
    )
    resolver.resolve_schema()
    # note that version is in unresolved bundled json
    settings_schema = resolver.schema['_settings.yaml']
    assert settings_schema['_dict_version'] == "0.4.7"


def test_init_PropExtractor(fixture_res_schema):
    nodeprops = PropExtractor(fixture_res_schema)
    assert fixture_res_schema == nodeprops.resolved_schema


@pytest.fixture
def fixture_PropExtractor(fixture_res_schema):
    nodeprops = PropExtractor(fixture_res_schema)
    return nodeprops


def test_get_schema_name(fixture_PropExtractor):
    nodeprops = fixture_PropExtractor
    assert nodeprops.schema_name == "unaligned_reads_file"


def test_get_prop_names(fixture_PropExtractor):
    nodeprops = fixture_PropExtractor
    expected = [
        'type',
        'id',
        'submitter_id',
        'state',
        'project_id',
        'created_datetime',
        'updated_datetime',
        'file_name',
        'file_size',
        'file_format',
        'md5sum',
        'object_id',
        'file_state',
        'error_type',
        'ga4gh_drs_uri',
        'genomics_assay',
        'core_metadata_collections',
        'data_category',
        'data_format',
        'data_type',
        'run_id',
    ]
    assert nodeprops.get_prop_names() == expected


def test_get_prop_info_found(fixture_PropExtractor):
    nodeprops = fixture_PropExtractor
    expected = {
        'type': 'string',
        'term': {
            'description': (
                "The 128-bit hash value expressed as a 32 digit hexadecimal "
                "number used as a file's digital fingerprint.\n"
            )
        },
        'pattern': '^[a-f0-9]{32}$'
    }
    assert nodeprops.get_prop_info('md5sum') == expected


def test_get_data_type(fixture_PropExtractor):
    nodeprops = fixture_PropExtractor
    assert nodeprops.get_data_type('run_id') == "string"


def test_get_data_type_pattern(fixture_PropExtractor):
    nodeprops = fixture_PropExtractor
    assert (
        nodeprops.get_data_type('md5sum')
        == "string | pattern = ^[a-f0-9]{32}$"
    )


def test_get_data_type_enum(fixture_PropExtractor):
    nodeprops = fixture_PropExtractor
    assert nodeprops.get_data_type('file_state') == "enum"


def test_get_data_type_none(fixture_PropExtractor):
    nodeprops = fixture_PropExtractor
    assert nodeprops.get_data_type('state') is None


def test_get_data_type_warn(fixture_PropExtractor, caplog):
    nodeprops = fixture_PropExtractor
    # check for not found warning
    with caplog.at_level("WARNING"):
        assert nodeprops.get_data_type('state') is None
        assert any(
            "Property 'state' has no 'type' or 'enum' key. Could be an injected property"
            in record.message
            for record in caplog.records
        )


def test_get_description(fixture_PropExtractor):
    nodeprops = fixture_PropExtractor
    expected = (
        "The 128-bit hash value expressed as a 32 digit hexadecimal number "
        "used as a file's digital fingerprint.\n"
    )
    assert nodeprops.get_description('md5sum') == expected


def test_get_description_prop_with_term(fixture_PropExtractor):
    nodeprops = fixture_PropExtractor
    expected = (
        "Unique ID for any specific defined piece of work that is undertaken or "
        "attempted to meet a single requirement.\n"
    )
    assert nodeprops.get_description('project_id') == expected


def test_get_description_not_found(fixture_PropExtractor, caplog):
    nodeprops = fixture_PropExtractor
    # check for not found warning
    with caplog.at_level("WARNING"):
        assert nodeprops.get_description('core_metadata_collections') is None
        assert any(
            "Property 'core_metadata_collections' has no description key"
            in record.message
            for record in caplog.records
        )