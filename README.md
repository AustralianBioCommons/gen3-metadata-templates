# gen3-metadata-templates
Tool to create metadata submission templates from a gen3 json schema.

## installation
```bash
pip install gen3_metadata_templates
```

## Usage

```python
from gen3_validator.resolve_schema import ResolveSchema
from gen3_metadata_templates.props import NodeProps

# Creating a bundled resolved gen3 jsonschema
resolver = ResolveSchema(schema_path="examples/schema/json/acdc_schema.json")
resolver.resolve_schema()

# initialising node props class
node_props = NodeProps(resolver.schema_resolved['unaligned_reads_file.yaml'])

# getting schema name
node_props.get_schema_name()

# return prop names for the schema
prop_names = node_props.get_prop_names()
print(prop_names)

# return the data types for the properties
types = {}
for prop_name in prop_names:
    types[prop_name] = node_props.get_data_type(prop_name)
print(types)

# return the description for the properties
descriptions = {}
for prop_name in prop_names:
    descriptions[prop_name] = node_props.get_description(prop_name)
print(descriptions)
    
```

## Dev Installation
- Make sure you have [Poetry](https://python-poetry.org/docs/#installing-with-pipx) `version 2.1.3` installed.
```bash
git clone https://github.com/AustralianBioCommons/gen3-metadata-templates.git
cd gen3-metadata-templates
pip install poetry
poetry install
eval $(poetry env activate)
```