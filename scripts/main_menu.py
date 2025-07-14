# Fedora-AutoEnv-Setup/scripts/main_menu.py

import sys
from typing import Dict

from scripts import console_output as con
from scripts.config import PHASES, app_logger
from scripts.phase_manager import are_dependencies_met, mark_phase_complete


def display_main_menu(phase_status: Dict[str, bool]):
    """Displays the main menu of available phases."""
    con.print_step("Fedora AutoEnv Setup - Main Menu", char="*")
    con.print_info("Select a phase to run, or 'q' to quit.")
    con.print_rule()

    menu_items: Dict[str, str] = {} # Maps menu number (str) to phase_id (str)
    item_number = 1

    for phase_id, phase_info in PHASES.items():
        status_text = ""
        can_run = are_dependencies_met(phase_id, phase_status)

        if phase_status.get(phase_id, False):
            status_text = "[bold green](Completed)[/]"
        elif not can_run:
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

        if (can_run and not phase_status.get(phase_id, False)) or \
           (phase_status.get(phase_id, False) and can_run):
            menu_items[str(item_number)] = phase_id
        item_number += 1

    con.print_rule()
    con.console.print(" q. Quit")
    return menu_items

def main_menu_handler(app_config: Dict, phase_status: Dict[str, bool]):
    """Handles the main menu interaction loop."""
    while True:
        menu_options = display_main_menu(phase_status)
        valid_choices = list(menu_options.keys()) + ['q', 'Q']

        choice = con.ask_question("Enter your choice:", choices=valid_choices).lower()

        if choice == 'q':
            con.print_info("Exiting Fedora AutoEnv Setup. Bye!")
            break
        elif choice in menu_options:
            phase_to_run_id = menu_options[choice]
            phase_to_run_info = PHASES[phase_to_run_id]

            if not are_dependencies_met(phase_to_run_id, phase_status):
                con.print_warning(f"Cannot run '{phase_to_run_info['name']}'. Dependencies not met.")
                con.ask_question("Press Enter to continue...")
                continue

            if phase_status.get(phase_to_run_id, False):
                if not con.confirm_action(f"'{phase_to_run_info['name']}' is already marked as complete. Run again?", default=False):
                    continue

            con.print_info(f"\nStarting '{phase_to_run_info['name']}'...")

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
