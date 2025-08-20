# class to extract and store property, data type, and description

import logging
from dataclasses import dataclass

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PropExtractor:
    """Extracts and stores property names, data types, and descriptions from a resolved schema.

    This class provides utility methods to access schema property names, data types,
    and descriptions.
    """

    def __init__(self, resolved_schema: dict):
        """Initializes PropExtractor with a resolved schema dictionary.

        Args:
            resolved_schema (dict): The fully resolved JSON schema for a node.
        """
        self.resolved_schema = resolved_schema
        self.schema_name = self.resolved_schema.get('title', 'Unknown Schema')
        self._properties = self.resolved_schema.get('properties', {})

    # def get_schema_name(self) -> str:
    #     """Returns the schema's title.

    #     Returns:
    #         str: The value of the 'title' field in the schema.
    #     """
    #     schema_name = self.resolved_schema['title']
    #     return schema_name

    def get_prop_names(self) -> list:
        """Returns a list of top-level property names in the schema.

        Returns:
            list: List of property names defined under 'properties'.
        """
        prop_names = list(self._properties.keys())
        return prop_names

    def get_prop_info(self, prop_name: str) -> dict:
        """Retrieves the property definition for a given property name.

        Args:
            prop_name (str): The name of the property to retrieve.

        Returns:
            dict: The property definition dictionary, or None if not found.

        """
        return self._properties.get(prop_name)

    def get_data_type(self, prop_name: str) -> str:
        """Returns the data type of a given property.

        Handles 'type', 'pattern', and 'enum' keys, and attempts to join non-string types.

        Args:
            prop_name (str): The name of the property.

        Returns:
            str: The data type as a string, or None if not found or not applicable.

        Logs a warning if the property or its type is not found.
        """
        prop_info = self.get_prop_info(prop_name)
        if not prop_info:
            logger.warning(
                f"Property '{prop_name}' not found in {self.get_schema_name()}, could not pull type"
            )
            return None
        
        if "type" in prop_info and "pattern" in prop_info:
            return f"string | pattern = {prop_info['pattern']}"
        if "type" in prop_info:
            return self._format_type_value(prop_info["type"])
        if "enum" in prop_info:
            return "enum"

        logger.warning(
            f"Property '{prop_name}' has no 'type' or 'enum' key. "
            f"Could be an injected property | prop_info = {prop_info}"
        )
        return None

    def _format_type_value(self, type_value) -> str:
        """Helper to format a type value which might be a string or list."""
        if isinstance(type_value, list):
            return ", ".join(type_value)
        return str(type_value)

    def get_description(self, prop_name: str) -> str:
        """Returns the description for a given property.

        Checks both 'description' and 'term.description' fields.

        Args:
            prop_name (str): The name of the property.

        Returns:
            str: The property description, or None if not found.

        Logs a warning if the property or its description is not found.
        """
        prop_info = self.get_prop_info(prop_name)
        if not prop_info:
            logger.warning(
                f"Property '{prop_name}' not found in {self.get_schema_name()}, could not pull description"
            )
            return None

        description = prop_info.get("description")
        if description is None:
            term_info = prop_info.get("term", {})
            description = term_info.get("description")

        if description is None:
            logger.warning(
                f"Property '{prop_name}' has no description key. "
                "Could be an injected property, usually don't need these in the "
                f"template | prop_info = {prop_info}"
            )

        return description

@dataclass
class NodeProps:
    node_name: str
    prop_name: str
    data_type: str
    description: str

