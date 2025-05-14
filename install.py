# install.py
import logging
import sys
import os
import shutil
import pwd
from pathlib import Path

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
# utils.py is used by system_preparation and basic_configuration

# --- Constants ---
LOG_FILE = "app.log"
REQUIREMENTS_FILE = "requirements.txt"
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_SOURCE_DIR_ZSH = SCRIPT_DIR / "zsh"
CONFIG_SOURCE_DIR_NANO = SCRIPT_DIR / "nano"
# Questo marker ora indica il completamento di Fase 1 + Fase 2 + Fase 3 + copia config
MARKER_FILE_NAME = ".full_setup_complete_marker" # Rinominato per chiarezza
MARKER_FILE_PATH = SCRIPT_DIR / MARKER_FILE_NAME

# --- Global State Flags ---
PHASE_1_SYSTEM_PREP_SUCCESS_SESSION = False
PHASE_2_BASIC_CONFIG_SUCCESS_SESSION = False
PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION = False # Nuovo flag per la Fase 3


# --- Logging Setup ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def get_real_user_home():
    # ... (nessuna modifica qui, la funzione rimane la stessa) ...
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


def check_full_setup_marker_exists():
    """Checks if the full setup marker file exists."""
    if MARKER_FILE_PATH.exists():
        print_info(f"Marker file '{MARKER_FILE_NAME}' found. Full setup (Phases 1, 2, 3 + configs) previously completed.")
        return True
    return False

def create_full_setup_marker_file():
    """Creates a marker file to signify successful completion of ALL setup phases including configs."""
    try:
        MARKER_FILE_PATH.touch()
        print_success(f"Full setup marker file '{MARKER_FILE_NAME}' created. All setup phases and config deployment complete.")
        logging.info(f"Full setup marker file created at {MARKER_FILE_PATH}")
        return True
    except Exception as e:
        print_error(f"Failed to create full setup marker file '{MARKER_FILE_NAME}': {e}")
        logging.error(f"Failed to create full setup marker file: {e}", exc_info=True)
        return False

def check_python_requirements():
    # ... (nessuna modifica qui, la funzione rimane la stessa) ...
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
    # ... (nessuna modifica qui, la funzione rimane la stessa) ...
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


def display_menu(full_setup_already_done: bool):
    """Displays the main menu and handles user choice."""
    global PHASE_1_SYSTEM_PREP_SUCCESS_SESSION, PHASE_2_BASIC_CONFIG_SUCCESS_SESSION, PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION

    print_header("Main Menu - System Setup Utility")
    console.print(f"Target user for configs: {os.environ.get('SUDO_USER', os.getlogin())} (Home: {USER_HOME_DIR})")
    if full_setup_already_done:
        console.print("[green bold]INFO: Full Setup (Phases 1, 2, 3 + Configs) was previously completed.[/green]")
        console.print("You can choose to re-run phases if needed.")

    console.print("Choose an option:")

    # --- Option 1: System Preparation (Phase 1) ---
    status_p1 = "[yellow]Pending[/yellow]"
    if full_setup_already_done or PHASE_1_SYSTEM_PREP_SUCCESS_SESSION:
        status_p1 = "[green]✓ Done[/green]" if full_setup_already_done else "[cyan]✓ Done this session[/cyan]"
    console.print(f"1. Phase 1: System Preparation - Status: {status_p1}")

    # --- Option 2: Basic Package Configuration (Phase 2) ---
    status_p2 = "[yellow]Pending[/yellow]"
    if full_setup_already_done or PHASE_2_BASIC_CONFIG_SUCCESS_SESSION:
        status_p2 = "[green]✓ Done[/green]" if full_setup_already_done else "[cyan]✓ Done this session[/cyan]"
    
    can_run_p2 = PHASE_1_SYSTEM_PREP_SUCCESS_SESSION or full_setup_already_done
    p2_text = f"2. Phase 2: Basic Package Configuration - Status: {status_p2}"
    if not can_run_p2 and not PHASE_2_BASIC_CONFIG_SUCCESS_SESSION and not full_setup_already_done:
        p2_text += " (Requires Phase 1 completion)"
    console.print(p2_text)

    # --- Option 3: Advanced Configuration (Phase 3) & Finalize ---
    status_p3 = "[yellow]Pending[/yellow]"
    if full_setup_already_done or PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION:
        status_p3 = "[green]✓ Done[/green]" if full_setup_already_done else "[cyan]✓ Done this session[/cyan]"

    can_run_p3 = (PHASE_1_SYSTEM_PREP_SUCCESS_SESSION and PHASE_2_BASIC_CONFIG_SUCCESS_SESSION) or full_setup_already_done
    p3_text = f"3. Phase 3: Advanced Configuration & Finalize Setup - Status: {status_p3}"
    if not can_run_p3 and not PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION and not full_setup_already_done:
        p3_text += " (Requires Phase 1 & 2 completion)"
    console.print(p3_text)
    
    console.print("0. Exit")
    console.print("-" * 70) # Aumentato per il testo più lungo

    choices = ["0", "1"]
    if can_run_p2: choices.append("2")
    if can_run_p3: choices.append("3")
    
    valid_choices = sorted(list(set(choices)))
    default_choice = "0"
    if "1" in valid_choices and not (PHASE_1_SYSTEM_PREP_SUCCESS_SESSION or full_setup_already_done) : default_choice = "1"
    elif "2" in valid_choices and can_run_p2 and not (PHASE_2_BASIC_CONFIG_SUCCESS_SESSION or full_setup_already_done): default_choice = "2"
    elif "3" in valid_choices and can_run_p3 and not (PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION or full_setup_already_done): default_choice = "3"

    choice = Prompt.ask("Enter your choice", choices=valid_choices, default=default_choice)
    return choice


def run_phase_three_configuration_and_finalize():
    """
    Placeholder for Phase Three (Advanced) configuration steps.
    If successful, it then deploys user configs and creates the final marker.
    Returns True if Phase 3 AND finalization steps were successful, False otherwise.
    """
    global PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION # Modifichiamo questo flag

    print_header("Phase 3: Advanced Configuration & Finalization")
    
    # --- Inserisci qui la logica effettiva della Fase 3 ---
    print_info("Executing advanced configuration steps for Phase 3...")
    # Esempio:
    # success_step1 = run_command(["some_advanced_command"])
    # success_step2 = configure_something_else()
    # if not (success_step1 and success_step2):
    #     print_error("Some advanced configuration steps in Phase 3 failed.")
    #     PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION = False
    #     return False
    
    print_success("Placeholder for Phase 3 advanced configuration steps completed successfully.")
    # --- Fine della logica effettiva della Fase 3 ---

    PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION = True # Assume successo se arriviamo qui

    # Ora, dopo il successo della Fase 3, procedi con la copia dei file e il marker finale
    print_info("Phase 3 completed. Proceeding to deploy user configs and finalize setup.")
    if deploy_user_configs():
        if create_full_setup_marker_file():
            print_success("Full setup including Phase 3 and config deployment is now complete!")
            return True
        else:
            print_error("Failed to create the full setup completion marker file. The setup might be incomplete for future runs.")
            # Anche se il marker fallisce, la fase 3 e la copia dei config potrebbero essere andate a buon fine
            # Ma per lo stato generale, consideriamo questo un fallimento del "finalize"
            return False # Fallimento della finalizzazione
    else:
        print_error("Failed to deploy user configuration files after Phase 3. The setup is not fully complete.")
        return False # Fallimento della copia dei config


def main():
    """Main function to run the application."""
    global PHASE_1_SYSTEM_PREP_SUCCESS_SESSION, PHASE_2_BASIC_CONFIG_SUCCESS_SESSION, PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION

    logging.info("Application started.")
    print_with_emoji("🚀", "Application started.", "highlight")

    if not check_python_requirements():
        print_error("Critical Python dependencies are missing. Please install them and restart.")
        sys.exit(1)

    full_setup_already_done = check_full_setup_marker_exists()

    if os.geteuid() != 0:
        print_warning("This application performs system-wide changes and requires root privileges.")
        if not Prompt.ask("The script is not running as root (sudo). Most operations will fail. Continue for menu display only?", choices=["y", "n"], default="n") == "y":
            print_info("Exiting. Please run with 'sudo python3 install.py'")
            sys.exit(0)
    
    while True:
        # Aggiorna lo stato per il menu in base ai flag di sessione se il setup completo non è già fatto
        # Questo permette al menu di riflettere i progressi *all'interno* di una sessione.
        current_display_status_is_complete = full_setup_already_done or \
                                             (PHASE_1_SYSTEM_PREP_SUCCESS_SESSION and \
                                              PHASE_2_BASIC_CONFIG_SUCCESS_SESSION and \
                                              PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION)

        choice = display_menu(current_display_status_is_complete)


        if choice == '1': # Phase 1: System Preparation
            if full_setup_already_done:
                print_info("Phase 1 was already part of a completed full setup.")
                if Prompt.ask("Do you want to re-run Phase 1?", choices=["y","n"], default="n") == 'n':
                    Prompt.ask("\nPress Enter to return to the main menu...", default="")
                    continue
            
            try:
                if run_system_preparation():
                    PHASE_1_SYSTEM_PREP_SUCCESS_SESSION = True
                else:
                    PHASE_1_SYSTEM_PREP_SUCCESS_SESSION = False # Resetta in caso di fallimento
            except Exception as e:
                PHASE_1_SYSTEM_PREP_SUCCESS_SESSION = False
                print_error(f"An unexpected error occurred during Phase 1: {e}")
                logging.critical(f"Unhandled exception in run_system_preparation: {e}", exc_info=True)
            Prompt.ask("\nPress Enter to return to the main menu...", default="")
        
        elif choice == '2': # Phase 2: Basic Package Configuration
            if full_setup_already_done:
                print_info("Phase 2 was already part of a completed full setup.")
                if Prompt.ask("Do you want to re-run Phase 2?", choices=["y","n"], default="n") == 'n':
                    Prompt.ask("\nPress Enter to return to the main menu...", default="")
                    continue

            can_run_p2_now = PHASE_1_SYSTEM_PREP_SUCCESS_SESSION or full_setup_already_done
            if not can_run_p2_now:
                print_warning("Phase 1 (System Preparation) must be completed successfully first in this session.")
            else:
                try:
                    if run_basic_configuration():
                        PHASE_2_BASIC_CONFIG_SUCCESS_SESSION = True
                    else:
                        PHASE_2_BASIC_CONFIG_SUCCESS_SESSION = False # Resetta
                except Exception as e:
                    PHASE_2_BASIC_CONFIG_SUCCESS_SESSION = False
                    print_error(f"An unexpected error occurred during Phase 2: {e}")
                    logging.critical(f"Unhandled exception in run_basic_configuration: {e}", exc_info=True)
            Prompt.ask("\nPress Enter to return to the main menu...", default="")

        elif choice == '3': # Phase 3: Advanced Configuration & Finalize
            if full_setup_already_done:
                print_info("Full setup (including Phase 3 and configs) was already completed.")
                if Prompt.ask("Do you want to re-run Phase 3 and config deployment?", choices=["y","n"], default="n") == 'n':
                    Prompt.ask("\nPress Enter to return to the main menu...", default="")
                    continue
            
            can_run_p3_now = (PHASE_1_SYSTEM_PREP_SUCCESS_SESSION and PHASE_2_BASIC_CONFIG_SUCCESS_SESSION) or full_setup_already_done
            if not can_run_p3_now:
                print_warning("Phase 1 and Phase 2 must be completed successfully first in this session.")
            else:
                try:
                    if run_phase_three_configuration_and_finalize():
                        # Il successo di PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION è gestito all'interno della funzione
                        # E il marker file aggiorna lo stato 'full_setup_already_done'
                        full_setup_already_done = check_full_setup_marker_exists() # Ricarica lo stato del marker
                        if full_setup_already_done:
                             print_success("Phase 3 and finalization completed successfully!")
                        else:
                            print_warning("Phase 3 and finalization steps had issues. Marker not created.")
                    else:
                        # PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION sarà False se la funzione ritorna False
                        PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION = False # Assicura che sia False
                        print_error("Phase 3 and/or finalization steps failed.")
                except Exception as e:
                    PHASE_3_ADVANCED_CONFIG_SUCCESS_SESSION = False
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
        console.print(f"\n[error]A critical unhandled error occurred in main: {e}[/error]")
        logging.critical(f"Unhandled critical exception in main: {e}", exc_info=True)
        sys.exit(1)