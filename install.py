# Fedora-AutoEnv-Setup/install.py

import json
import sys
import os # For os.geteuid() if we add root check
from pathlib import Path
from typing import Dict, List, Callable, Optional

from scripts.logger_utils import setup_logger, app_logger
from scripts import console_output as con
from scripts import config_loader
from scripts import phase1_system_preparation
from scripts import phase2_basic_installation
from scripts import phase3_terminal_enhancement
from scripts import phase4_gnome_configuration # Import new phase
from scripts import phase5_nvidia_installation # Import new phase
from scripts import phase6_additional_packages # Import new phase


# --- Constants ---
STATUS_FILE_NAME = "install_status.json"
CONFIG_FILE_NAME = "packages.yaml" # Referenced by config_loader

# Define phase names (keys should match those in packages.yaml for consistency)
# These will also be the keys in our status file.
PHASES = {
    "phase1_system_preparation": {
        "name": "Phase 1: System Preparation ⚙️",
        "description": "Initial system checks, DNF configuration, RPM Fusion, DNS, system update, Flathub, and hostname.",
        "dependencies": [],
        "handler": phase1_system_preparation.run_phase1
    },
    "phase2_basic_configuration": {
        "name": "Phase 2: Basic System Package Configuration 📦",
        "description": "Install essential CLI tools, Python, Zsh, media codecs, etc.",
        "dependencies": ["phase1_system_preparation"],
        "handler": phase2_basic_installation.run_phase2
    },
    "phase3_terminal_enhancement": {
        "name": "Phase 3: Terminal Enhancement 💻✨",
        "description": "Set up Zsh, install plugins (Oh My Zsh assumed for paths), and copy custom configs.",
        "dependencies": ["phase2_basic_configuration"], # Depends on Zsh and git
        "handler": phase3_terminal_enhancement.run_phase3
    },
    "phase4_gnome_configuration": {
        "name": "Phase 4: GNOME Configuration & Extensions 🎨🖼️",
        "description": "Install GNOME Tweaks, Extension Manager, and configured extensions.",
        "dependencies": ["phase1_system_preparation", "phase2_basic_configuration"], # Flatpak setup in P1, pip in P2
        "handler": phase4_gnome_configuration.run_phase4
    },
    "phase5_nvidia_installation": {
        "name": "Phase 5: NVIDIA Driver Installation 🎮🖥️",
        "description": "Install NVIDIA proprietary or open kernel drivers. Requires compatible GPU and user confirmation.",
        "dependencies": ["phase1_system_preparation"], # Depends on DNF, RPM Fusion setup from Phase 1
        "handler": phase5_nvidia_installation.run_phase5
    },
    "phase6_additional_packages": {
        "name": "Phase 6: Additional User Packages 🧩🌐",
        "description": "Install user-selected applications from DNF and Flatpak.",
        "dependencies": ["phase1_system_preparation", "phase2_basic_configuration"],
        "handler": phase6_additional_packages.run_phase6
    }
}

# Path to the status file (in the same directory as install.py)
STATUS_FILE_PATH = Path(__file__).parent / STATUS_FILE_NAME

# --- Phase Status Management ---

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
            con.print_warning(f"Could not load status file '{STATUS_FILE_NAME}': {e}. Starting fresh.")
            return {phase_id: False for phase_id in PHASES}
    return {phase_id: False for phase_id in PHASES}

def save_phase_status(status: Dict[str, bool]):
    """Saves the completion status of phases to the status file."""
    try:
        with open(STATUS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(status, f, indent=4)
    except IOError as e:
        con.print_error(f"Could not save status file '{STATUS_FILE_NAME}': {e}")

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

# Placeholder is no longer needed as actual handlers are used.
# def run_phase_placeholder(phase_id: str, app_config: dict) -> bool:
#     ...

# --- Main Menu and Application Logic ---

def display_main_menu(phase_status: Dict[str, bool]):
    """Displays the main menu of available phases."""
    con.print_step("Fedora AutoEnv Setup - Main Menu", char="*")
    con.print_info("Select a phase to run, or 'q' to quit.")
    con.print_rule()

    menu_items: Dict[str, str] = {} # Maps menu number (str) to phase_id (str)
    item_number = 1

    # Sort phases for consistent display order, e.g., by key
    # sorted_phase_ids = sorted(PHASES.keys()) # Or define a specific order if needed

    for phase_id, phase_info in PHASES.items(): # Using dict order (Python 3.7+)
        status_text = ""
        can_run = are_dependencies_met(phase_id, phase_status)

        if phase_status.get(phase_id, False):
            status_text = "[bold green](Completed)[/]"
        elif not can_run:
            # Get names of unmet dependencies
            unmet_deps_names = [
                PHASES[dep_id]["name"]
                for dep_id in phase_info["dependencies"]
                if not phase_status.get(dep_id, False)
            ]
            deps_str = ", ".join(unmet_deps_names)
            status_text = f"[bold yellow](Locked - Needs: {deps_str})[/]"
        else:
            status_text = "[cyan](Available)[/]"

        menu_label = f"{item_number}. {phase_info['name']} {status_text}"
        con.console.print(menu_label)
        
        # Allow selection if (available and not completed) OR (completed and can_run - for re-running)
        if (can_run and not phase_status.get(phase_id, False)) or \
           (phase_status.get(phase_id, False) and can_run):
            menu_items[str(item_number)] = phase_id
        item_number += 1
    
    con.print_rule()
    con.console.print(" q. Quit")
    return menu_items

def main():
    """Main function to run the Fedora AutoEnv Setup utility."""

    app_logger.info("Fedora AutoEnv Setup script started.")

    try:
        # Check if running as root, many phases need it
        # if os.geteuid() != 0:
        #     con.print_error("This script needs to be run with sudo or as root for many operations.", exit_after=True)
        #     sys.exit(1)
        # Note: Some phases determine target_user from SUDO_USER, so running via `sudo ./install.py` is preferred.

        # Load application-wide configuration from packages.yaml
        app_config = config_loader.load_configuration(CONFIG_FILE_NAME) # Explicitly pass filename
        if not app_config: # load_configuration returns {} on error or empty file
            # Check if the file itself is missing, as load_configuration prints detailed errors
            if not Path(CONFIG_FILE_NAME).is_file():
                con.print_error(f"Critical: Configuration file '{CONFIG_FILE_NAME}' not found in project root or current directory.", exit_after=True)
            else:
                # File exists but is empty, or parsing failed (error already printed by loader)
                con.print_error(f"Critical: Failed to load or parse '{CONFIG_FILE_NAME}'. Please ensure it exists and is valid. Check messages above.", exit_after=True)
            sys.exit(1) # exit_after=True should handle this, but being explicit.

        phase_status = load_phase_status()

        while True:
            menu_options = display_main_menu(phase_status)
            # Generate choice list for Prompt.ask dynamically
            valid_choices = list(menu_options.keys()) + ['q', 'Q']
            
            choice = con.ask_question("Enter your choice:", choices=valid_choices).lower()

            if choice == 'q':
                con.print_info("Exiting Fedora AutoEnv Setup. Bye!")
                break
            elif choice in menu_options:
                phase_to_run_id = menu_options[choice]
                phase_to_run_info = PHASES[phase_to_run_id]

                if not are_dependencies_met(phase_to_run_id, phase_status):
                    # This check is somewhat redundant due to menu display logic, but safe
                    con.print_warning(f"Cannot run '{phase_to_run_info['name']}'. Dependencies not met.")
                    con.ask_question("Press Enter to continue...")
                    continue

                if phase_status.get(phase_to_run_id, False): # If phase is marked complete
                    if not con.confirm_action(f"'{phase_to_run_info['name']}' is already marked as complete. Run again?", default=False):
                        continue

                con.print_info(f"\nStarting '{phase_to_run_info['name']}'...")
                
                # *** THE FIX IS HERE: Pass app_config to the handler ***
                success = phase_to_run_info["handler"](app_config) 
                
                if success:
                    mark_phase_complete(phase_to_run_id, phase_status)
                else:
                    con.print_error(f"'{phase_to_run_info['name']}' encountered an error or was not fully completed.")

                if not con.confirm_action("Return to main menu?", default=True):
                    con.print_info("Exiting Fedora AutoEnv Setup. Bye!")
                    break
            else:
                con.print_warning("Invalid choice. Please try again.")
    except Exception as e:
        # con.console.print_exception(show_locals=True) # Rich traceback to console
        app_logger.critical(f"An unexpected critical error occurred in the main application: {e}", exc_info=True) # Log with traceback
        con.print_error(f"An unexpected critical error occurred: {e}. Check the log file for details.")


    # In finally block:
    finally:
        app_logger.info("Fedora AutoEnv Setup script finished.")
        con.print_info("Fedora AutoEnv Setup finished.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        con.print_info("\nOperation cancelled by user. Exiting.")
    except Exception as e:
        con.console.print_exception(show_locals=True) # Rich traceback for debugging
        con.print_error(f"An unexpected critical error occurred in the main application: {e}")
    finally:
        con.print_info("Fedora AutoEnv Setup finished.")