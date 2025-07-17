# Templates Planning


**Plan for Generating Gen3 Metadata Templates:**

1. **Inputs:**
   - Gen3 JSON schema (draft 4)
   - List of data nodes to ingest

2. **Process:**
   - Infer the order of data nodes in the graph model from the JSON schema (using logic from gen3-data-validator).
   - Resolve the JSON schema to obtain all necessary definitions.
   - For each data node:
     - Extract properties, data types, and descriptions.
     - Add this information to a corresponding tab in an Excel spreadsheet, with tabs ordered according to the graph model.

3. **Output:**
   - A single Excel spreadsheet with one tab per data node, ordered as in the graph model.

4. **Versioning:**
   - Version 1.0: No data validation in the Excel spreadsheet.
   - Version 2.0: Add data validation features to the spreadsheet.


## Classes

inherit : `gen3-data-validator.ResolveSchema.get_node_order()`

```python

class ReadWrite:
    
    def read_json_schema

    def check_json_schema_draft

    def write_xlsx


class PropertyExtractor(ReadWrite):

    def resolve_schema

    def get_node_order

    def add_pk_fk

    def pull_prop_names

    def pull_data_types

    def pull_descriptions


class TemplateConstructor(ReadWrite, PropertyExtractor):

    def create_node_template

    def construct_excel



```