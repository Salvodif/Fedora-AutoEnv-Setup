# Fedora-AutoEnv-Setup/install.py

import json
import sys
from pathlib import Path
from typing import Dict, List, Callable, Optional

from scripts import console_output as con
from scripts import config_loader
from scripts import phase1_system_preparation
from scripts import phase2_basic_installation
from scripts import phase3_terminal_enhancement

# --- Constants ---
STATUS_FILE_NAME = "install_status.json"
CONFIG_FILE_NAME = "packages.yaml" # Referenced by config_loader

# Define phase names (keys should match those in packages.yaml for consistency)
# These will also be the keys in our status file.
PHASES = {
    "phase1_system_preparation": {
        "name": "Phase 1: System Preparation",
        "description": "Initial system checks and dnf5 setup.",
        "dependencies": [],
        "handler": phase1_system_preparation.run_phase1
    },
    "phase2_basic_configuration": {
        "name": "Phase 2: Basic System Package Configuration",
        "description": "Install essential CLI tools, Python, Zsh, etc.",
        "dependencies": ["phase1_system_preparation"],
        "handler": phase2_basic_installation.run_phase2
    },
    "phase3_terminal_enhancement": {
        "name": "Phase 3: Terminal Enhancement",
        "description": "Install Zsh plugins (Oh My Zsh assumed for paths).",
        "dependencies": ["phase2_basic_configuration"], # Depends on Zsh and git
        "handler": phase3_terminal_enhancement.run_phase3
    },
    "phase4_gnome_configuration": {
        "name": "Phase 4: GNOME Configuration & Extensions",
        "description": "Install GNOME Tweaks, Extension Manager, and extensions.",
        "dependencies": ["phase2_basic_configuration"], # Might depend on basic tools
        "handler": lambda: run_phase_placeholder("phase4_gnome_configuration") # Placeholder
    },
    "phase5_nvidia_installation": {
        "name": "Phase 5: NVIDIA Driver Installation",
        "description": "Setup RPM Fusion and install NVIDIA drivers.",
        "dependencies": ["phase1_system_preparation", "phase2_basic_configuration"], # Depends on dnf and core utils
        "handler": lambda: run_phase_placeholder("phase5_nvidia_installation") # Placeholder
    },
    "phase6_additional_packages": {
        "name": "Phase 6: Additional User Packages",
        "description": "Install applications like GIMP, Spotify, Steam, etc.",
        "dependencies": ["phase2_basic_configuration"], # General dependency
        "handler": lambda: run_phase_placeholder("phase6_additional_packages") # Placeholder
    }
    # Add more phases here as needed
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
                # Ensure all known phases are in the status, default to False if not
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

# --- Placeholder for Actual Phase Execution ---

def run_phase_placeholder(phase_id: str) -> bool:
    """
    Placeholder function for running a phase.
    In a real scenario, this would call the specific script/functions for the phase.
    """
    con.print_step(f"Executing: {PHASES[phase_id]['name']}")
    con.print_info(f"Running placeholder logic for {phase_id}...")
    # Simulate work
    import time
    time.sleep(1) # Simulate some work being done

    # Simulate success or failure (can be made more interactive or deterministic later)
    # For now, assume success for the placeholder
    succeeded = True # con.confirm_action(f"Did '{PHASES[phase_id]['name']}' complete successfully?", default=True)

    if succeeded:
        con.print_success(f"Placeholder for '{PHASES[phase_id]['name']}' completed.")
        return True
    else:
        con.print_error(f"Placeholder for '{PHASES[phase_id]['name']}' reported failure.")
        return False

# --- Main Menu and Application Logic ---

def display_main_menu(phase_status: Dict[str, bool]):
    """Displays the main menu of available phases."""
    con.print_step("Fedora AutoEnv Setup - Main Menu", char="*")
    con.print_info("Select a phase to run, or 'q' to quit.")
    con.print_rule()

    menu_items: Dict[str, str] = {}
    item_number = 1

    for phase_id, phase_info in PHASES.items():
        status_text = ""
        can_run = are_dependencies_met(phase_id, phase_status)

        if phase_status.get(phase_id, False):
            status_text = "[bold green](Completed)[/]"
        elif not can_run:
            deps_str = ", ".join([PHASES[dep]["name"] for dep in phase_info["dependencies"] if not phase_status.get(dep, False)])
            status_text = f"[bold yellow](Locked - Needs: {deps_str})[/]"
        else:
            status_text = "[cyan](Available)[/]"

        menu_label = f"{item_number}. {phase_info['name']} {status_text}"
        con.console.print(menu_label)
        if can_run and not phase_status.get(phase_id, False):
            menu_items[str(item_number)] = phase_id
        elif phase_status.get(phase_id, False) and can_run : # Allow re-running completed
             menu_items[str(item_number)] = phase_id

        item_number += 1

    con.print_rule()
    con.console.print(" q. Quit")
    return menu_items

def main():
    """Main function to run the Fedora AutoEnv Setup utility."""
    # Load configuration (optional here, but good practice if phases need it)
    # app_config = config_loader.load_configuration()
    # if not app_config:
    #     con.print_error("Failed to load 'packages.yaml'. Please ensure it exists and is valid.", exit_after=True)
    #     sys.exit(1) # Redundant due to exit_after but explicit

    phase_status = load_phase_status()

    while True:
        menu_options = display_main_menu(phase_status)
        choice = con.ask_question("Enter your choice:", choices=list(menu_options.keys()) + ['q']).lower()

        if choice == 'q':
            con.print_info("Exiting Fedora AutoEnv Setup. Bye!")
            break
        elif choice in menu_options:
            phase_to_run_id = menu_options[choice]
            phase_to_run_info = PHASES[phase_to_run_id]

            # Double check dependencies before running (menu should prevent this, but good practice)
            if not are_dependencies_met(phase_to_run_id, phase_status):
                con.print_warning(f"Cannot run '{phase_to_run_info['name']}'. Dependencies not met.")
                con.ask_question("Press Enter to continue...") # Pause
                continue

            if phase_status.get(phase_to_run_id, False):
                if not con.confirm_action(f"'{phase_to_run_info['name']}' is already marked as complete. Run again?", default=False):
                    continue

            con.print_info(f"Starting '{phase_to_run_info['name']}'...")
            # --- Actual phase execution would happen here ---
            # For now, we call the handler defined in PHASES, which is a placeholder
            success = phase_to_run_info["handler"]()
            # -----------------------------------------------
            if success:
                mark_phase_complete(phase_to_run_id, phase_status)
            else:
                con.print_error(f"'{phase_to_run_info['name']}' encountered an error or was cancelled.")

            con.ask_question("Press Enter to return to the menu...") # Pause
        else:
            con.print_warning("Invalid choice. Please try again.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        con.print_info("\nOperation cancelled by user. Exiting.")
    except Exception as e:
        con.print_error(f"An unexpected error occurred: {e}")
        # For debugging, you might want to print the full traceback
        # import traceback
        # traceback.print_exc()
    finally:
        con.print_info("Fedora AutoEnv Setup finished.")