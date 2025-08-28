from gen3_validator.resolve_schema import ResolveSchema
from gen3_validator.dict import DataDictionary, get_min_node_path
from gen3_metadata_templates.props import PropExtractor
import xlsxwriter
import io
import logging
import openpyxl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import pandas as pd
except ImportError:
    logger.error("pandas is required to export to xlsx")
    raise


def _is_link_array(resolver: object, node: str, prop: str) -> bool:
    """
    Check if a property is a link array in a Gen3 schema.

    :param object resolver: The schema resolver object from gen3_validator, which should provide access to resolved schemas and node relationships.
    :param str node: The name of the node containing the property.
    :param str prop: The name of the property to check.

    :returns: True if the property is a link array, False otherwise.
    :rtype: bool
    """
    if node == "program" or node == "program.yaml":
        logger.info(
            "Skipping link array check for program since this is the top-level node in gen3."
        )
        return False

    links = resolver.get_node_link(f"{node}.yaml")[1]
    logger.info(f"Links found for node '{node}': {links}")
    link_names = [link['name'] for link in links]
    if prop in link_names:
        logger.info(f"Property '{prop}' is a link array in node '{node}'.")
        return True
    logger.info(f"Property '{prop}' is NOT a link array in node '{node}'.")
    return False


def _get_ordered_columns(
    df,
    resolver,
    exclude_columns=[]
):
    """
    Generate an ordered list of columns for a node template DataFrame.

    The order is: primary key first, then foreign keys, then remaining properties.
    Optionally, certain columns can be excluded.

    :param pandas.DataFrame df: DataFrame with at least 'prop_name' and 'node_name' columns.
    :param object resolver: Schema resolver object, used for _is_link_array.
    :param list exclude_columns: List of property names to exclude. Defaults to a standard set of Gen3-injected/system columns.

    :returns: Tuple of (ordered column names, ordered column indices)
    :rtype: tuple[list, list]

    :raises ValueError: If required columns ('prop_name', 'node_name') are missing from df.
    :raises Exception: If node_name cannot be determined from df.
    """
    if exclude_columns is None:
        exclude_columns = []

    # Check for required columns
    required_cols = {"prop_name", "node_name"}
    if not required_cols.issubset(df.columns):
        logger.error(f"DataFrame missing required columns: {required_cols - set(df.columns)}")
        raise ValueError(f"DataFrame must contain columns: {required_cols}")

    try:
        prop_names = df["prop_name"].to_list()
        node_name = df.iloc[0]["node_name"]
    except Exception as e:
        logger.error("Could not extract 'prop_name' or 'node_name' from DataFrame.", exc_info=True)
        raise Exception("Could not extract 'prop_name' or 'node_name' from DataFrame.") from e

    pk_name_list = []
    fk_names_list = []
    remain_prop_names = []

    # Build lists of primary key, foreign keys, and remaining property names
    for prop in prop_names:
        # filter excluded cols
        if prop in exclude_columns:
            continue
        # check if prop is primary key
        if prop == "submitter_id":
            pk_name_list.append(prop)
            continue
        # check if prop is fk link array
        try:
            if _is_link_array(resolver, node_name, prop):
                fk_names_list.append(prop)
                continue
        except Exception as e:
            logger.error(
                f"Error checking if '{prop}' is a link array for node '{node_name}': {e}",
                exc_info=True
            )
            raise Exception(f"Error checking if '{prop}' is a link array for node '{node_name}': {e}")
        remain_prop_names.append(prop)
    # ordering cols
    ord_cols_list = pk_name_list + fk_names_list + remain_prop_names

    # get column indexes in the DataFrame for the ordered columns
    ord_col_index = []
    for col in ord_cols_list:
        if col in prop_names:
            idx = prop_names.index(col)
            ord_col_index.append(idx)
        else:
            logger.error(f"Column '{col}' not found in DataFrame prop_names.")
            raise ValueError(f"Column '{col}' not found in DataFrame prop_names.")

    # rename columns for output: primary key and foreign keys get special names
    ord_cols_list_renamed = []
    for col in ord_cols_list:
        if col == "submitter_id":
            ord_cols_list_renamed.append(f"{node_name}-submitter_id")
            continue
        try:
            if _is_link_array(resolver, node_name, col):
                # Remove trailing 's' for plural, if present, for foreign key naming
                fk_name = col[:-1] if col.endswith("s") else col
                ord_cols_list_renamed.append(f"{fk_name}-submitter_id")
                continue
        except Exception as e:
            logger.error(
                f"Error checking if '{col}' is a link array for node '{node_name}': {e}",
                exc_info=True
            )
            raise Exception(f"Error checking if '{col}' is a link array for node '{node_name}': {e}")
        ord_cols_list_renamed.append(col)

    return ord_cols_list_renamed, ord_col_index


def _format_node_xlsx(df, resolver, exclude_columns: list = None):
    """
    Format a node DataFrame for Excel output, ordering columns and renaming as needed.

    :param pandas.DataFrame df: DataFrame with node properties.
    :param object resolver: Schema resolver object.
    :param list exclude_columns: List of property names to exclude.

    :returns: Formatted DataFrame with ordered and renamed columns.
    :rtype: pandas.DataFrame

    :raises Exception: If column ordering or renaming fails.
    """
    try:
        ordered_cols_list, ord_col_index = _get_ordered_columns(df, resolver, exclude_columns)
    except Exception as e:
        logger.error(f"Failed to get ordered columns: {e}", exc_info=True)
        raise Exception(f"Failed to get ordered columns: {e}")

    try:
        colnames = df['prop_name'].to_list()
        df_trimmed = df.drop(columns=["node_name", "prop_name"])
        df_trimmed = df_trimmed.reset_index(drop=True)
        df_transposed = df_trimmed.transpose().reset_index(drop=True)
        df_transposed.columns = colnames

        # pulling ordered cols
        df_final = df_transposed.iloc[:, ord_col_index]
        df_final.columns = ordered_cols_list
    except Exception as e:
        logger.error(f"Error formatting DataFrame columns: {e}", exc_info=True)
        raise Exception(f"Error formatting DataFrame columns: {e}")

    return df_final


def make_node_template_pd(resolver: object, node: str, exclude_columns: list = None, excluded_nodes: list = None):
    """
    Extract the properties of a specified node from a resolved schema dictionary
    and return them as a pandas DataFrame.

    :param object resolver: The schema resolver object.
    :param str node: The name of the node to extract properties for.
    :param list exclude_columns: List of property names to exclude. If None, uses a default set.

    :returns: DataFrame of node properties, formatted for Excel output.
    :rtype: pandas.DataFrame
    """

    if excluded_nodes is not None and node in excluded_nodes:
        logger.warning(f"Skipping node '{node}' since it is excluded.")
        return

    resolved_schema = resolver.return_resolved_schema(node)
    node_props = PropExtractor(resolved_schema)
    props_list = node_props.extract_properties()
    df = pd.DataFrame([p.__dict__ for p in props_list])
    df = _format_node_xlsx(df, resolver, exclude_columns)
    return df


def pd_to_xlsx_mem(df: pd.DataFrame, sheet_name: str) -> bytes:
    """
    Write a pandas DataFrame to an Excel (.xlsx) file in memory.

    :param pandas.DataFrame df: The DataFrame to write.
    :param str sheet_name: The name of the Excel sheet.

    :returns: The contents of the generated Excel file as bytes.
    :rtype: bytes
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output.getvalue()


def combine_xlsx_sheets(xlsx_bytes_dict: dict, output_filename: str):
    """
    Combine multiple in-memory xlsx files (as bytes) into a single xlsx file,
    with each input as a separate sheet.

    :param dict xlsx_bytes_dict: Dictionary where keys are sheet names and values are xlsx file bytes.
    :param str output_filename: The filename to save the combined xlsx file to.

    :returns: None
    """
    # Each value in xlsx_bytes_dict is bytes of an xlsx file with a single sheet
    with pd.ExcelWriter(output_filename, engine="xlsxwriter") as writer:
        for sheet_name, xlsx_bytes in xlsx_bytes_dict.items():
            print(sheet_name)
            # Read the xlsx bytes into a DataFrame
            df = pd.read_excel(io.BytesIO(xlsx_bytes))
            # Write to the combined Excel file under the given sheet name
            df.to_excel(writer, index=False, sheet_name=sheet_name)

    logger.info(f"Combined xlsx file saved to {output_filename}")


def generate_xlsx_template(resolver: object, target_node: str, output_filename: str, exclude_columns: list = None, excluded_nodes: list = None):
    """
    Generate Excel templates for a set of nodes in a Gen3 schema and combine them into a single Excel file.

    :param object resolver: The schema resolver object from gen3_validator, which should provide access to resolved schemas and node relationships.
    :param str target_node: The name of the target node for which to generate the template.
    :param str output_filename: The filename to save the combined Excel file to.

    :returns: None
    """

    if excluded_nodes is None:
        excluded_nodes = ["program", "project"]

    if exclude_columns is None:
        exclude_columns = [
            "type",
            "id",
            "state",
            "object_id",
            "file_state",
            "error_type",
            "ga4gh_drs_uri",
            "core_metadata_collections",
            "created_datetime",
            "updated_datetime"
        ]

    node_order = get_min_node_path(
        edges=resolver.get_all_node_pairs(),
        target_node=target_node
        ).path

    xlsx_dict = {}
    for node in node_order:
        if node in excluded_nodes:
            logger.warning(f"Skipping node '{node}' since it is excluded.")
            continue
        df = make_node_template_pd(resolver=resolver, node=node, exclude_columns=exclude_columns)
        if df is not None:
            xlsx_dict[node] = pd_to_xlsx_mem(df, node)
    combine_xlsx_sheets(xlsx_dict, output_filename)
