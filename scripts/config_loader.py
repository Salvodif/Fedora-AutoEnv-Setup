# Fedora-AutoEnv-Setup/scripts/config_loader.py

import json 
from pathlib import Path
import sys
# No direct use of system_utils specific functions here, but logger is used.
from scripts.logger_utils import app_logger # For internal logging

# Default configuration filename
DEFAULT_CONFIG_FILENAME = "packages.json" 

def load_configuration(config_file_path: str = None) -> dict:
    """
    Loads configuration from a JSON file.

    Args:
        config_file_path (str, optional):
            The path to the JSON configuration file.
            If None, it looks for 'packages.json' in the following order:
            1. Parent directory of this script (project root).
            2. Current working directory.

    Returns:
        dict: A dictionary containing the configuration data.
              Returns an empty dictionary if the file is not found
              or if an error occurs during parsing.
    """
    path_to_check: Optional[Path] = None # Initialize to None

    if config_file_path:
        app_logger.debug(f"Attempting to load configuration from specified path: {config_file_path}")
        path_to_check = Path(config_file_path)
    else:
        app_logger.debug(f"No config_file_path specified. Looking for '{DEFAULT_CONFIG_FILENAME}' in default locations.")
        # Try in the parent directory of this script (assuming script is in 'scripts/' and config is in root)
        # Path(__file__) is the path to this config_loader.py file.
        # .parent is 'scripts/'
        # .parent.parent is the project root 'Fedora-AutoEnv-Setup/'
        project_root_config_path = Path(__file__).resolve().parent.parent / DEFAULT_CONFIG_FILENAME
        current_dir_config_path = Path.cwd() / DEFAULT_CONFIG_FILENAME

        if project_root_config_path.is_file():
            app_logger.info(f"Found configuration file at project root: {project_root_config_path}")
            path_to_check = project_root_config_path
        elif current_dir_config_path.is_file():
            app_logger.info(f"Found configuration file in current working directory: {current_dir_config_path}")
            path_to_check = current_dir_config_path
        else:
            # Error message printed to stderr for user visibility if config is critical.
            # Also logged for script developers.
            error_msg = (f"Configuration file '{DEFAULT_CONFIG_FILENAME}' not found "
                         f"in '{Path(__file__).resolve().parent.parent}' (project root) "
                         f"or '{Path.cwd()}' (current directory).")
            print(f"Error: {error_msg}", file=sys.stderr)
            app_logger.error(error_msg)
            return {}

    if not path_to_check or not path_to_check.is_file(): # path_to_check should be set if we didn't return {} above
        error_msg = f"Configuration file '{path_to_check or config_file_path or DEFAULT_CONFIG_FILENAME}' not found or is not a file."
        print(f"Error: {error_msg}", file=sys.stderr)
        app_logger.error(error_msg)
        return {}

    app_logger.info(f"Loading configuration from: {path_to_check}")
    try:
        with open(path_to_check, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # json.load can return None if the JSON file contains just "null".
        # It will raise JSONDecodeError for an empty file or malformed JSON.
        if config_data is None: 
            warning_msg = f"Configuration file '{path_to_check}' contains 'null' or is effectively empty. Returning empty configuration."
            print(f"Warning: {warning_msg}", file=sys.stderr)
            app_logger.warning(warning_msg)
            return {} # Treat as empty configuration
        
        if not isinstance(config_data, dict):
            error_msg = f"Configuration file '{path_to_check}' does not contain a valid JSON object (dictionary) at the root. Found type: {type(config_data)}."
            print(f"Error: {error_msg}", file=sys.stderr)
            app_logger.error(error_msg)
            return {}
            
        app_logger.info(f"Successfully loaded configuration from '{path_to_check}'.")
        return config_data
    except json.JSONDecodeError as e:
        error_msg = f"Error parsing JSON file '{path_to_check}': {e}"
        print(f"Error: {error_msg}", file=sys.stderr)
        app_logger.error(error_msg, exc_info=False) # exc_info=False as e already contains good info
        return {}
    except IOError as e:
        error_msg = f"I/O error reading file '{path_to_check}': {e}"
        print(f"Error: {error_msg}", file=sys.stderr)
        app_logger.error(error_msg, exc_info=True)
        return {}
    except Exception as e: # Catch any other unexpected errors
        error_msg = f"Unexpected error loading configuration from '{path_to_check}': {e}"
        print(f"Error: {error_msg}", file=sys.stderr)
        app_logger.error(error_msg, exc_info=True)
        return {}

def get_phase_data(config: dict, phase_name: str) -> dict:
    """
    Extracts configuration data for a specific phase.

    Args:
        config (dict): The complete configuration dictionary.
        phase_name (str): The key name of the phase (e.g., "phase1_system_preparation").

    Returns:
        dict: A dictionary containing data for the specified phase.
              Returns an empty dictionary if the phase is not found or
              if the phase data is not a dictionary.
    """
    if not isinstance(config, dict):
        # This case should ideally be caught by load_configuration if it returns non-dict.
        # But as a safeguard for direct calls:
        app_logger.error(f"Invalid configuration provided to get_phase_data: Expected a dictionary, got {type(config)}.")
        # No print to stderr here, as this is more of an internal programming error.
        return {}

    phase_config_data = config.get(phase_name)

    if phase_config_data is None:
        # This is a common case (phase not defined in config), so log as info, not warning/error.
        # No print to stderr, as calling code usually handles this (e.g., skips the phase).
        app_logger.info(f"Phase '{phase_name}' not found in the loaded configuration.")
        return {}

    if not isinstance(phase_config_data, dict):
        # If a phase key exists but its value is not a dictionary, this is a config error.
        warning_msg = (f"Data for phase '{phase_name}' in configuration is not a dictionary. "
                       f"Found type: {type(phase_config_data)}. Returning empty data for this phase.")
        print(f"Warning: {warning_msg}", file=sys.stderr)
        app_logger.warning(warning_msg)
        return {}

    app_logger.debug(f"Successfully retrieved data for phase '{phase_name}'.")
    return phase_config_data