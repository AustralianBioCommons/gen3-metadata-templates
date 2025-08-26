# gen3-metadata-templates
Tool to create metadata submission templates from a gen3 json schema.

## installation
```bash
pip install gen3_metadata_templates
```

## Usage

```python
from gen3_metadata_templates.templates import *
from gen3_validator.resolve_schema import ResolveSchema

resolver = ResolveSchema("path/to/gen3_schema.json")
resolver.resolve_schema()

generate_xlsx_template(resolver=resolver, target_node="unaligned_reads_file", output_filename="unaligned_reads_file.xlsx")


# some columns are excluded by default, but you can return all by using
generate_xlsx_template(resolver=resolver, target_node="unaligned_reads_file", output_filename="unaligned_reads_file.xlsx", exclude_columns= [])
    
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