# basic_configuration.py
import logging
import os
import shutil

from myrich import console, print_info, print_warning, print_error, print_success, print_step, print_with_emoji
from utils import run_command # Import from utils

# ... (PACKAGES_TO_INSTALL, CHROME_REPO_URL, CHROME_REPO_NAME remain the same) ...
PACKAGES_TO_INSTALL = [
    "git", "curl", "cargo", "zsh", "python3", "python3-pip",
    "stow", "dnf-plugins-core", "powerline-fonts", "btop",
    "bat", "fzf", "google-chrome-stable"
]
CHROME_REPO_URL = "https://dl.google.com/linux/chrome/rpm/stable/x86_64"
CHROME_REPO_NAME = "google-chrome"


# Remove the local _run_command function, as we'll use the one from utils.py

def _check_root_privileges(): # Renamed for clarity, similar to system_preparation
    """Checks for root privileges."""
    if os.geteuid() != 0:
        print_error("This operation requires superuser (root) privileges.")
        logging.error("Attempted basic configuration without root privileges.")
        return False
    return True


def _add_google_chrome_repo():
    """Adds the Google Chrome repository."""
    print_step(1, "Adding Google Chrome repository")
    # ... (no changes to the logic, just ensure it uses the imported run_command)
    if not shutil.which("dnf"): # dnf might be dnf5 now
        dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
        if not shutil.which(dnf_cmd):
            print_error("`dnf` or `dnf5` command not found. Cannot proceed with repository management.")
            logging.error("`dnf`/`dnf5` command not found during Chrome repo setup.")
            return False
    else:
        dnf_cmd = "dnf"


    try:
        # Using run_command to check repo existence
        stdout, stderr, returncode = run_command(
            [dnf_cmd, 'repolist', CHROME_REPO_NAME],
            capture_output=True,
            check=False # Don't raise an exception if repo is not found
        )
        if returncode == 0 and CHROME_REPO_NAME in stdout and "enabled" in stdout:
            print_info(f"Google Chrome repository '{CHROME_REPO_NAME}' already exists and is enabled.")
            return True
    except Exception as e:
        print_warning(f"Could not check for existing Chrome repo: {e}")
        logging.warning(f"Could not check for existing Chrome repo: {e}")

    cmd_add_repo = [
        dnf_cmd, "config-manager", "--add-repo", CHROME_REPO_URL
    ]
    if not run_command(cmd_add_repo):
        print_error("Failed to add Google Chrome repository.")
        logging.error(f"Failed to add Google Chrome repository using {dnf_cmd} config-manager.")
        return False
    print_success("Google Chrome repository added successfully.")
    return True


def install_packages():
    """Installs the specified packages using DNF (or DNF5 if available)."""
    print_step(2, "Installing core packages")
    
    dnf_command = "dnf5" if shutil.which("dnf5") else "dnf"
    if not shutil.which(dnf_command):
        print_error(f"`{dnf_command}` command not found. Cannot install packages.")
        logging.error(f"`{dnf_command}` not found for package installation.")
        return False

    all_good = True
    packages_to_actually_install = list(PACKAGES_TO_INSTALL) # Create a mutable copy

    # Install dnf-plugins-core first if it's in the list and dnf is used
    # dnf5 might handle config-manager differently or have it built-in.
    # For now, let's assume dnf-plugins-core is still relevant if dnf is the primary.
    if "dnf-plugins-core" in packages_to_actually_install and dnf_command == "dnf":
        print_info("Ensuring 'dnf-plugins-core' is installed first (for dnf)...")
        if not run_command([dnf_command, "install", "-y", "dnf-plugins-core"]):
            print_error("Failed to install dnf-plugins-core. Repository management for Chrome might fail.")
            logging.error("Failed to install dnf-plugins-core.")
            # Don't return False here, let it try to continue
        else:
            print_success("'dnf-plugins-core' is installed.")
            packages_to_actually_install.remove("dnf-plugins-core") # Avoid installing again


    if "google-chrome-stable" in packages_to_actually_install:
        if not _add_google_chrome_repo():
            print_warning("Proceeding without Google Chrome due to repository setup failure.")
            logging.warning("Google Chrome repository setup failed. Chrome will not be installed.")
            packages_to_actually_install.remove("google-chrome-stable")


    if not packages_to_actually_install:
        print_info("No further packages to install from the list.")
        return True

    command = [dnf_command, "install", "-y"] + packages_to_actually_install
    
    if run_command(command):
        print_success(f"Successfully installed: {', '.join(packages_to_actually_install)}")
    else:
        print_error(f"Failed to install some packages: {', '.join(packages_to_actually_install)}")
        logging.error(f"{dnf_command} installation command failed for: {', '.join(packages_to_actually_install)}")
        all_good = False

    return all_good


def set_zsh_as_default_shell():
    """Sets Zsh as the default shell for the current user."""
    print_step(3, "Setting Zsh as default shell")
    zsh_path = shutil.which("zsh")
    if not zsh_path:
        print_error("Zsh is not installed or not found in PATH. Cannot set as default shell.")
        logging.error("Zsh not found via shutil.which('zsh').")
        return False

    try:
        username = os.environ.get('SUDO_USER')
        if not username:
            username = os.getlogin()
            print_warning(f"SUDO_USER not set, falling back to os.getlogin(): {username}")
            logging.warning(f"SUDO_USER not set, falling back to os.getlogin(): {username}")
    except OSError:
        print_error("Could not determine the current user to change shell.")
        logging.error("os.getlogin() failed and SUDO_USER not set.")
        return False

    print_info(f"Attempting to set {zsh_path} as default shell for user '{username}'.")
    command = ["chsh", "-s", zsh_path, username]

    if run_command(command):
        print_success(f"Zsh set as default shell for user '{username}'.")
        print_with_emoji("❗", "[bold yellow]Please log out and log back in, or restart your terminal for the changes to take effect.[/bold yellow]")
        return True
    else:
        print_error(f"Failed to set Zsh as default shell for user '{username}'.")
        logging.error(f"chsh command failed for user {username} with shell {zsh_path}.")
        return False

def run_basic_configuration():
    """Main function to run all basic configuration steps."""
    print_header("Basic System Package Configuration")

    if not _check_root_privileges(): # Use the renamed local check
        return False # Indicate failure

    success = True
    if not install_packages():
        print_error("Package installation phase encountered errors. Some packages might not be installed.")
        success = False
    
    if "zsh" in PACKAGES_TO_INSTALL and shutil.which("zsh"):
        if not set_zsh_as_default_shell():
            print_warning("Failed to set Zsh as default shell. Please do it manually if desired.")
            # This might not be a critical failure for the overall success status
    elif "zsh" in PACKAGES_TO_INSTALL:
        print_warning("Zsh was in the list of packages to install, but 'which zsh' cannot find it. Skipping setting it as default shell.")
        logging.warning("Zsh not found after attempted installation. Skipping chsh.")

    if success:
        console.print("\n[bold green]Basic package configuration phase completed.[/bold green]")
    else:
        console.print("\n[bold yellow]Basic package configuration phase completed with some errors.[/bold yellow]")
    
    console.print("Please check the log file 'app.log' for any warnings or errors.")
    return success


if __name__ == '__main__':
    logging.basicConfig(
        filename='app_test_basic_config.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    console.print("[yellow]Running basic_configuration.py directly for testing purposes.[/yellow]")
    console.print("[yellow]This requires superuser privileges for 'dnf' and 'chsh'.[/yellow]")
    run_basic_configuration()