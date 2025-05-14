# install.py
import logging
import sys
import os
import shutil
import pwd
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

from myrich import (
    console, print_header, print_info, print_error, print_success,
    print_with_emoji, print_warning, print_step
)
from system_preparation import run_system_preparation # Fase 1
from basic_configuration import run_basic_configuration # Fase 2
from terminal_enhancement import run_terminal_enhancement # Fase 4 (Fase 3 logic is embedded)
from nvidia_installation import run_nvidia_driver_installation # Fase 5

# --- Constants ---
LOG_FILE = "app.log"
REQUIREMENTS_FILE = "requirements.txt"
SCRIPT_DIR = Path(__file__).resolve().parent

STATUS_FILE_NAME = "setup_progress.json"
STATUS_FILE_PATH = SCRIPT_DIR / STATUS_FILE_NAME

STATUS_KEY_LAST_COMPLETED_PHASE = "last_completed_phase"

LAST_COMPLETED_PHASE = 0
MAX_INITIAL_PHASES = 5 # Phase 1, 2, 3 (AdvCfg+Deploy), 4 (Terminal), 5 (NVIDIA)


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


def get_real_user_home():
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user:
        try:
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except KeyError:
            home_path = Path(f"/home/{sudo_user}")
            if home_path.is_dir(): return home_path
            return Path.home() 
    return Path.home()

USER_HOME_DIR = get_real_user_home()


def check_python_requirements():
    print_info(f"Checking Python requirements from {REQUIREMENTS_FILE}...")
    try:
        with open(REQUIREMENTS_FILE, 'r') as f:
            requirements_list = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print_info(f"{REQUIREMENTS_FILE} not found. No Python dependencies to check for the script itself.")
        return True # No file, no problem for this check
    
    if not requirements_list:
        print_info(f"{REQUIREMENTS_FILE} is empty. No Python dependencies to check.")
        return True
        
    missing_packages = []
    for req_str in requirements_list:
        # Simplified check for this example
        package_name = req_str.split('==')[0].split('>=')[0].strip()
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

def deploy_user_configs():
    print_step("Config Deployment", "Deploying user configuration files .zshrc and .nanorc")
    if not USER_HOME_DIR or not USER_HOME_DIR.is_dir():
        print_error(f"User home '{USER_HOME_DIR}' invalid. Cannot deploy configs.")
        return False
    
    print_info(f"Target user home for configs: {USER_HOME_DIR}")
    all_copied = True
    configs_to_deploy = {
        SCRIPT_DIR / "zsh" / ".zshrc": USER_HOME_DIR / ".zshrc",
        SCRIPT_DIR / "nano" / ".nanorc": USER_HOME_DIR / ".nanorc"
    }

    for src, dest in configs_to_deploy.items():
        if src.exists():
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                print_success(f"Copied '{src.name}' to '{dest}'")
                if os.geteuid() == 0 and os.environ.get('SUDO_UID') and os.environ.get('SUDO_GID'):
                    try:
                        os.chown(dest, int(os.environ['SUDO_UID']), int(os.environ['SUDO_GID']))
                        print_info(f"Set ownership of '{dest.name}' to SUDO_USER.")
                    except Exception as e_chown:
                        print_warning(f"Could not chown '{dest}': {e_chown}")
            except Exception as e_copy:
                print_error(f"Failed to copy '{src.name}' to '{dest}': {e_copy}")
                all_copied = False
        else:
            print_warning(f"Source '{src}' not found. Skipping deployment of {src.name}.")
            all_copied = False
    return all_copied


def run_phase_three_advanced_config_and_finalize():
    print_header("Phase 3: Advanced Configuration & Finalization")
    phase_3_logic_successful = True
    print_info("Executing advanced configuration steps for Phase 3 (if any)...")
    # --- Placeholder for actual Phase 3 Advanced Configuration ---
    
    if not phase_3_logic_successful:
        print_error("Core logic for Phase 3 failed. Skipping config deployment.")
        return False

    print_info("Phase 3 core logic complete. Deploying user configs.")
    if deploy_user_configs():
        print_success("Phase 3 (Advanced Config & Finalize) complete!")
        update_last_completed_phase(3)
        return True
    else:
        print_error("Failed to deploy configs in Phase 3. Phase not fully complete.")
        return False

def display_menu():
    print_header("Main Menu - System Setup Utility")
    console.print(f"Target user: {os.environ.get('SUDO_USER', os.getlogin())} (Home: {USER_HOME_DIR})")
    if LAST_COMPLETED_PHASE >= MAX_INITIAL_PHASES:
        console.print("[green bold]INFO: Full Initial Setup (All Phases) was previously completed.[/]")
    console.print("Choose an option:")

    status_p1 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 1 else "[yellow]Pending[/yellow]"
    console.print(f"1. Phase 1: System Preparation - Status: {status_p1}")

    status_p2 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 2 else "[yellow]Pending[/yellow]"
    can_run_p2 = (LAST_COMPLETED_PHASE >= 1)
    p2_text = f"2. Phase 2: Basic Package Configuration - Status: {status_p2}"
    if not can_run_p2 and LAST_COMPLETED_PHASE < 2: p2_text += " (Requires Phase 1)"
    console.print(p2_text)

    status_p3 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 3 else "[yellow]Pending[/yellow]"
    can_run_p3 = (LAST_COMPLETED_PHASE >= 2)
    p3_text = f"3. Phase 3: Advanced Config & Finalize - Status: {status_p3}"
    if not can_run_p3 and LAST_COMPLETED_PHASE < 3: p3_text += " (Requires Phase 2)"
    console.print(p3_text)
    
    status_p4 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 4 else "[yellow]Pending[/yellow]"
    can_run_p4 = (LAST_COMPLETED_PHASE >= 3) 
    p4_text = f"4. Phase 4: Terminal Enhancement - Status: {status_p4}"
    if not can_run_p4 and LAST_COMPLETED_PHASE < 4: p4_text += " (Requires Phase 3)"
    console.print(p4_text)

    status_p5 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 5 else "[yellow]Pending[/yellow]"
    can_run_p5 = (LAST_COMPLETED_PHASE >= 1) # NVIDIA drivers depend on RPM Fusion from Phase 1
    p5_text = f"5. Phase 5: NVIDIA Driver Installation - Status: {status_p5}"
    if not can_run_p5 and LAST_COMPLETED_PHASE < 5: p5_text += " (Requires Phase 1)"
    console.print(p5_text)

    console.print("0. Exit")
    console.print("-" * 70)

    choices = ["0", "1"]
    if can_run_p2 or LAST_COMPLETED_PHASE >= 2: choices.append("2")
    if can_run_p3 or LAST_COMPLETED_PHASE >= 3: choices.append("3")
    if can_run_p4 or LAST_COMPLETED_PHASE >= 4: choices.append("4") 
    if can_run_p5 or LAST_COMPLETED_PHASE >= 5: choices.append("5")
    
    valid_choices = sorted(list(set(choices)))
    default_choice = "0"

    if "1" in valid_choices and LAST_COMPLETED_PHASE < 1: default_choice = "1"
    elif "2" in valid_choices and can_run_p2 and LAST_COMPLETED_PHASE < 2: default_choice = "2"
    elif "3" in valid_choices and can_run_p3 and LAST_COMPLETED_PHASE < 3: default_choice = "3"
    elif "4" in valid_choices and can_run_p4 and LAST_COMPLETED_PHASE < 4: default_choice = "4"
    elif "5" in valid_choices and can_run_p5 and LAST_COMPLETED_PHASE < 5: default_choice = "5"
    
    return Prompt.ask("Enter your choice", choices=valid_choices, default=default_choice)


def main():
    global LAST_COMPLETED_PHASE
    logging.info("Application started.")
    print_with_emoji("🚀", "Application started.", "highlight")

    if not check_python_requirements():
        sys.exit(1)
    load_last_completed_phase() 

    if os.geteuid() != 0:
        print_warning("Root privileges required for many phases.")
        if Prompt.ask("Not running as root. Continue with limited functionality (menu display, user-specific phases)?", choices=["y", "n"], default="n") != "y":
            sys.exit(0)
    
    while True:
        choice = display_menu()
        action_taken = False # To control the "Press Enter" prompt

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

        elif choice == '3':
            action_taken = True
            if LAST_COMPLETED_PHASE >= 3 and Prompt.ask("Phase 3 completed. Re-run?", default="n") == 'n': continue
            if LAST_COMPLETED_PHASE < 2: print_warning("Phase 2 must be completed first.")
            # Phase 3 might need root for some advanced config or chown in deploy_user_configs
            else:
                try:
                    if run_phase_three_advanced_config_and_finalize(): update_last_completed_phase(3)
                except Exception as e: logging.critical(f"Phase 3 Error: {e}", exc_info=True); print_error(f"P3 Err: {e}")

        elif choice == '4':
            action_taken = True
            if LAST_COMPLETED_PHASE >= 4 and Prompt.ask("Phase 4 completed. Re-run?", default="n") == 'n': continue
            if LAST_COMPLETED_PHASE < 3: print_warning("Phase 3 must be completed first.")
            # terminal_enhancement handles user context if script is root
            else:
                try:
                    if run_terminal_enhancement(): update_last_completed_phase(4)
                except Exception as e: logging.critical(f"Phase 4 Error: {e}", exc_info=True); print_error(f"P4 Err: {e}")
        
        elif choice == '5':
            action_taken = True
            if LAST_COMPLETED_PHASE >= 5 and Prompt.ask("Phase 5 completed. Re-run?", default="n") == 'n': continue
            if LAST_COMPLETED_PHASE < 1: print_warning("Phase 1 must be completed first (for RPM Fusion).")
            elif os.geteuid() != 0: print_error("Phase 5 requires root.")
            else:
                try:
                    # nvidia_installation itself might trigger a reboot, halting the script.
                    # If it completes without rebooting, then we update the phase.
                    if run_nvidia_driver_installation(): 
                        update_last_completed_phase(5)
                except Exception as e: logging.critical(f"Phase 5 Error: {e}", exc_info=True); print_error(f"P5 Err: {e}")

        elif choice == '0':
            print_success("Exiting application. Goodbye!")
            break
        else:
            print_warning("Invalid choice, please try again.")
            action_taken = True # Show "Press Enter" for invalid choice too

        if action_taken and choice != '0': # Don't prompt after exit
            Prompt.ask("\nPress Enter to return to menu...", default="", show_default=False)


    print_with_emoji("👋", "Application terminated.", "info")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user.[/warning]")
        logging.warning("Application interrupted by user (KeyboardInterrupt).")
    except Exception as e:
        escaped_error_message = escape_markup(str(e))
        console.print(f"\n[error]CRITICAL UNHANDLED ERROR: {escaped_error_message}[/error]")
        logging.critical(f"Unhandled critical exception in main: {e}", exc_info=True)
    finally:
        logging.info("Application finished or terminated.")
        sys.exit(0 if 'e' not in locals() else 1) # Exit 0 on normal exit, 1 on error