# basic_configuration.py
import logging
import os
import shutil
from pathlib import Path # Aggiunto per la gestione dei percorsi

from scripts.myrich import (
    console, print_info, print_warning, print_error, print_success,
    print_step, print_with_emoji, print_header
)
from scripts.utils import run_command

# List of packages to be installed
PACKAGES_TO_INSTALL = [
    "git", "curl", "cargo", "zsh", "python3", "python3-pip",
    "stow", "dnf-plugins-core", "powerline-fonts", "btop",
    "bat", "fzf", "google-chrome-stable", "steam", "timeshift",
    "vlc"
]

# Google Chrome repo details
CHROME_REPO_URL = "https://dl.google.com/linux/chrome/rpm/stable/x86_64"
CHROME_REPO_NAME = "google-chrome" # Usato per il nome del file .repo
GOOGLE_CHROME_REPO_FILE_PATH = Path("/etc/yum.repos.d/") / f"{CHROME_REPO_NAME}.repo"


def _check_root_privileges():
    """Checks for root privileges."""
    if os.geteuid() != 0:
        print_error("This operation requires superuser (root) privileges.")
        logging.error("Attempted basic configuration without root privileges.")
        return False
    return True

def _add_google_chrome_repo_manual():
    """Adds the Google Chrome repository by creating a .repo file directly."""
    print_info("Attempting to add Google Chrome repository by creating .repo file manually.")

    repo_content = f"""[{CHROME_REPO_NAME}]
name={CHROME_REPO_NAME}
baseurl={CHROME_REPO_URL}
enabled=1
gpgcheck=1
gpgkey=https://dl.google.com/linux/linux_signing_key.pub
"""
    try:
        if GOOGLE_CHROME_REPO_FILE_PATH.exists():
            existing_content = GOOGLE_CHROME_REPO_FILE_PATH.read_text()
            if CHROME_REPO_URL in existing_content and "enabled=1" in existing_content.replace(" ", ""):
                print_info(f"Google Chrome repository file '{GOOGLE_CHROME_REPO_FILE_PATH}' already exists and seems correctly configured.")
                return True

        print_info(f"Creating repository file: {GOOGLE_CHROME_REPO_FILE_PATH}")
        GOOGLE_CHROME_REPO_FILE_PATH.parent.mkdir(parents=True, exist_ok=True) # Assicura che /etc/yum.repos.d esista
        with open(GOOGLE_CHROME_REPO_FILE_PATH, "w") as f:
            f.write(repo_content)
        
        print_success(f"Google Chrome repository file '{GOOGLE_CHROME_REPO_FILE_PATH}' created/updated successfully.")
        
        dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
        print_info(f"Running '{dnf_cmd} makecache --repo={CHROME_REPO_NAME}' to refresh repository information.")
        run_command([dnf_cmd, "makecache", f"--repo={CHROME_REPO_NAME}"], check=False, capture_output=True) # check=False, output silenziato a meno di errori

        return True
    except IOError as e:
        print_error(f"Failed to write Google Chrome repository file '{GOOGLE_CHROME_REPO_FILE_PATH}': {e}")
        logging.error(f"IOError writing {GOOGLE_CHROME_REPO_FILE_PATH}: {e}", exc_info=True)
        return False
    except Exception as e:
        print_error(f"An unexpected error occurred while creating Google Chrome repository file: {e}")
        logging.error(f"Unexpected error creating .repo file: {e}", exc_info=True)
        return False

def _add_google_chrome_repo():
    """Adds the Google Chrome repository."""
    print_step(1.1, "Configuring Google Chrome repository") # Sotto-passo di install_packages

    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
    if not shutil.which(dnf_cmd):
        print_error(f"`{dnf_cmd}` command not found. Cannot proceed with repository management.")
        logging.error(f"`{dnf_cmd}` command not found during Chrome repo setup.")
        return False
    
    use_manual_method = False
    config_manager_path = shutil.which(f"{dnf_cmd}-config-manager") # Verifica se config-manager è disponibile per il dnf corrente

    # Preferisci config-manager se dnf-plugins-core è installato e il comando è il dnf tradizionale
    if dnf_cmd == "dnf" and "dnf-plugins-core" in PACKAGES_TO_INSTALL and config_manager_path:
        print_info(f"Attempting to add repo using '{dnf_cmd} config-manager --add-repo'...")
        cmd_add_repo_config_manager = [dnf_cmd, "config-manager", "--add-repo", CHROME_REPO_URL]
        
        stdout, stderr, returncode = run_command(cmd_add_repo_config_manager, capture_output=True, check=False)
        
        if returncode == 0:
            print_success("Google Chrome repository added successfully using config-manager.")
            return True
        else:
            print_warning(f"'{' '.join(cmd_add_repo_config_manager)}' failed (code: {returncode}). Stderr: {stderr.strip() if stderr else 'N/A'}")
            print_info("Falling back to manual .repo file creation method for Google Chrome.")
            use_manual_method = True
    else:
        if dnf_cmd == "dnf" and "dnf-plugins-core" in PACKAGES_TO_INSTALL and not config_manager_path:
            print_info(f"'{dnf_cmd}-config-manager' not found, even if dnf-plugins-core is in install list. Proceeding with manual method.")
        print_info("Using manual .repo file creation method for Google Chrome.")
        use_manual_method = True

    if use_manual_method:
        return _add_google_chrome_repo_manual()
    
    return False


def install_packages():
    """Installs the specified packages using DNF (or DNF5 if available)."""
    print_step(1, "Installing core packages")
    
    dnf_command = "dnf5" if shutil.which("dnf5") else "dnf"
    if not shutil.which(dnf_command):
        print_error(f"`{dnf_command}` command not found. Cannot install packages.")
        logging.error(f"`{dnf_command}` not found for package installation.")
        return False

    all_good = True
    # Lavora su una copia per poterla modificare
    packages_to_install_this_run = list(PACKAGES_TO_INSTALL)

    # Installa dnf-plugins-core per primo SE è nella lista E stiamo usando 'dnf' (non 'dnf5')
    # E SE config-manager non è già disponibile (potrebbe essere parte di una installazione base)
    if "dnf-plugins-core" in packages_to_install_this_run and dnf_command == "dnf":
        # Verifichiamo se config-manager è già presente. Se sì, potremmo non aver bisogno di installare dnf-plugins-core esplicitamente
        # o potremmo volerlo comunque per assicurarci che sia aggiornato.
        # Per semplicità, se è nella lista, proviamo a installarlo/aggiornarlo.
        print_info("Ensuring 'dnf-plugins-core' is installed/updated (for dnf)...")
        if not run_command([dnf_command, "install", "-y", "dnf-plugins-core"]):
            print_warning("Failed to install/update dnf-plugins-core. Repository management for Chrome via config-manager might fail.")
            logging.warning("Failed to install/update dnf-plugins-core.")
            # Non è un fallimento critico per l'intero processo, il fallback manuale per Chrome può funzionare
        else:
            print_success("'dnf-plugins-core' processed.")
            # Non lo rimuoviamo dalla lista principale di installazione, DNF gestirà se è già installato.

    # Gestisci Google Chrome (aggiunta repo + inserimento nella lista di installazione)
    if "google-chrome-stable" in packages_to_install_this_run:
        if not _add_google_chrome_repo():
            print_warning("Proceeding without Google Chrome due to repository setup failure.")
            logging.warning("Google Chrome repository setup failed. Chrome will not be installed.")
            try:
                packages_to_install_this_run.remove("google-chrome-stable")
            except ValueError:
                pass # Già non presente
    
    # Filtra i pacchetti che potrebbero essere stati rimossi (es. Chrome)
    final_packages_list = [pkg for pkg in packages_to_install_this_run if pkg] 

    if not final_packages_list:
        print_info("No further packages to install from the list.")
        return True # Potrebbe essere che tutto era già gestito o rimosso

    command = [dnf_command, "install", "-y"] + final_packages_list
    
    if run_command(command):
        print_success(f"Successfully processed packages: {', '.join(final_packages_list)}")
    else:
        print_error(f"Failed to install/process some packages: {', '.join(final_packages_list)}")
        logging.error(f"{dnf_command} installation command failed for: {', '.join(final_packages_list)}")
        all_good = False

    return all_good


def set_zsh_as_default_shell():
    """Sets Zsh as the default shell for the current user."""
    print_step(2, "Setting Zsh as default shell")
    zsh_path = shutil.which("zsh")
    if not zsh_path:
        print_error("Zsh is not installed or not found in PATH. Cannot set as default shell.")
        logging.error("Zsh not found via shutil.which('zsh').")
        return False

    try:
        username = os.environ.get('SUDO_USER')
        if not username: # Fallback se SUDO_USER non è impostato (es. script eseguito direttamente come root)
            username = os.getlogin()
            print_warning(f"SUDO_USER not set, falling back to os.getlogin(): {username} for chsh.")
            logging.warning(f"SUDO_USER not set, chsh target user: {username}")
        if not username: # Ancora nessun username
             print_error("Could not determine the target username for chsh.")
             logging.error("Username for chsh could not be determined.")
             return False

    except OSError:
        print_error("Could not determine the current user to change shell (OSError on os.getlogin()).")
        logging.error("os.getlogin() failed and SUDO_USER not set for chsh.")
        return False

    print_info(f"Attempting to set {zsh_path} as default shell for user '{username}'.")
    command = ["chsh", "-s", zsh_path, username]

    if run_command(command):
        print_success(f"Zsh set as default shell for user '{username}'.")
        # L'invito a riavviare il terminale sarà gestito alla fine di run_basic_configuration
        return True
    else:
        print_error(f"Failed to set Zsh as default shell for user '{username}'.")
        logging.error(f"chsh command failed for user {username} with shell {zsh_path}.")
        return False

def run_basic_configuration():
    """
    Main function to run all basic configuration steps.
    This is considered "Phase 2" of the setup.
    Returns True if all critical steps were successful, False otherwise.
    """
    print_header("Phase 2: Basic System Package Configuration")

    if not _check_root_privileges():
        return False # Fallimento critico

    overall_success = True # Traccia il successo complessivo di questa fase

    if not install_packages():
        print_error("Package installation phase encountered errors. Some packages might not be installed.")
        overall_success = False # Un fallimento qui è significativo
        # Decidi se vuoi interrompere o continuare. Per ora, continuiamo a provare a impostare la shell
        # se zsh è stato installato.
    
    zsh_in_list = "zsh" in PACKAGES_TO_INSTALL
    zsh_installed_and_found = shutil.which("zsh") is not None

    if zsh_in_list and zsh_installed_and_found:
        if not set_zsh_as_default_shell():
            print_warning("Failed to set Zsh as default shell. Please do it manually if desired.")
            # Non consideriamo questo un fallimento critico per overall_success, ma un avvertimento.
    elif zsh_in_list and not zsh_installed_and_found:
        print_warning("Zsh was in the list of packages to install, but it was not found after installation. Skipping setting it as default shell.")
        logging.warning("Zsh not found after attempted installation. Skipping chsh.")

    if overall_success:
        console.print("\n[bold green]Phase 2 (Basic Package Configuration) completed successfully.[/bold green]")
        print_with_emoji("❗", "[bold yellow on_black] IMPORTANT: Zsh has been set as the default shell (if installed). [/bold yellow on_black]")
        print_with_emoji("❗", "[bold yellow on_black] Please close and reopen your terminal, or log out and log back in, [/bold yellow on_black]")
        print_with_emoji("❗", "[bold yellow on_black] for the new shell and other changes to take full effect. [/bold yellow on_black]")
    else:
        console.print("\n[bold yellow]Phase 2 (Basic Package Configuration) completed with some errors.[/bold yellow]")
        print_warning("Please check the log file 'app.log' and output above for details.")
        print_info("Some configurations might require manual intervention.")
    
    return overall_success


if __name__ == '__main__':
    # For testing basic_configuration.py directly
    # Make sure to run as root: sudo python3 basic_configuration.py
    logging.basicConfig(
        filename='app_test_basic_config.log',
        level=logging.INFO, # Log more info for direct testing
        format='%(asctime)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
    )
    console.print("[yellow]Running basic_configuration.py directly for testing purposes.[/yellow]")
    console.print("[yellow]This requires superuser privileges for 'dnf' and 'chsh'.[/yellow]")
    if run_basic_configuration():
        print_success("Basic configuration test completed successfully.")
    else:
        print_error("Basic configuration test completed with errors.")