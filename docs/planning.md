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



class SchemaLoader:
    def __init__(self):
        # Initialize any required state (if needed in the future)
        pass

    def load(self, schema_path_or_obj):
        # Returns raw schema object
        pass


class SchemaResolver:
    """
    Abstracted wrapper for Gen3 schema resolution logic.
    Internally uses gen3-data-validator's ResolveSchema, but exposes a simplified interface.
    """
    def __init__(self):
        try:
            from gen3_data_validator import ResolveSchema
        except ImportError:
            raise ImportError("gen3_data_validator package is required for Gen3SchemaResolver")
        self._resolver = ResolveSchema()

    def get_node_order(self, schema, node_list=None):
        """
        Returns the ordered list of nodes as determined by the schema's graph model.
        Optionally restricts to a subset of nodes.
        """
        return self._resolver.get_node_order(schema, node_list=node_list)

    def resolve_schema(self, raw_schema):
        """
        Returns the fully dereferenced schema using the underlying resolver.
        """
        return self._resolver.resolve_schema(raw_schema)


class NodeGraphBuilder:
    def __init__(self):
        # Initialize any required state (if needed in the future)
        pass

    def build(self, resolved_schema, node_list):
        # Returns ordered node representation
        pass


class NodePropertyExtractor:
    def __init__(self):
        # Initialize any required state (if needed in the future)
        pass

    def extract_properties(self, node_def):
        # Returns property metadata
        pass


class ExcelTemplateWriter:
    def __init__(self):
        # Initialize any required state (if needed in the future)
        pass

    def write(self, ordered_nodes_properties, out_path, validation_rules=None):
        # Creates XLSX file
        pass


class TemplateGeneratorService:
    def __init__(self):
        # Set up component dependencies
        self.schema_loader = SchemaLoader()
        self.schema_resolver = SchemaResolver()
        self.node_graph_builder = NodeGraphBuilder()
        self.property_extractor = NodePropertyExtractor()
        self.template_writer = ExcelTemplateWriter()
        self.validation_engine = ValidationRulesEngine()

    def generate(self, schema_path, node_list, out_path):
        # Orchestrates the above components for end-to-end template generation
        pass


class ValidationRulesEngine:
    def __init__(self):
        # Initialize any required state (planned for future expansion)
        pass

    def get_rules_for_node(self, node_type):
        pass  # To be implemented in v2.0


```