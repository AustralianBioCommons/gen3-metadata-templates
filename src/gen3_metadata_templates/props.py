# class to extract and store property, data type, and description

import logging
from dataclasses import dataclass

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NodeProps:
    """Extracts and stores property names, data types, and descriptions from a resolved schema.

    This class provides utility methods to access schema property names, data types,
    and descriptions.
    """

    def __init__(self, resolved_schema: dict):
        """Initializes NodeProps with a resolved schema dictionary.

        Args:
            resolved_schema (dict): The fully resolved JSON schema for a node.
        """
        self.resolved_schema = resolved_schema

    def get_schema_name(self) -> str:
        """Returns the schema's title.

        Returns:
            str: The value of the 'title' field in the schema.
        """
        schema_name = self.resolved_schema['title']
        return schema_name

    def get_prop_names(self) -> list:
        """Returns a list of top-level property names in the schema.

        Returns:
            list: List of property names defined under 'properties'.
        """
        prop_names = list(self.resolved_schema['properties'].keys())
        return prop_names

    def get_prop_info(self, prop_name: str) -> dict:
        """Retrieves the property definition for a given property name.

        Args:
            prop_name (str): The name of the property to retrieve.

        Returns:
            dict: The property definition dictionary, or None if not found.

        Logs a warning if the property is not found.
        """
        prop_names = self.get_prop_names()
        prop_info = None

        if prop_name in prop_names:
            prop_info = self.resolved_schema['properties'][prop_name]
        else:
            logger.warning(
                f"Property '{prop_name}' not found in {self.get_schema_name()}"
            )

        return prop_info

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
        if prop_info is None:
            logger.warning(
                f"Property '{prop_name}' not found in {self.get_schema_name()}, could not pull type"
            )
            return None

        if "type" in prop_info and "pattern" in prop_info:
            prop_type = f"string | pattern = {prop_info['pattern']}"
        elif "type" in prop_info:
            prop_type = prop_info["type"]
        elif "enum" in prop_info:
            prop_type = "enum"
        else:
            logger.warning(
                f"Property '{prop_name}' has no 'type' or 'enum' key. "
                f"Could be an injected property, usually don't need "
                f"these in the template | prop_info = {prop_info}"
            )
            return None

        if not isinstance(prop_type, str):
            try:
                joined_types = ", ".join(prop_type)
                logger.warning(
                    f"Property type '{prop_type}' is not string, converting to string: {joined_types}"
                )
                return joined_types
            except TypeError:
                logger.warning(
                    f"Property type '{prop_type}' is not string and could not be joined."
                )
                return str(prop_type)

        return prop_type

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
        if prop_info is None:
            logger.warning(
                f"Property '{prop_name}' not found in {self.get_schema_name()}, could not pull description"
            )
            return None
        prop_description = None

        if "description" in prop_info:
            prop_description = prop_info['description']
        if "term" in prop_info:
            prop_description = prop_info['term']["description"]

        if prop_description is None:
            logger.warning(
                f"Property '{prop_name}' has no description key. "
                "Could be an injected property, usually don't need these in the "
                f"template | prop_info = {prop_info}"
            )

        return prop_description

@dataclass
class NodeInfo:
    name: str
    props: NodeProps