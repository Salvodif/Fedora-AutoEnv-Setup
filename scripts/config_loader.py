# Fedora-AutoEnv-Setup/scripts/config_loader.py

import json
from pathlib import Path
from typing import Dict, Any

from scripts import console_output as con
from scripts.config import app_logger

def load_configuration(config_file: str) -> Dict[str, Any]:
    """Loads the configuration from the given JSON file."""
    config_path = Path(config_file)
    if not config_path.is_file():
        con.print_error(f"Configuration file '{config_file}' not found.")
        return {}

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        con.print_error(f"Error loading configuration file '{config_file}': {e}")
        return {}
