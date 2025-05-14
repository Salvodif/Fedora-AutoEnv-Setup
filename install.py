# install.py
import logging
import sys
import os
import shutil
import pwd
from pathlib import Path

# Gestione importlib.metadata vs pkg_resources (per Python 3.8+)
try:
    from importlib.metadata import DistributionNotFound, version as get_version
    # Per parsare stringhe di requisiti complesse, 'packaging' è utile
    # from packaging.requirements import Requirement 
    PKG_RESOURCE_STYLE = False
except ImportError: # Fallback per Python < 3.8 o se importlib.metadata non è completo
    import pkg_resources
    PKG_RESOURCE_STYLE = True


from rich.prompt import Prompt

from myrich import (
    console, print_header, print_info, print_error, print_success,
    print_with_emoji, print_warning, print_step
)
from system_preparation import run_system_preparation # Questa è la Fase 1
from basic_configuration import run_basic_configuration # Questa è la Fase 2
# utils.py è usato da system_preparation e basic_configuration

# --- Constants ---
LOG_FILE = "app.log"
REQUIREMENTS_FILE = "requirements.txt"
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_SOURCE_DIR_ZSH = SCRIPT_DIR / "zsh"
CONFIG_SOURCE_DIR_NANO = SCRIPT_DIR / "nano"
MARKER_FILE_NAME = ".initial_setup_complete_marker" # Ora indica il completamento di Fase 1 + Fase 2 + copia config
MARKER_FILE_PATH = SCRIPT_DIR / MARKER_FILE_NAME

# --- Global State Flags ---
# INITIAL_SETUP_COMPLETE è determinato dal marker file
PHASE_1_SYSTEM_PREP_SUCCESS_SESSION = False # Successo di system_preparation in questa sessione
PHASE_2_BASIC_CONFIG_SUCCESS_SESSION = False # Successo di basic_configuration in questa sessione


# --- Logging Setup ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO, # Abbassato a INFO per più dettagli nel log
    format='%(asctime)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def get_real_user_home():
    """Gets the home directory of the user who invoked sudo."""
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
                # Se anche /home/utente non esiste, e siamo root, .home() darà /root
                # Se non siamo root (improbabile per questo script), darà la home dell'utente corrente.
                print_error(f"Fallback home directory /home/{sudo_user} not found. Using current user's home.")
                return Path.home() 
    else:
        # Non eseguito con sudo o SUDO_USER non è impostato.
        # Se siamo root (os.geteuid() == 0), Path.home() sarà /root.
        # Se non siamo root, sarà la home dell'utente che esegue lo script.
        current_user_login = os.getlogin()
        print_info(f"Not running with SUDO_USER. Target home determined by os.getlogin(): {current_user_login} -> {Path.home()}")
        return Path.home()

USER_HOME_DIR = get_real_user_home() # Determina la home directory una volta all'avvio


def check_marker_file_exists():
    """Checks if the main setup marker file exists."""
    if MARKER_FILE_PATH.exists():
        print_info(f"Marker file '{MARKER_FILE_NAME}' found. Full initial setup (Phase 1 & 2 + configs) previously completed.")
        return True
    return False

def create_main_marker_file():
    """Creates a marker file to signify successful completion of ALL initial setup phases."""
    try:
        MARKER_FILE_PATH.touch()
        print_success(f"Main marker file '{MARKER_FILE_NAME}' created. All initial setup phases complete.")
        logging.info(f"Main setup marker file created at {MARKER_FILE_PATH}")
        return True
    except Exception as e:
        print_error(f"Failed to create main marker file '{MARKER_FILE_NAME}': {e}")
        logging.error(f"Failed to create main marker file: {e}", exc_info=True)
        return False

def check_python_requirements():
    """Checks if Python packages listed in requirements.txt are installed."""
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
        else: # importlib.metadata
            package_name = req_str.split('==')[0].split('>=')[0].split('<=')[0].split('!=')[0].split('~=')[0].strip()
            try:
                get_version(package_name)
                print_success(f"  [green]✓[/green] {package_name} is installed (importlib.metadata).")
                installed_ok_count += 1
            except DistributionNotFound: # Corretto da PackageNotFoundError a DistributionNotFound per importlib.metadata
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
    
    if installed_ok_count > 0 or not requirements_list: # OK se non ci sono requisiti o se tutti sono soddisfatti
        print_success("Python requirements check passed.")
    return True


def deploy_user_configs():
    """Copies .zshrc and .nanorc to the user's home directory."""
    print_step("Final", "Deploying user configuration files") # Rinominato step
    
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
                # Crea la directory di destinazione se non esiste (per .config/app/file.conf per esempio)
                # In questo caso, dest_path è direttamente nella home, quindi .parent è USER_HOME_DIR
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                shutil.copy2(source_file, dest_path) # copy2 preserva i metadati
                print_success(f"Copied '{source_file.name}' to '{dest_path}'")
                
                # Imposta la proprietà corretta se stiamo eseguendo come root
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
            all_copied_successfully = False # Considerare non trovare un file sorgente come un fallimento

    if all_copied_successfully:
        print_success("All user configuration files deployed successfully.")
    else:
        print_warning("Some user configuration files could not be deployed. Check messages above.")
    return all_copied_successfully


def display_menu(initial_setup_already_done: bool):
    """Displays the main menu and handles user choice."""
    global PHASE_1_SYSTEM_PREP_SUCCESS_SESSION, PHASE_2_BASIC_CONFIG_SUCCESS_SESSION

    print_header("Main Menu - System Setup Utility")
    console.print(f"Target user for configs: {os.environ.get('SUDO_USER', os.getlogin())} (Home: {USER_HOME_DIR})")
    if initial_setup_already_done:
        console.print("[green bold]INFO: Initial setup (Phases 1 & 2 + configs) was previously completed.[/green]")
        console.print("You can choose to re-run phases or proceed to advanced options if available.")

    console.print("Choose an option:")

    # --- Option 1: System Preparation (Phase 1) ---
    status_p1 = "[yellow]Pending[/yellow]"
    if initial_setup_already_done or PHASE_1_SYSTEM_PREP_SUCCESS_SESSION:
        status_p1 = "[green]✓ Done[/green]" if initial_setup_already_done else "[cyan]✓ Done this session[/cyan]"
    console.print(f"1. Phase 1: System Preparation (DNF, Update, Repos) - Status: {status_p1}")

    # --- Option 2: Basic Package Configuration (Phase 2) ---
    status_p2 = "[yellow]Pending[/yellow]"
    if initial_setup_already_done or PHASE_2_BASIC_CONFIG_SUCCESS_SESSION: # Se il setup completo è fatto, anche P2 è fatta
        status_p2 = "[green]✓ Done[/green]" if initial_setup_already_done else "[cyan]✓ Done this session[/cyan]"
    
    can_run_p2 = PHASE_1_SYSTEM_PREP_SUCCESS_SESSION or initial_setup_already_done
    p2_text = f"2. Phase 2: Basic Package Configuration (Core tools, Zsh) - Status: {status_p2}"
    if not can_run_p2 and not PHASE_2_BASIC_CONFIG_SUCCESS_SESSION and not initial_setup_already_done:
        p2_text += " (Requires Phase 1 completion first)"
    console.print(p2_text)

    # --- Option 3: Advanced/Next Steps (Placeholder) ---
    if initial_setup_already_done:
        console.print("3. Advanced Configuration / Next Steps [Placeholder]")
    else:
        console.print("[dim]3. Advanced Configuration / Next Steps (Requires full initial setup)[/dim]")
    
    console.print("0. Exit")
    console.print("-" * 60)

    choices = ["0", "1"]
    if can_run_p2 or PHASE_2_BASIC_CONFIG_SUCCESS_SESSION or initial_setup_already_done:
        choices.append("2")
    if initial_setup_already_done:
        choices.append("3")
    
    valid_choices = sorted(list(set(choices)))
    default_choice = "0"
    if "1" in valid_choices and not (PHASE_1_SYSTEM_PREP_SUCCESS_SESSION or initial_setup_already_done) : default_choice = "1"
    elif "2" in valid_choices and not (PHASE_2_BASIC_CONFIG_SUCCESS_SESSION or initial_setup_already_done) and can_run_p2: default_choice = "2"


    choice = Prompt.ask("Enter your choice", choices=valid_choices, default=default_choice)
    return choice


def run_phase_three_configuration():
    """Placeholder for Phase Three (Advanced) configuration steps."""
    print_header("Phase Three: Advanced Configuration / Next Steps")
    print_info("This is where you would add logic for further advanced setup or application configurations.")
    print_success("Phase Three placeholder executed.")


def main():
    """Main function to run the application."""
    global PHASE_1_SYSTEM_PREP_SUCCESS_SESSION, PHASE_2_BASIC_CONFIG_SUCCESS_SESSION

    logging.info("Application started.")
    print_with_emoji("🚀", "Application started.", "highlight")

    if not check_python_requirements():
        print_error("Critical Python dependencies are missing. Please install them and restart.")
        sys.exit(1)

    # Controlla se l'intero setup iniziale (P1+P2+configs) è già stato fatto
    initial_setup_already_done = check_marker_file_exists()

    if os.geteuid() != 0:
        print_warning("This application performs system-wide changes and requires root privileges.")
        if not Prompt.ask("The script is not running as root (sudo). Most operations will fail. Continue for menu display only?", choices=["y", "n"], default="n") == "y":
            print_info("Exiting. Please run with 'sudo python3 install.py'")
            sys.exit(0)
    
    while True:
        choice = display_menu(initial_setup_already_done)

        if choice == '1': # Phase 1: System Preparation
            if initial_setup_already_done:
                print_info("Phase 1 (System Preparation) was already part of a completed initial setup.")
                if Prompt.ask("Do you want to re-run Phase 1?", choices=["y","n"], default="n") == 'n':
                    Prompt.ask("\nPress Enter to return to the main menu...", default="")
                    continue
            
            try:
                if run_system_preparation(): # run_system_preparation dovrebbe ritornare True/False
                    PHASE_1_SYSTEM_PREP_SUCCESS_SESSION = True
                    print_success("Phase 1 (System Preparation) completed successfully this session.")
                else:
                    PHASE_1_SYSTEM_PREP_SUCCESS_SESSION = False
                    print_error("Phase 1 (System Preparation) failed or had issues this session.")
            except Exception as e:
                PHASE_1_SYSTEM_PREP_SUCCESS_SESSION = False
                print_error(f"An unexpected error occurred during Phase 1: {e}")
                logging.critical(f"Unhandled exception in run_system_preparation: {e}", exc_info=True)
            Prompt.ask("\nPress Enter to return to the main menu...", default="")
        
        elif choice == '2': # Phase 2: Basic Package Configuration
            if initial_setup_already_done:
                print_info("Phase 2 (Basic Configuration) was already part of a completed initial setup.")
                if Prompt.ask("Do you want to re-run Phase 2?", choices=["y","n"], default="n") == 'n':
                    Prompt.ask("\nPress Enter to return to the main menu...", default="")
                    continue

            can_proceed_with_p2 = PHASE_1_SYSTEM_PREP_SUCCESS_SESSION or initial_setup_already_done
            if not can_proceed_with_p2:
                print_warning("Phase 1 (System Preparation) must be completed successfully first in this session.")
            else:
                try:
                    if run_basic_configuration(): # run_basic_configuration dovrebbe ritornare True/False
                        PHASE_2_BASIC_CONFIG_SUCCESS_SESSION = True
                        print_success("Phase 2 (Basic Package Configuration) completed successfully this session.")
                        
                        # --- NUOVA LOGICA ---
                        # Se P1 e P2 sono successi E il setup completo non è ancora marcato
                        # Allora copia i file di config e crea il marker principale
                        if (PHASE_1_SYSTEM_PREP_SUCCESS_SESSION or initial_setup_already_done) and \
                           PHASE_2_BASIC_CONFIG_SUCCESS_SESSION and \
                           not initial_setup_already_done: # Evita di ricopiare e rimarcare se già fatto
                            
                            print_info("Both Phase 1 and Phase 2 are complete. Proceeding to deploy user configs.")
                            if deploy_user_configs():
                                if create_main_marker_file():
                                    initial_setup_already_done = True # Aggiorna lo stato per il menu
                                    print_success("All initial setup steps (Phase 1, Phase 2, Configs) are now complete!")
                                else:
                                    print_error("Failed to create the main completion marker file. The setup might be incomplete for future runs.")
                            else:
                                print_error("Failed to deploy user configuration files. The setup is not fully complete.")
                        elif initial_setup_already_done:
                             print_info("User configs were deployed as part of a previous full setup.")

                    else: # run_basic_configuration ha fallito
                        PHASE_2_BASIC_CONFIG_SUCCESS_SESSION = False
                        print_error("Phase 2 (Basic Package Configuration) failed or had issues this session.")
                except Exception as e:
                    PHASE_2_BASIC_CONFIG_SUCCESS_SESSION = False
                    print_error(f"An unexpected error occurred during Phase 2: {e}")
                    logging.critical(f"Unhandled exception in run_basic_configuration: {e}", exc_info=True)
            Prompt.ask("\nPress Enter to return to the main menu...", default="")

        elif choice == '3': # Phase Three / Advanced
            if initial_setup_already_done:
                run_phase_three_configuration()
            else:
                print_warning("Full initial setup (Phase 1 & 2 + Configs) must be completed first.")
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