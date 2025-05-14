# install.py
import logging
import sys
import os
import shutil # For copying files
import pwd    # For getting user's home directory even with sudo
from pathlib import Path # For easier path manipulation

import pkg_resources

from rich.prompt import Prompt

from myrich import console, print_header, print_info, print_error, print_success, print_with_emoji
from system_preparation import run_system_preparation
from basic_configuration import run_basic_configuration
# utils.py is used by system_preparation and basic_configuration

# --- Constants ---
LOG_FILE = "app.log"
REQUIREMENTS_FILE = "requirements.txt"
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_SOURCE_DIR_ZSH = SCRIPT_DIR / "zsh"
CONFIG_SOURCE_DIR_NANO = SCRIPT_DIR / "nano"
MARKER_FILE_NAME = ".initial_setup_complete_marker"
MARKER_FILE_PATH = SCRIPT_DIR / MARKER_FILE_NAME # Marker in script's directory

# --- Global State Flags (derived from marker file or runtime) ---
# These will be checked/set during runtime
INITIAL_SETUP_COMPLETE = False # True if marker file exists and valid
SYSTEM_PREP_SUCCESS_THIS_SESSION = False
BASIC_CONFIG_SUCCESS_THIS_SESSION = False


# --- Logging Setup ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.WARNING,
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
            print_warning(f"Could not find user {sudo_user} via pwd. Falling back.")
            # Fallback if user not in local passwd (e.g., LDAP without nss_ldap)
            # This is less reliable but a common pattern.
            home_path = Path(f"/home/{sudo_user}")
            if home_path.exists():
                return home_path
            else: # Last resort, might be /root if script directly run as root
                return Path.home()

    else: # Not running with sudo, or SUDO_USER not set
        return Path.home()

USER_HOME_DIR = get_real_user_home()


def check_marker_file():
    """Checks for the marker file to determine if initial setup was completed."""
    global INITIAL_SETUP_COMPLETE
    if MARKER_FILE_PATH.exists():
        print_info(f"Marker file '{MARKER_FILE_NAME}' found. Initial setup previously completed.")
        INITIAL_SETUP_COMPLETE = True
        # Optionally, read content from marker if it stored more state
    else:
        INITIAL_SETUP_COMPLETE = False

def create_marker_file():
    """Creates a marker file to signify successful completion of Phase 1."""
    global INITIAL_SETUP_COMPLETE
    try:
        MARKER_FILE_PATH.touch()
        print_success(f"Marker file '{MARKER_FILE_NAME}' created. Initial setup complete.")
        INITIAL_SETUP_COMPLETE = True
        logging.info("Initial setup marker file created.")
        return True
    except Exception as e:
        print_error(f"Failed to create marker file '{MARKER_FILE_NAME}': {e}")
        logging.error(f"Failed to create marker file: {e}", exc_info=True)
        return False

def check_python_requirements():
    """Checks if Python packages listed in requirements.txt are installed."""
    print_info(f"Checking Python requirements from {REQUIREMENTS_FILE}...")
    # ... (implementation from previous step - no changes needed here)
    try:
        with open(REQUIREMENTS_FILE, 'r') as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print_error(f"{REQUIREMENTS_FILE} not found. Cannot check Python dependencies.")
        logging.error(f"{REQUIREMENTS_FILE} not found.")
        return False

    missing_packages = []
    installed_ok_count = 0
    for req_str in requirements:
        try:
            req = pkg_resources.Requirement.parse(req_str)
            pkg_resources.get_distribution(req.name)
            print_success(f"  [green]✓[/green] {req.name} is installed.")
            installed_ok_count +=1
        except pkg_resources.DistributionNotFound:
            missing_packages.append(req.name)
            print_error(f"  [red]✗[/red] {req.name} is NOT installed.")
        except pkg_resources.VersionConflict as e:
            missing_packages.append(f"{req.name} (version conflict: {e})")
            print_error(f"  [red]✗[/red] {req.name} has a version conflict: {e.report()}")
        except Exception as e:
            print_error(f"  [red]✗[/red] Error checking {req_str}: {e}")
            missing_packages.append(req_str)

    if missing_packages:
        print_error("\nThe following Python packages are missing or have issues:")
        for pkg in missing_packages:
            console.print(f"  - {pkg}")
        print_info(f"Please install them, e.g., using: pip install -r {REQUIREMENTS_FILE}")
        logging.error(f"Missing Python requirements: {', '.join(missing_packages)}")
        return False
    
    if installed_ok_count > 0 :
        print_success("All Python requirements are met.")
    else:
        print_info("No Python requirements to check (or requirements file is empty).")
    return True


def deploy_user_configs():
    """Copies .zshrc and .nanorc to the user's home directory."""
    print_step(0, "Deploying user configuration files") # A "sub-step"
    
    if not USER_HOME_DIR or not USER_HOME_DIR.is_dir():
        print_error(f"User home directory '{USER_HOME_DIR}' not found or invalid. Cannot deploy configs.")
        logging.error(f"User home directory {USER_HOME_DIR} invalid for config deployment.")
        return False

    print_info(f"Target user home directory for configs: {USER_HOME_DIR}")
    
    all_copied = True
    
    # Config for .zshrc
    zshrc_source = CONFIG_SOURCE_DIR_ZSH / ".zshrc"
    zshrc_dest = USER_HOME_DIR / ".zshrc"
    
    if zshrc_source.exists():
        try:
            shutil.copy2(zshrc_source, zshrc_dest)
            print_success(f"Copied '{zshrc_source.name}' to '{zshrc_dest}'")
            # Set ownership if running as root and SUDO_USER is known
            sudo_uid = os.environ.get('SUDO_UID')
            sudo_gid = os.environ.get('SUDO_GID')
            if sudo_uid and sudo_gid and os.geteuid() == 0:
                try:
                    os.chown(zshrc_dest, int(sudo_uid), int(sudo_gid))
                    print_info(f"Set ownership of '{zshrc_dest.name}' to user {os.environ.get('SUDO_USER')}")
                except Exception as e_chown:
                    print_warning(f"Could not chown {zshrc_dest}: {e_chown}")
                    logging.warning(f"chown failed for {zshrc_dest}: {e_chown}")
        except Exception as e:
            print_error(f"Failed to copy '{zshrc_source.name}' to '{zshrc_dest}': {e}")
            logging.error(f"Failed to copy {zshrc_source.name}: {e}", exc_info=True)
            all_copied = False
    else:
        print_warning(f"Source file '{zshrc_source}' not found. Skipping .zshrc deployment.")
        logging.warning(f"Source .zshrc not found at {zshrc_source}")
        all_copied = False # Or True if you consider skipping non-fatal

    # Config for .nanorc
    nanorc_source = CONFIG_SOURCE_DIR_NANO / ".nanorc"
    nanorc_dest = USER_HOME_DIR / ".nanorc"

    if nanorc_source.exists():
        try:
            shutil.copy2(nanorc_source, nanorc_dest)
            print_success(f"Copied '{nanorc_source.name}' to '{nanorc_dest}'")
            sudo_uid = os.environ.get('SUDO_UID')
            sudo_gid = os.environ.get('SUDO_GID')
            if sudo_uid and sudo_gid and os.geteuid() == 0:
                try:
                    os.chown(nanorc_dest, int(sudo_uid), int(sudo_gid))
                    print_info(f"Set ownership of '{nanorc_dest.name}' to user {os.environ.get('SUDO_USER')}")
                except Exception as e_chown:
                    print_warning(f"Could not chown {nanorc_dest}: {e_chown}")
                    logging.warning(f"chown failed for {nanorc_dest}: {e_chown}")
        except Exception as e:
            print_error(f"Failed to copy '{nanorc_source.name}' to '{nanorc_dest}': {e}")
            logging.error(f"Failed to copy {nanorc_source.name}: {e}", exc_info=True)
            all_copied = False
    else:
        print_warning(f"Source file '{nanorc_source}' not found. Skipping .nanorc deployment.")
        logging.warning(f"Source .nanorc not found at {nanorc_source}")
        all_copied = False # Or True

    if all_copied:
        print_success("User configuration files deployed successfully.")
    else:
        print_warning("Some user configuration files could not be deployed. Check messages above.")
    return all_copied


def display_menu():
    """Displays the main menu and handles user choice."""
    global INITIAL_SETUP_COMPLETE, SYSTEM_PREP_SUCCESS_THIS_SESSION, BASIC_CONFIG_SUCCESS_THIS_SESSION

    print_header("Main Menu - System Setup Utility")
    console.print(f"Target user for configs: {os.environ.get('SUDO_USER', os.getlogin())} (Home: {USER_HOME_DIR})")
    console.print("Choose an option:")

    # Option 1: System Preparation
    sys_prep_status_text = ""
    if INITIAL_SETUP_COMPLETE:
        sys_prep_status_text = "[green]✓ Completed (Phase 1)[/green]"
    elif SYSTEM_PREP_SUCCESS_THIS_SESSION:
        sys_prep_status_text = "[cyan]✓ Done this session[/cyan]"
    else:
        sys_prep_status_text = "[yellow]Pending[/yellow]"
    console.print(f"1. System Preparation (DNF, Update, Repos) - Status: {sys_prep_status_text}")

    # Option 2: Basic Package Configuration
    basic_config_status_text = ""
    if INITIAL_SETUP_COMPLETE: # If phase 1 is done, this part is also implicitly done
        basic_config_status_text = "[green]✓ Completed (Phase 1)[/green]"
    elif BASIC_CONFIG_SUCCESS_THIS_SESSION:
        basic_config_status_text = "[cyan]✓ Done this session[/cyan]"
    else:
        basic_config_status_text = "[yellow]Pending[/yellow]"
    
    can_run_basic_config = SYSTEM_PREP_SUCCESS_THIS_SESSION or INITIAL_SETUP_COMPLETE
    basic_config_option_display = f"2. Basic Package Configuration (Core tools, Zsh) - Status: {basic_config_status_text}"
    if not can_run_basic_config and not BASIC_CONFIG_SUCCESS_THIS_SESSION: # Show requirement if not met and not already done
         basic_config_option_display += " (Requires System Preparation first)"
    console.print(basic_config_option_display)

    # Option 3: Phase Two Configuration (Advanced)
    if INITIAL_SETUP_COMPLETE:
        console.print("3. Advanced Configuration (Phase Two) [Placeholder]")
    else:
        console.print("[dim]3. Advanced Configuration (Phase Two) (Requires Phase 1 completion)[/dim]")


    console.print("0. Exit")
    console.print("-" * 50)

    choices = ["0", "1"]
    if can_run_basic_config or BASIC_CONFIG_SUCCESS_THIS_SESSION : # Can run or has run basic config
        choices.append("2")
    if INITIAL_SETUP_COMPLETE: # Phase 1 done, enable phase 2
        choices.append("3")
    
    # Filter out duplicates and sort for consistent order if logic above adds them multiple times
    valid_choices = sorted(list(set(choices)))
    choice = Prompt.ask("Enter your choice", choices=valid_choices, default="0")
    return choice

def run_phase_two_configuration():
    """Placeholder for Phase Two configuration steps."""
    print_header("Phase Two: Advanced Configuration")
    print_info("This is where you would add logic for advanced setup.")
    print_info("For example: configuring specific applications, dotfiles management beyond initial copy, etc.")
    # Add your phase two logic here
    print_success("Phase Two placeholder executed.")


def main():
    """Main function to run the application."""
    global INITIAL_SETUP_COMPLETE, SYSTEM_PREP_SUCCESS_THIS_SESSION, BASIC_CONFIG_SUCCESS_THIS_SESSION

    logging.info("Application started.")
    print_with_emoji("🚀", "Application started.", "highlight")

    if not check_python_requirements():
        print_error("Critical Python dependencies are missing. Please install them and restart.")
        sys.exit(1)

    check_marker_file() # Check if initial setup was done in a previous run

    if os.geteuid() != 0:
        print_warning("This application performs system-wide changes.")
        print_warning("It's highly recommended to run it with 'sudo python3 install.py'")
        if not Prompt.ask("Continue without sudo? (Not Recommended, most operations will fail)", choices=["y", "n"], default="n") == "y":
            sys.exit(0)
    
    while True:
        choice = display_menu()

        if choice == '1': # System Preparation
            if INITIAL_SETUP_COMPLETE:
                print_info("System Preparation (Phase 1) was already completed in a previous session.")
                if Prompt.ask("Do you want to re-run System Preparation?", choices=["y","n"], default="n") == 'n':
                    Prompt.ask("\nPress Enter to return to the main menu...")
                    continue
            try:
                if run_system_preparation():
                    SYSTEM_PREP_SUCCESS_THIS_SESSION = True
                else:
                    SYSTEM_PREP_SUCCESS_THIS_SESSION = False # Explicitly set
                    print_warning("System preparation did not complete successfully this session.")
            except Exception as e:
                SYSTEM_PREP_SUCCESS_THIS_SESSION = False
                print_error(f"An unexpected error occurred during system preparation: {e}")
                logging.critical(f"Unhandled exception in run_system_preparation: {e}", exc_info=True)
            
            # Check if ready to deploy configs and create marker
            if SYSTEM_PREP_SUCCESS_THIS_SESSION and BASIC_CONFIG_SUCCESS_THIS_SESSION and not INITIAL_SETUP_COMPLETE:
                if deploy_user_configs():
                    create_marker_file() # This will set INITIAL_SETUP_COMPLETE to True
            Prompt.ask("\nPress Enter to return to the main menu...")
        
        elif choice == '2': # Basic Package Configuration
            if INITIAL_SETUP_COMPLETE:
                print_info("Basic Package Configuration (Phase 1) was already completed.")
                if Prompt.ask("Do you want to re-run Basic Package Configuration?", choices=["y","n"], default="n") == 'n':
                    Prompt.ask("\nPress Enter to return to the main menu...")
                    continue
            
            if not SYSTEM_PREP_SUCCESS_THIS_SESSION and not INITIAL_SETUP_COMPLETE:
                print_warning("Please complete 'System Preparation' (Option 1) successfully in this session first.")
            else:
                try:
                    if run_basic_configuration():
                        BASIC_CONFIG_SUCCESS_THIS_SESSION = True
                    else:
                        BASIC_CONFIG_SUCCESS_THIS_SESSION = False # Explicitly set
                        print_warning("Basic package configuration did not complete successfully this session.")
                except Exception as e:
                    BASIC_CONFIG_SUCCESS_THIS_SESSION = False
                    print_error(f"An unexpected error occurred during basic configuration: {e}")
                    logging.critical(f"Unhandled exception in run_basic_configuration: {e}", exc_info=True)

            # Check if ready to deploy configs and create marker
            if SYSTEM_PREP_SUCCESS_THIS_SESSION and BASIC_CONFIG_SUCCESS_THIS_SESSION and not INITIAL_SETUP_COMPLETE:
                if deploy_user_configs():
                    create_marker_file() # This will set INITIAL_SETUP_COMPLETE to True
            Prompt.ask("\nPress Enter to return to the main menu...")

        elif choice == '3': # Advanced Configuration (Phase Two)
            if INITIAL_SETUP_COMPLETE:
                run_phase_two_configuration()
            else:
                print_warning("Phase 1 (System Preparation & Basic Config) must be completed first.")
            Prompt.ask("\nPress Enter to return to the main menu...")
        
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