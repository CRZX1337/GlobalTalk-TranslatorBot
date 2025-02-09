import json
import os
from typing import Any, Dict

def load_json(filename: str, default: Any = None) -> Any:
    """
    Loads data from a JSON file.

    Args:
        filename: The name of the JSON file.
        default: The default value to return if the file does not exist.

    Returns:
        The data loaded from the JSON file, or the default value if the file does not exist.
    """
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return default if default is not None else {}  # Return empty dict if default is None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON in file {filename}: {e}")
        return default if default is not None else {}
    except Exception as e:
        print(f"Error loading JSON from file {filename}: {e}")
        return default if default is not None else {}

def save_json(filename: str, data: Any) -> None:
    """
    Saves data to a JSON file.

    Args:
        filename: The name of the JSON file.
        data: The data to save.
    """
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)  # Added indent for readability
    except TypeError as e:
        print(f"Error saving JSON to file {filename}: {e}. Data type not serializable.")
    except Exception as e:
        print(f"Error saving JSON to file {filename}: {e}")