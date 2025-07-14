# Fedora-AutoEnv-Setup/scripts/phase_manager.py

import json
from pathlib import Path
from typing import Dict

from scripts import console_output as con
from scripts.config import PHASES, STATUS_FILE_PATH, app_logger


def load_phase_status() -> Dict[str, bool]:
    """Loads the completion status of phases from the status file."""
    if STATUS_FILE_PATH.exists():
        try:
            with open(STATUS_FILE_PATH, 'r', encoding='utf-8') as f:
                status = json.load(f)
                for phase_id in PHASES:
                    if phase_id not in status:
                        status[phase_id] = False
                return status
        except (json.JSONDecodeError, IOError) as e:
            con.print_warning(f"Could not load status file '{STATUS_FILE_PATH.name}': {e}. Starting fresh.")
            return {phase_id: False for phase_id in PHASES}
    return {phase_id: False for phase_id in PHASES}

def save_phase_status(status: Dict[str, bool]):
    """Saves the completion status of phases to the status file."""
    try:
        with open(STATUS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(status, f, indent=4)
    except IOError as e:
        con.print_error(f"Could not save status file '{STATUS_FILE_PATH.name}': {e}")

def mark_phase_complete(phase_id: str, status: Dict[str, bool]):
    """Marks a phase as complete and saves the status."""
    if phase_id in status:
        status[phase_id] = True
        save_phase_status(status)
        con.print_success(f"'{PHASES[phase_id]['name']}' marked as complete.")
    else:
        con.print_warning(f"Attempted to mark unknown phase '{phase_id}' as complete.")

def are_dependencies_met(phase_id: str, status: Dict[str, bool]) -> bool:
    """Checks if all dependencies for a given phase are met."""
    if phase_id not in PHASES:
        con.print_error(f"Unknown phase ID '{phase_id}' for dependency check.")
        return False
    for dep_id in PHASES[phase_id]["dependencies"]:
        if not status.get(dep_id, False):
            return False
    return True
