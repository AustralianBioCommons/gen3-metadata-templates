I’m going to convert the provided content into clean, standards-compliant Markdown with proper headings, lists, and code fences where appropriate.

## Software Development Plan — schema_tool

### 1. Project Overview

- **Name**: schema_tool (Python package and CLI)
- **Purpose**: schema_tool reads a bundled JSON file containing a list of JSON schemas. Each item represents a “node” in a graph model. The tool will:
  1. Parse the bundle and convert each schema into an internal representation (`SchemaNode`), extracting:
     - Property name
     - Data type
     - Description
     - Required flag
  2. Determine dependencies between nodes (via `$ref` or a `links` array) and build a directed graph of node relationships.
  3. Topologically sort the nodes to establish a valid processing order.
  4. Given a user-specified list of node names (or all nodes by default), produce a property template:
     - JSON dictionary
     - Rows in a CSV file
- **Interfaces**:
  - Programmatic API for integration into Python code.
  - Command-line interface (CLI) for ad-hoc use.
- **Constraints**:
  - Minimal dependencies:
    - Standard `json` and `csv` modules.
    - Optional: `jsonschema` for `$ref` resolution.
  - Functional approach where possible.
  - Use `@dataclass` for structured data.
  - Follow PEP 8 naming conventions.
  - Modularize by functionality.

---

### 2. Repository Structure

```
schema_tool/                  # Top-level package
├── __init__.py               # Expose high-level functions
├── models.py                 # dataclasses: SchemaNode, SchemaProperty
├── loader.py                 # load_bundle(file_path) -> List[SchemaNode]
├── graph.py                  # build_adjacency(), topological_sort()
├── template.py               # make_json(), make_csv_rows(), save_json(), save_csv()
├── cli.py                    # CLI implementation (argparse or click)
tests/
├── test_loader.py
├── test_graph.py
├── test_template.py
README.md                     # Description, installation, usage
pyproject.toml                # Poetry config; include example schemas
examples/
└── bundled_schema_example.json
```

- **README.md should explain**:
  - What the tool does
  - Installation (pip/Poetry)
  - CLI usage examples
  - Programmatic API examples

---

### 3. Implementation Details

#### 3.1 Data Models (`models.py`)

- **`SchemaProperty` dataclass**:
  - `name: str`
  - `data_type: str`
  - `description: Optional[str]`
  - `required: bool = False`
  - `definitions: Dict[str, Any]` (optional, for nested definitions)
- **`SchemaNode` dataclass**:
  - `name: str` (schema title or ID)
  - `properties: List[SchemaProperty]`
  - `links_to: List[str]` (names of referenced nodes)
  - `raw_schema: Dict[str, Any]`
- Keep methods minimal (`__repr__`, optional `__post_init__`).

#### 3.2 Schema Loading (`loader.py`)

- **`load_bundle(file_path: str) -> List[SchemaNode]` should**:
  1. Load JSON file as list of schema objects.
  2. Extract node name from `title` or `id`.
  3. Build `SchemaProperty` instances:
     - Fill in `data_type` from `"type"`, default `'object'` if missing.
     - Capture `description` and `required` flag.
  4. Identify dependencies:
     - Look for `$ref` or `links` array entries.
     - Populate `links_to` list.
  5. Return list of `SchemaNode` objects.
- **Dependencies**: Only `json`. Optionally `jsonschema` for `$ref` resolution.

#### 3.3 Graph Operations (`graph.py`)

- **`build_adjacency(nodes)`**:
  - Input: iterable of `SchemaNode`
  - Output: `{ node_name: set(links_to_names) }`
- **`topological_sort(adj)`**:
  - Implement Kahn’s algorithm.
  - Return list of node names in dependency order.
  - Raise descriptive error on cycles.

#### 3.4 Template Generation (`template.py`)

- **`make_json(nodes, selected)`**:
  - Return `{ node_name: [ {name, type, description}, ... ] }`
- **`make_csv_rows(nodes, selected)`**:
  - Yield dictionaries with keys:
    - `node`
    - `property`
    - `type`
    - `description`
- **Saving functions**:
  - `save_json(selected_nodes, path)`
  - `save_csv(selected_nodes, path)`
- If `selected` is empty, include all nodes.

#### 3.5 CLI (`cli.py`)

- **CLI Options**:
  - `--bundle` (required): Path to JSON bundle.
  - `--nodes` (optional): Comma-separated node names.
  - `--format` (optional, default: `json`): Output format.
  - `--output` (required): Output file path.
- **Main flow**:
  1. Parse args.
  2. Call `load_bundle()`.
  3. Build adjacency, topologically sort.
  4. Select nodes (user list or sorted list).
  5. Call `save_json()` or `save_csv()`.
  6. Handle errors gracefully.
- Expose CLI entry in `pyproject.toml` under `[project.scripts]`.

---

### 4. Testing (`tests/`)

Use pytest. Include tests for:

- **`load_bundle()`**: property extraction, `links_to`, missing fields.
- **`build_adjacency()`, `topological_sort()`**: correct order, cycle detection.
- **`make_json()`, `make_csv_rows()`**: correct structure and filtering.
- **CLI**: end-to-end tests via `subprocess`.

---

### 5. Documentation & Packaging

- **README.md should include**:
  - Purpose & architecture.
  - Installation (pip, pipx, clone).
  - CLI usage examples.
  - Programmatic usage examples.
- **Packaging**:
  - Use Poetry.
  - Include `examples/` in distribution.
  - Add `jsonschema` only if needed.
  - Configure `[project.scripts]` for CLI.
  - Include pytest under `[tool.poetry.dev-dependencies]`.

---

### Outcome

Following this plan will produce a modular, maintainable tool with clear separation of concerns, minimal dependencies, and both CLI and API access.

- I reformatted your content into clean Markdown with proper `##`/`###` headings, normalized bullet lists, and fenced the repository tree. You can paste this directly into `docs/planning.md`.