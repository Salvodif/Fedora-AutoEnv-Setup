# install.py
import logging
import sys
import os
# shutil and pwd are not directly used here anymore after moving deploy_user_configs
from pathlib import Path
import json

from rich.text import Text
from rich.markup import escape as escape_markup

try:
    from importlib.metadata import DistributionNotFound, version as get_version
    PKG_RESOURCE_STYLE = False
except ImportError:
    import pkg_resources
    PKG_RESOURCE_STYLE = True

from rich.prompt import Prompt

from scripts.myrich import (
    console, print_header, print_info, print_error, print_success,
    print_with_emoji, print_warning # print_step is not directly used here anymore
)
from scripts.system_preparation import run_system_preparation # Phase 1
from scripts.basic_configuration import run_basic_configuration # Phase 2
# Import the main function from terminal_enhancement
from scripts.terminal_enhancement import run_terminal_enhancement # Phase 3
from scripts.gnome_configuration import run_gnome_configuration # Phase 4
from scripts.nvidia_installation import run_nvidia_driver_installation # Phase 5
from scripts.additional_packages import run_additional_packages_installation # Phase 6

# --- Constants ---
LOG_FILE = "app.log"
REQUIREMENTS_FILE = "requirements.txt"
SCRIPT_DIR = Path(__file__).resolve().parent # This SCRIPT_DIR is for install.py's context

STATUS_FILE_NAME = "setup_progress.json"
STATUS_FILE_PATH = SCRIPT_DIR / STATUS_FILE_NAME # Status file relative to install.py

STATUS_KEY_LAST_COMPLETED_PHASE = "last_completed_phase"

LAST_COMPLETED_PHASE = 0
MAX_INITIAL_PHASES = 6


# --- Logging Setup ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def load_last_completed_phase():
    global LAST_COMPLETED_PHASE
    if STATUS_FILE_PATH.exists():
        try:
            with open(STATUS_FILE_PATH, "r") as f:
                status_data = json.load(f)
                LAST_COMPLETED_PHASE = status_data.get(STATUS_KEY_LAST_COMPLETED_PHASE, 0)
            print_info(f"Loaded setup progress: Last completed phase = {LAST_COMPLETED_PHASE}")
        except (json.JSONDecodeError, TypeError) as e: 
            print_error(f"Error decoding {STATUS_FILE_NAME}: {e}. Resetting progress to 0.")
            LAST_COMPLETED_PHASE = 0
    else:
        print_info(f"{STATUS_FILE_NAME} not found. Initializing progress to 0.")
        LAST_COMPLETED_PHASE = 0
    save_last_completed_phase()


def save_last_completed_phase():
    try:
        with open(STATUS_FILE_PATH, "w") as f:
            json.dump({STATUS_KEY_LAST_COMPLETED_PHASE: LAST_COMPLETED_PHASE}, f, indent=4)
    except Exception as e:
        print_error(f"Failed to save setup progress: {e}")
        logging.error(f"Failed to save status file {STATUS_FILE_NAME}: {e}", exc_info=True)

def update_last_completed_phase(phase_number: int):
    global LAST_COMPLETED_PHASE
    if phase_number > LAST_COMPLETED_PHASE:
        LAST_COMPLETED_PHASE = phase_number
        save_last_completed_phase()
    elif phase_number < LAST_COMPLETED_PHASE:
        logging.warning(f"Attempted to downgrade last_completed_phase from {LAST_COMPLETED_PHASE} to {phase_number}.")

# get_real_user_home() and USER_HOME_DIR are no longer needed directly in install.py
# as deploy_user_configs is now in terminal_enhancement.py, which has its own logic for this.

def check_python_requirements():
    print_info(f"Checking Python requirements from {REQUIREMENTS_FILE}...")
    try:
        with open(REQUIREMENTS_FILE, 'r') as f:
            requirements_list = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print_info(f"{REQUIREMENTS_FILE} not found. No Python dependencies to check for the script itself.")
        return True 
    if not requirements_list:
        print_info(f"{REQUIREMENTS_FILE} is empty. No Python dependencies to check.")
        return True
    missing_packages = []
    for req_str in requirements_list:
        package_name = req_str.split('==')[0].split('>=')[0].split('<')[0].split('~=')[0].strip()
        try:
            if PKG_RESOURCE_STYLE:
                pkg_resources.get_distribution(package_name)
            else:
                get_version(package_name)
            print_success(f"  [green]✓[/green] {package_name} is installed.")
        except (DistributionNotFound if not PKG_RESOURCE_STYLE else pkg_resources.DistributionNotFound):
            missing_packages.append(package_name)
            print_error(f"  [red]✗[/red] {package_name} is NOT installed.")
        except Exception as e:
            print_error(f"  [red]✗[/red] Error checking {package_name}: {e}")
            missing_packages.append(package_name)
    if missing_packages:
        print_error("\nThe following Python packages (for the script) are missing:")
        for pkg in missing_packages: console.print(f"  - {pkg}")
        print_info(f"Please install them, e.g., using: pip install -r {REQUIREMENTS_FILE}")
        return False
    print_success("Python requirements check passed.")
    return True

# run_phase_three_terminal_and_configs() is now simplified as terminal_enhancement.py handles its sub-steps.
# We will call run_terminal_enhancement directly from main() for Phase 3.

def display_menu():
    print_header("Main Menu - System Setup Utility")
    # USER_HOME_DIR is not displayed here anymore as it's context-specific to terminal_enhancement
    current_user_for_display = os.environ.get('SUDO_USER', os.getlogin())
    console.print(f"Current effective user for operations (if applicable): {current_user_for_display}")
    if LAST_COMPLETED_PHASE >= MAX_INITIAL_PHASES:
        console.print("[green bold]INFO: Full Initial Setup (All Phases) was previously completed.[/]")
    console.print("Choose an option:")

    # Phase 1: System Preparation
    status_p1 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 1 else "[yellow]Pending[/yellow]"
    console.print(f"1. Phase 1: System Preparation - Status: {status_p1}")

    # Phase 2: Basic Configuration
    status_p2 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 2 else "[yellow]Pending[/yellow]"
    can_run_p2 = (LAST_COMPLETED_PHASE >= 1)
    p2_text = f"2. Phase 2: Basic Package Configuration - Status: {status_p2}"
    if not can_run_p2 and LAST_COMPLETED_PHASE < 2: p2_text += " (Requires Phase 1)"
    console.print(p2_text)

    # Phase 3: Terminal Enhancement (now includes user configs)
    status_p3 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 3 else "[yellow]Pending[/yellow]"
    can_run_p3 = (LAST_COMPLETED_PHASE >= 2)
    p3_text = f"3. Phase 3: Terminal Enhancement - Status: {status_p3}"
    if not can_run_p3 and LAST_COMPLETED_PHASE < 3: p3_text += " (Requires Phase 2)"
    console.print(p3_text)
    
    # Phase 4: GNOME Configuration
    status_p4 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 4 else "[yellow]Pending[/yellow]"
    can_run_p4 = (LAST_COMPLETED_PHASE >= 2) 
    p4_text = f"4. Phase 4: GNOME Configuration - Status: {status_p4}"
    if not can_run_p4 and LAST_COMPLETED_PHASE < 4: p4_text += " (Requires Phase 2)"
    console.print(p4_text)

    # Phase 5: NVIDIA Driver Installation
    status_p5 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 5 else "[yellow]Pending[/yellow]"
    can_run_p5 = (LAST_COMPLETED_PHASE >= 2) 
    p5_text = f"5. Phase 5: NVIDIA Driver Installation - Status: {status_p5}"
    if not can_run_p5 and LAST_COMPLETED_PHASE < 2: p5_text += " (Requires Phase 2)"
    elif not (LAST_COMPLETED_PHASE >=1) and LAST_COMPLETED_PHASE < 5 : p5_text += " (Requires Phase 1 for RPMFusion)"
    console.print(p5_text)

    # Phase 6: Additional Packages
    status_p6 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 6 else "[yellow]Pending[/yellow]"
    can_run_p6 = (LAST_COMPLETED_PHASE >= 2) # Requires basic setup from Phase 2
    p6_text = f"6. Phase 6: Additional Packages - Status: {status_p6}"
    if not can_run_p6 and LAST_COMPLETED_PHASE < 6: p6_text += " (Requires Phase 2)"
    console.print(p6_text)

    console.print("0. Exit")
    console.print("-" * 70)

    choices = ["0", "1"]
    if can_run_p2 or LAST_COMPLETED_PHASE >= 2: choices.append("2")
    if can_run_p3 or LAST_COMPLETED_PHASE >= 3: choices.append("3")
    if can_run_p4 or LAST_COMPLETED_PHASE >= 4: choices.append("4")
    if can_run_p5 or LAST_COMPLETED_PHASE >= 5: choices.append("5")
    if can_run_p6 or LAST_COMPLETED_PHASE >= 6: choices.append("6")

    valid_choices = sorted(list(set(choices)))
    default_choice = "0"

    if "1" in valid_choices and LAST_COMPLETED_PHASE < 1: default_choice = "1"
    elif "2" in valid_choices and can_run_p2 and LAST_COMPLETED_PHASE < 2: default_choice = "2"
    elif "3" in valid_choices and can_run_p3 and LAST_COMPLETED_PHASE < 3: default_choice = "3"
    elif "4" in valid_choices and can_run_p4 and LAST_COMPLETED_PHASE < 4 and LAST_COMPLETED_PHASE >=2 : default_choice = "4"
    elif "5" in valid_choices and can_run_p5 and LAST_COMPLETED_PHASE < 5 and LAST_COMPLETED_PHASE >=2 : default_choice = "5"
    elif "6" in valid_choices and can_run_p6 and LAST_COMPLETED_PHASE < 6 and LAST_COMPLETED_PHASE >=2 : default_choice = "6"

    if default_choice == "0" and LAST_COMPLETED_PHASE == 2 :
        if "3" in valid_choices and LAST_COMPLETED_PHASE <3: default_choice = "3"
        elif "4" in valid_choices and LAST_COMPLETED_PHASE <4: default_choice = "4"
        elif "5" in valid_choices and LAST_COMPLETED_PHASE <5: default_choice = "5"
        elif "6" in valid_choices and LAST_COMPLETED_PHASE <6: default_choice = "6"
    elif default_choice == "0" and LAST_COMPLETED_PHASE == 3:
        if "4" in valid_choices and LAST_COMPLETED_PHASE <4: default_choice = "4"
        elif "5" in valid_choices and LAST_COMPLETED_PHASE <5: default_choice = "5"
        elif "6" in valid_choices and LAST_COMPLETED_PHASE <6: default_choice = "6"
    elif default_choice == "0" and LAST_COMPLETED_PHASE == 4:
        if "5" in valid_choices and LAST_COMPLETED_PHASE <5: default_choice = "5"
        elif "6" in valid_choices and LAST_COMPLETED_PHASE <6: default_choice = "6"
    elif default_choice == "0" and LAST_COMPLETED_PHASE == 5:
        if "6" in valid_choices and LAST_COMPLETED_PHASE <6: default_choice = "6"

    return Prompt.ask("Enter your choice", choices=valid_choices, default=default_choice)

def main():
    global LAST_COMPLETED_PHASE
    logging.info("Application started.")
    print_with_emoji("🚀", "Application started.", "highlight")

    if not check_python_requirements():
        sys.exit(1)
    load_last_completed_phase() 

    if os.geteuid() != 0:
        print_warning("Root privileges may be required for many phases.")
        if Prompt.ask("Not running as root. Continue with limited functionality?", choices=["y", "n"], default="n") != "y":
            sys.exit(0)
    
    while True:
        choice = display_menu()
        action_taken = False 

        if choice == '1':
            action_taken = True
            if LAST_COMPLETED_PHASE >= 1 and Prompt.ask("Phase 1 completed. Re-run?", default="n") == 'n': continue
            if os.geteuid() != 0: print_error("Phase 1 requires root.")
            else:
                try:
                    if run_system_preparation(): update_last_completed_phase(1)
                except Exception as e: logging.critical(f"Phase 1 Error: {e}", exc_info=True); print_error(f"P1 Err: {e}")
        
        elif choice == '2':
            action_taken = True
            if LAST_COMPLETED_PHASE >= 2 and Prompt.ask("Phase 2 completed. Re-run?", default="n") == 'n': continue
            if LAST_COMPLETED_PHASE < 1: print_warning("Phase 1 must be completed first.")
            elif os.geteuid() != 0: print_error("Phase 2 requires root.")
            else:
                try:
                    if run_basic_configuration(): update_last_completed_phase(2)
                except Exception as e: logging.critical(f"Phase 2 Error: {e}", exc_info=True); print_error(f"P2 Err: {e}")

        elif choice == '3': # Phase 3: Terminal Enhancement (includes user configs now)
            action_taken = True
            if LAST_COMPLETED_PHASE >= 3 and Prompt.ask("Phase 3 completed. Re-run?", default="n") == 'n': continue
            if LAST_COMPLETED_PHASE < 2: print_warning("Phase 2 must be completed first.")
            else:
                try:
                    # run_terminal_enhancement now handles its own sub-steps including config deployment
                    # It will return True if successful.
                    if run_terminal_enhancement(): 
                        update_last_completed_phase(3)
                except Exception as e: logging.critical(f"Phase 3 Error: {e}", exc_info=True); print_error(f"P3 Err: {e}")

        elif choice == '4':
            action_taken = True
            if LAST_COMPLETED_PHASE >= 4 and Prompt.ask("Phase 4 completed. Re-run?", default="n") == 'n': continue
            if LAST_COMPLETED_PHASE < 2:
                print_warning("Phase 2 must be completed before GNOME Configuration (Phase 4).")
            # Root check for package installs inside run_gnome_configuration is implicit,
            # but gsettings/extensions also need user context handling which is done inside.
            # Script running as root with SUDO_USER is the ideal scenario for this phase.
            else:
                try:
                    if run_gnome_configuration(): update_last_completed_phase(4)
                except Exception as e: logging.critical(f"Phase 4 Error: {e}", exc_info=True); print_error(f"P4 Err: {e}")

        elif choice == '5':
            action_taken = True
            if LAST_COMPLETED_PHASE >= 5 and Prompt.ask("Phase 5 completed. Re-run?", default="n") == 'n': continue
            if LAST_COMPLETED_PHASE < 1: 
                print_warning("Phase 1 (System Prep for RPM Fusion) must be completed first.")
            elif LAST_COMPLETED_PHASE < 2: 
                 print_warning("Phase 2 (Basic Config) must be completed first.")
            elif os.geteuid() != 0: print_error("Phase 5 (NVIDIA) requires root.")
            else:
                try:
                    if run_nvidia_driver_installation(): 
                        update_last_completed_phase(5)
                except Exception as e: logging.critical(f"Phase 5 Error: {e}", exc_info=True); print_error(f"P5 Err: {e}")

        elif choice == '6': # Phase 6: Additional Packages
            action_taken = True
            if LAST_COMPLETED_PHASE >= 6 and Prompt.ask("Phase 6 completed. Re-run?", default="n") == 'n': continue
            if LAST_COMPLETED_PHASE < 2:
                print_warning("Phase 2 (Basic Config) must be completed before Additional Packages (Phase 6).")
            elif os.geteuid() != 0: 
                print_error("Phase 6 (Additional Packages) requires root privileges for `dnf` and `flatpak` system installs.")
            else:
                try:
                    if run_additional_packages_installation(): 
                        update_last_completed_phase(6)
                except Exception as e: logging.critical(f"Phase 6 Error: {e}", exc_info=True); print_error(f"P6 Err: {e}")

        elif choice == '0':
            print_success("Exiting application. Goodbye!")
            break
        else:
            print_warning("Invalid choice, please try again.")
            action_taken = True 

        if action_taken and choice != '0': 
            Prompt.ask("\nPress Enter to return to menu...", default="", show_default=False)

    print_with_emoji("👋", "Application terminated.", "info")

if __name__ == "__main__":
    exit_code = 0
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user.[/warning]")
        logging.warning("Application interrupted by user (KeyboardInterrupt).")
    except Exception as e:
        escaped_error_message = escape_markup(str(e))
        console.print(f"\n[error]CRITICAL UNHANDLED ERROR: {escaped_error_message}[/error]")
        logging.critical(f"Unhandled critical exception in main: {e}", exc_info=True)
        exit_code = 1
    finally:
        logging.info("Application finished or terminated.")
        sys.exit(exit_code)