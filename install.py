import logging
import sys
import os
import shutil
import pwd
from pathlib import Path
import json

from rich.text import Text

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

# --- Constants ---
LOG_FILE = "app.log"
REQUIREMENTS_FILE = "requirements.txt"
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_SOURCE_DIR_ZSH = SCRIPT_DIR / "zsh"
CONFIG_SOURCE_DIR_NANO = SCRIPT_DIR / "nano"

STATUS_FILE_NAME = "setup_progress.json"
STATUS_FILE_PATH = SCRIPT_DIR / STATUS_FILE_NAME

STATUS_KEY_LAST_COMPLETED_PHASE = "last_completed_phase"

LAST_COMPLETED_PHASE = 0


# --- Logging Setup ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def load_last_completed_phase():
    """Carica l'ultima fase completata dal file JSON. Se non esiste, restituisce 0."""
    global LAST_COMPLETED_PHASE
    if STATUS_FILE_PATH.exists():
        try:
            with open(STATUS_FILE_PATH, "r") as f:
                status_data = json.load(f)
                LAST_COMPLETED_PHASE = status_data.get(STATUS_KEY_LAST_COMPLETED_PHASE, 0)
            print_info(f"Loaded setup progress from {STATUS_FILE_NAME}: Last completed phase = {LAST_COMPLETED_PHASE}")
        except (json.JSONDecodeError, TypeError) as e: # TypeError se il file è vuoto o malformato
            print_error(f"Error decoding {STATUS_FILE_NAME} or key missing: {e}. Resetting progress to 0.")
            logging.error(f"Error in {STATUS_FILE_NAME} (or key missing): {e}. Resetting to 0.", exc_info=True)
            LAST_COMPLETED_PHASE = 0
            save_last_completed_phase()
        except Exception as e:
            print_error(f"Unexpected error loading {STATUS_FILE_NAME}: {e}. Resetting progress to 0.")
            logging.error(f"Unexpected error loading status file {STATUS_FILE_NAME}: {e}", exc_info=True)
            LAST_COMPLETED_PHASE = 0
    else:
        print_info(f"{STATUS_FILE_NAME} not found. Initializing progress: Last completed phase = 0.")
        LAST_COMPLETED_PHASE = 0
        save_last_completed_phase()

def save_last_completed_phase():
    """Salva l'ultima fase completata corrente nel file JSON."""
    try:
        with open(STATUS_FILE_PATH, "w") as f:
            json.dump({STATUS_KEY_LAST_COMPLETED_PHASE: LAST_COMPLETED_PHASE}, f, indent=4)
        print_info(f"Saved setup progress to {STATUS_FILE_NAME}: Last completed phase = {LAST_COMPLETED_PHASE}")
    except Exception as e:
        print_error(f"Failed to save setup progress to {STATUS_FILE_NAME}: {e}")
        logging.error(f"Failed to save status file {STATUS_FILE_NAME}: {e}", exc_info=True)

def update_last_completed_phase(phase_number: int):
    """Aggiorna e salva l'ultima fase completata."""
    global LAST_COMPLETED_PHASE
    if phase_number > LAST_COMPLETED_PHASE:
        LAST_COMPLETED_PHASE = phase_number
        save_last_completed_phase()
    elif phase_number < LAST_COMPLETED_PHASE:
        print_warning(f"Attempted to set last completed phase to {phase_number}, but current is {LAST_COMPLETED_PHASE}. No downgrade.")
        logging.warning(f"Attempted to downgrade last_completed_phase from {LAST_COMPLETED_PHASE} to {phase_number}.")


def get_real_user_home():
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user:
        try:
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except KeyError:
            print_warning(f"Could not find user {sudo_user} via pwd. Falling back to /home/{sudo_user}.")
            home_path = Path(f"/home/{sudo_user}")
            if home_path.is_dir():
                return home_path
            else:
                print_error(f"Fallback home directory /home/{sudo_user} not found. Using current user's home.")
                return Path.home() 
    else:
        current_user_login = os.getlogin()
        print_info(f"Not running with SUDO_USER. Target home determined by os.getlogin(): {current_user_login} -> {Path.home()}")
        return Path.home()

USER_HOME_DIR = get_real_user_home()


def check_python_requirements():
    print_info(f"Checking Python requirements from {REQUIREMENTS_FILE}...")
    try:
        with open(REQUIREMENTS_FILE, 'r') as f:
            requirements_list = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print_error(f"{REQUIREMENTS_FILE} not found. Cannot check Python dependencies.")
        logging.error(f"{REQUIREMENTS_FILE} not found.")
        return False
    missing_packages = []
    installed_ok_count = 0
    for req_str in requirements_list:
        if PKG_RESOURCE_STYLE:
            try:
                req_parsed = pkg_resources.Requirement.parse(req_str)
                pkg_resources.get_distribution(req_parsed.name)
                print_success(f"  [green]✓[/green] {req_parsed.name} is installed (pkg_resources).")
                installed_ok_count += 1
            except pkg_resources.DistributionNotFound:
                missing_packages.append(req_parsed.name)
                print_error(f"  [red]✗[/red] {req_parsed.name} is NOT installed (pkg_resources).")
            except pkg_resources.VersionConflict as e:
                missing_packages.append(f"{req_parsed.name} (version conflict: {e})")
                print_error(f"  [red]✗[/red] {req_parsed.name} version conflict: {e.report()} (pkg_resources).")
            except Exception as e:
                print_error(f"  [red]✗[/red] Error checking {req_str} (pkg_resources): {e}")
                missing_packages.append(req_str)
        else: 
            package_name = req_str.split('==')[0].split('>=')[0].split('<=')[0].split('!=')[0].split('~=')[0].strip()
            try:
                get_version(package_name)
                print_success(f"  [green]✓[/green] {package_name} is installed (importlib.metadata).")
                installed_ok_count += 1
            except DistributionNotFound: 
                missing_packages.append(package_name)
                print_error(f"  [red]✗[/red] {package_name} is NOT installed (importlib.metadata).")
            except Exception as e:
                print_error(f"  [red]✗[/red] Error checking {package_name} (importlib.metadata): {e}")
                missing_packages.append(package_name)
    if missing_packages:
        print_error("\nThe following Python packages are missing or have issues:")
        for pkg in missing_packages:
            console.print(f"  - {pkg}")
        print_info(f"Please install them, e.g., using: pip install -r {REQUIREMENTS_FILE}")
        logging.error(f"Missing Python requirements: {', '.join(missing_packages)}")
        return False
    if installed_ok_count > 0 or not requirements_list: 
        print_success("Python requirements check passed.")
    return True

def deploy_user_configs():
    print_step("Final Config Deployment", "Deploying user configuration files .zshrc and .nanorc")
    if not USER_HOME_DIR or not USER_HOME_DIR.is_dir():
        print_error(f"User home directory '{USER_HOME_DIR}' not found or invalid. Cannot deploy configs.")
        logging.error(f"User home directory {USER_HOME_DIR} invalid for config deployment.")
        return False
    print_info(f"Target user home directory for configs: {USER_HOME_DIR}")
    all_copied_successfully = True
    configs_to_deploy = {
        "zsh/.zshrc": USER_HOME_DIR / ".zshrc",
        "nano/.nanorc": USER_HOME_DIR / ".nanorc"
    }
    for src_rel_path, dest_path in configs_to_deploy.items():
        source_file = SCRIPT_DIR / src_rel_path
        if source_file.exists():
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, dest_path)
                print_success(f"Copied '{source_file.name}' to '{dest_path}'")
                sudo_uid_str = os.environ.get('SUDO_UID')
                sudo_gid_str = os.environ.get('SUDO_GID')
                if sudo_uid_str and sudo_gid_str and os.geteuid() == 0:
                    try:
                        sudo_uid = int(sudo_uid_str)
                        sudo_gid = int(sudo_gid_str)
                        os.chown(dest_path, sudo_uid, sudo_gid)
                        print_info(f"Set ownership of '{dest_path.name}' to user ID {sudo_uid}, group ID {sudo_gid}.")
                    except ValueError:
                        print_warning(f"SUDO_UID ('{sudo_uid_str}') or SUDO_GID ('{sudo_gid_str}') is not a valid integer. Cannot chown.")
                        logging.warning(f"Invalid SUDO_UID/GID for chown: {sudo_uid_str}/{sudo_gid_str}")
                    except Exception as e_chown:
                        print_warning(f"Could not chown '{dest_path}': {e_chown}")
                        logging.warning(f"chown failed for {dest_path}: {e_chown}")
            except Exception as e_copy:
                print_error(f"Failed to copy '{source_file.name}' to '{dest_path}': {e_copy}")
                logging.error(f"Failed to copy {source_file.name} to {dest_path}: {e_copy}", exc_info=True)
                all_copied_successfully = False
        else:
            print_warning(f"Source file '{source_file}' not found. Skipping deployment of {source_file.name}.")
            logging.warning(f"Source file not found: {source_file}")
            all_copied_successfully = False
    if all_copied_successfully:
        print_success("All user configuration files (.zshrc, .nanorc) deployed successfully.")
    else:
        print_warning("Some user configuration files (.zshrc, .nanorc) could not be deployed.")
    return all_copied_successfully


def display_menu():
    """Displays the main menu based on LAST_COMPLETED_PHASE."""
    print_header("Main Menu - System Setup Utility")
    console.print(f"Target user for configs: {os.environ.get('SUDO_USER', os.getlogin())} (Home: {USER_HOME_DIR})")

    MAX_INITIAL_PHASES = 3
    is_full_initial_setup_done = (LAST_COMPLETED_PHASE >= MAX_INITIAL_PHASES)

    if is_full_initial_setup_done:
        console.print("[green bold]INFO: Full Initial Setup (All Phases) was previously completed.[/green]")
        console.print("You can choose to re-run phases if needed.")

    console.print("Choose an option:")

    # --- Opzione 1: Fase 1 ---
    status_p1 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 1 else "[yellow]Pending[/yellow]"
    console.print(f"1. Phase 1: System Preparation - Status: {status_p1}")

    # --- Opzione 2: Fase 2 ---
    status_p2 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 2 else "[yellow]Pending[/yellow]"
    can_run_p2 = (LAST_COMPLETED_PHASE >= 1)
    p2_text = f"2. Phase 2: Basic Package Configuration - Status: {status_p2}"
    if not can_run_p2 and LAST_COMPLETED_PHASE < 2:
        p2_text += " (Requires Phase 1 completion)"
    console.print(p2_text)

    # --- Opzione 3: Fase 3 & Finalize ---
    status_p3 = "[green]✓ Done[/green]" if LAST_COMPLETED_PHASE >= 3 else "[yellow]Pending[/yellow]"
    can_run_p3 = (LAST_COMPLETED_PHASE >= 2)
    p3_text = f"3. Phase 3: Advanced Configuration & Finalize Setup - Status: {status_p3}"
    if not can_run_p3 and LAST_COMPLETED_PHASE < 3:
        p3_text += " (Requires Phase 1 & 2 completion)"
    console.print(p3_text)
    
    console.print("0. Exit")
    console.print("-" * 70)

    choices = ["0", "1"]
    if can_run_p2 or LAST_COMPLETED_PHASE >= 2: choices.append("2")
    if can_run_p3 or LAST_COMPLETED_PHASE >= 3: choices.append("3")
    
    valid_choices = sorted(list(set(choices)))
    default_choice = "0"

    if "1" in valid_choices and LAST_COMPLETED_PHASE < 1: default_choice = "1"
    elif "2" in valid_choices and can_run_p2 and LAST_COMPLETED_PHASE < 2: default_choice = "2"
    elif "3" in valid_choices and can_run_p3 and LAST_COMPLETED_PHASE < 3: default_choice = "3"
    
    choice = Prompt.ask("Enter your choice", choices=valid_choices, default=default_choice)
    return choice

def run_phase_three_configuration_and_finalize():
    """
    Runs Phase 3 logic, then deploys configs.
    Updates LAST_COMPLETED_PHASE to 3 if all steps are successful.
    Returns True if Phase 3 logic AND config deployment are successful.
    """
    print_header("Phase 3: Advanced Configuration & Finalization")
    
    phase_3_logic_successful = False
    
    print_info("Executing advanced configuration steps for Phase 3...")
    print_success("Placeholder for Phase 3 advanced configuration steps completed successfully.")
    phase_3_logic_successful = True

    if not phase_3_logic_successful:
        print_error("Core logic for Phase 3 failed. Skipping config deployment and finalization.")
        return False

    print_info("Phase 3 core logic completed. Proceeding to deploy user configs.")
    if deploy_user_configs():
        print_success("Phase 3, including config deployment, is now complete!")
        update_last_completed_phase(3)
        return True
    else:
        print_error("Failed to deploy user configuration files after Phase 3. Phase 3 is not fully complete.")
        return False


def main():
    """Main function to run the application."""
    global LAST_COMPLETED_PHASE

    logging.info("Application started.")
    print_with_emoji("🚀", "Application started.", "highlight")

    if not check_python_requirements():
        print_error("Critical Python dependencies are missing. Please install them and restart.")
        sys.exit(1)

    load_last_completed_phase() # Carica lo stato di avanzamento all'avvio

    if os.geteuid() != 0:
        print_warning("This application performs system-wide changes and requires root privileges.")
        if not Prompt.ask("The script is not running as root (sudo). Most operations will fail. Continue for menu display only?", choices=["y", "n"], default="n") == "y":
            print_info("Exiting. Please run with 'sudo python3 install.py'")
            sys.exit(0)
    
    while True:
        choice = display_menu()

        if choice == '1': # Phase 1: System Preparation
            if LAST_COMPLETED_PHASE >= 1:
                print_info("Phase 1 was previously completed.")
                if Prompt.ask("Do you want to re-run Phase 1?", choices=["y","n"], default="n") == 'n':
                    Prompt.ask("\nPress Enter to return to the main menu...", default="")
                    continue

            try:
                if run_system_preparation():
                    update_last_completed_phase(1)
                # else: non decrementiamo LAST_COMPLETED_PHASE in caso di fallimento di una riesecuzione
            except Exception as e:
                print_error(f"An unexpected error occurred during Phase 1: {e}")
                logging.critical(f"Unhandled exception in run_system_preparation: {e}", exc_info=True)
            Prompt.ask("\nPress Enter to return to the main menu...", default="")
        
        elif choice == '2': # Phase 2: Basic Package Configuration
            if LAST_COMPLETED_PHASE >= 2:
                print_info("Phase 2 was previously completed.")
                if Prompt.ask("Do you want to re-run Phase 2?", choices=["y","n"], default="n") == 'n':
                    Prompt.ask("\nPress Enter to return to the main menu...", default="")
                    continue

            if LAST_COMPLETED_PHASE < 1:
                print_warning("Phase 1 (System Preparation) must be completed first.")
            else:
                try:
                    if run_basic_configuration():
                        update_last_completed_phase(2)
                except Exception as e:
                    print_error(f"An unexpected error occurred during Phase 2: {e}")
                    logging.critical(f"Unhandled exception in run_basic_configuration: {e}", exc_info=True)
            Prompt.ask("\nPress Enter to return to the main menu...", default="")

        elif choice == '3': # Phase 3: Advanced Configuration & Finalize
            if LAST_COMPLETED_PHASE >= 3:
                print_info("Phase 3 (Advanced Config & Finalize) was previously completed.")
                if Prompt.ask("Do you want to re-run Phase 3 and config deployment?", choices=["y","n"], default="n") == 'n':
                    Prompt.ask("\nPress Enter to return to the main menu...", default="")
                    continue

            if LAST_COMPLETED_PHASE < 2:
                print_warning("Phase 1 and Phase 2 must be completed first.")
            else:
                try:
                    run_phase_three_configuration_and_finalize()
                except Exception as e:
                    print_error(f"An unexpected error occurred during Phase 3 or finalization: {e}")
                    logging.critical(f"Unhandled exception in Phase 3/Finalize: {e}", exc_info=True)
            Prompt.ask("\nPress Enter to return to the main menu...", default="")
        
        elif choice == '0': # Exit
            print_success("Exiting application. Goodbye!")
            logging.info("Application finished.")
            break
        else:
            print_warning("Invalid choice, please try again.")

    print_with_emoji("👋", "Application terminated.", "info")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[warning]Operation cancelled by user.[/warning]")
        logging.warning("Application interrupted by user (KeyboardInterrupt).")
        sys.exit(0)
    except Exception as e:
        escaped_error_message = Text.escape(str(e))
        console.print(f"\n[error]A critical unhandled error occurred in main: {escaped_error_message}[/error]")
        logging.critical(f"Unhandled critical exception in main: {e}", exc_info=True)
        sys.exit(1)