# Fedora-AutoEnv-Setup/scripts/config_loader.py

import yaml
from pathlib import Path
import sys

# Default configuration filename
DEFAULT_CONFIG_FILENAME = "packages.yaml"

def load_configuration(config_file_path: str = None) -> dict:
    """
    Loads configuration from a YAML file.

    Args:
        config_file_path (str, optional):
            The path to the YAML configuration file.
            If None, it looks for 'packages.yaml' in the following order:
            1. Parent directory of this script (project root).
            2. Current working directory.

    Returns:
        dict: A dictionary containing the configuration data.
              Returns an empty dictionary if the file is not found
              or if an error occurs during parsing.
    """
    if config_file_path:
        path_to_check = Path(config_file_path)
    else:
        # Try in the parent directory of this script (assuming script is in 'scripts/' and config is in root)
        project_root_path = Path(__file__).parent.parent / DEFAULT_CONFIG_FILENAME
        # Then try in the current working directory
        current_dir_path = Path.cwd() / DEFAULT_CONFIG_FILENAME

        if project_root_path.is_file():
            path_to_check = project_root_path
        elif current_dir_path.is_file():
            path_to_check = current_dir_path
        else:
            print(f"Error: Configuration file '{DEFAULT_CONFIG_FILENAME}' not found "
                  f"in '{Path(__file__).parent.parent}' (project root) or '{Path.cwd()}' (current directory).", file=sys.stderr)
            return {}

    if not path_to_check.is_file():
        print(f"Error: Configuration file '{path_to_check}' not found.", file=sys.stderr)
        return {}

    try:
        with open(path_to_check, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        if config_data is None: # Empty YAML file or only comments
            print(f"Warning: Configuration file '{path_to_check}' is empty or contains only comments.", file=sys.stderr)
            return {}
        return config_data
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{path_to_check}': {e}", file=sys.stderr)
        return {}
    except IOError as e:
        print(f"I/O error reading file '{path_to_check}': {e}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Unexpected error loading configuration from '{path_to_check}': {e}", file=sys.stderr)
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
        print(f"Error: Provided configuration is not a valid dictionary.", file=sys.stderr)
        return {}

    phase_config = config.get(phase_name)

    if phase_config is None:
        # It's a common case that a phase might not be defined, so a warning might be too noisy.
        # Consider if a silent failure or a debug log is more appropriate for your use case.
        # For now, retaining a print statement for clarity during development.
        # print(f"Info: Phase '{phase_name}' not found in configuration.", file=sys.stderr)
        return {}

    if not isinstance(phase_config, dict):
        print(f"Warning: Data for phase '{phase_name}' is not a dictionary. Found type: {type(phase_config)}", file=sys.stderr)
        return {}

    return phase_config