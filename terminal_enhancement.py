# terminal_enhancement.py
import shutil
import os
import logging
from pathlib import Path

from myrich import (
    console, print_info, print_error, print_success,
    print_step, print_header, print_warning
)
from utils import run_command

# Cargo packages to install
CARGO_PACKAGES = ["du-dust", "eza", "atuin"]

def _get_user_info():
    """Gets username and home directory, preferring SUDO_USER if available."""
    username = os.environ.get('SUDO_USER')
    user_home_str = None

    if username:
        # Try to get home directory for SUDO_USER
        try:
            # os.path.expanduser(f"~{username}") is generally reliable
            user_home_str = os.path.expanduser(f"~{username}")
        except Exception as e:
            logging.warning(f"Could not expand ~{username}: {e}. Falling back to /home/{username}")
            user_home_str = f"/home/{username}"
    else:
        # Not running with sudo, or SUDO_USER not set
        username = os.getlogin()
        user_home_str = os.path.expanduser("~")
        print_info(f"SUDO_USER not set. Targeting current user '{username}' with home '{user_home_str}'.")

    if not user_home_str: # Should not happen if above logic is sound
        print_error("User home directory could not be determined.")
        return None, None

    user_home = Path(user_home_str)
    if not user_home.is_dir():
        print_error(f"User home directory '{user_home}' for user '{username}' not found or is not a directory.")
        return None, None
        
    return username, user_home

def _install_zoxide(username: str, user_home: Path):
    """Installs zoxide for the specified user."""
    print_info("Installing zoxide...")
    logging.info(f"Attempting to install zoxide for user {username} in {user_home}")

    # zoxide install script string
    zoxide_install_script = "curl -sSfL https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh | sh"

    # Command to execute. Needs to run as the target user with correct HOME.
    # Using `sh -c '...'` is robust for commands with pipes.
    if os.geteuid() == 0 and username and username != "root":
        # Running as root, targeting a non-root user
        cmd_to_run = f"sudo -u {username} env HOME='{str(user_home)}' sh -c '{zoxide_install_script}'"
    else:
        # Running as the target user directly, or as root for root's own setup
        cmd_to_run = f"env HOME='{str(user_home)}' sh -c '{zoxide_install_script}'"

    # run_command needs shell=True for pipes if the command string contains them directly.
    # Here, `sh -c` handles the pipe, so the outer command to `run_command` can be shell=True
    # because `cmd_to_run` is a string that the shell needs to parse (especially `sudo -u ... sh -c '...'`).
    stdout, stderr, returncode = run_command(cmd_to_run, shell=True, capture_output=True, check=False)

    if returncode == 0:
        print_success("zoxide installed successfully.")
        logging.info("zoxide installed successfully.")
        print_info("You may need to source your shell configuration file (e.g., .zshrc) or open a new terminal for zoxide to be available.")
        return True
    else:
        print_error("Failed to install zoxide.")
        if stdout: print_info(f"zoxide install stdout:\n{stdout}")
        if stderr: print_error(f"zoxide install stderr:\n{stderr}")
        logging.error(f"zoxide installation failed. RC: {returncode}, stderr: {stderr.strip()}")
        return False

def _check_cargo():
    """Checks if cargo is installed and available in PATH."""
    print_info("Checking for cargo (Rust's package manager)...")
    if shutil.which("cargo"):
        print_success("cargo is installed and found in PATH.")
        logging.info("cargo found in PATH.")
        return True
    else:
        print_error("cargo not found in PATH. Please ensure it was installed in Phase 2 (Basic Package Configuration).")
        print_warning("Skipping installation of Rust-based terminal tools (du-dust, eza, atuin).")
        logging.error("cargo not found in PATH. Cannot install Rust packages.")
        return False

def _install_cargo_packages(username: str, user_home: Path):
    """Installs specified Rust packages using cargo for the user."""
    if not _check_cargo():
        return False # Prerequisite not met

    print_info(f"Installing Rust packages using cargo: {', '.join(CARGO_PACKAGES)}")
    all_packages_installed_successfully = True

    for package in CARGO_PACKAGES:
        print_info(f"Attempting to install '{package}' with cargo...")
        
        # Base cargo command
        cargo_cmd_list = ["cargo", "install", "--locked", package]
        
        # Prepare command for execution context
        if os.geteuid() == 0 and username and username != "root":
            # Running as root, targeting a non-root user
            # Ensure HOME is set, and cargo (from system PATH) can run
            # PATH for sudo -u can be minimal, relying on /usr/bin etc. being in it.
            # Cargo typically installs to $HOME/.cargo/bin
            effective_cmd = ["sudo", "-u", username, "env", f"HOME={str(user_home)}"] + cargo_cmd_list
        else:
            # Running as the target user directly, or as root for root's setup
            # Set HOME in env for subprocess if running as root for root, otherwise current env is fine
            if os.geteuid() == 0 and username == "root": # root for root
                 effective_cmd = ["env", f"HOME={str(user_home)}"] + cargo_cmd_list
            else: # non-root user for self
                 effective_cmd = cargo_cmd_list


        stdout, stderr, returncode = run_command(effective_cmd, capture_output=True, check=False)

        if returncode == 0:
            print_success(f"'{package}' installed successfully via cargo.")
            logging.info(f"Successfully installed {package} via cargo for user {username}.")
        else:
            print_error(f"Failed to install '{package}' via cargo.")
            if stdout: print_info(f"cargo install {package} stdout:\n{stdout.strip()}")
            if stderr: print_error(f"cargo install {package} stderr:\n{stderr.strip()}")
            logging.error(f"Failed to install {package} for user {username}. RC: {returncode}, stderr: {stderr.strip()}")
            all_packages_installed_successfully = False
            # Continue to try installing other packages

    if all_packages_installed_successfully:
        print_success("All specified Rust packages processed successfully.")
        logging.info("All Rust packages in CARGO_PACKAGES processed successfully.")
    else:
        print_warning("Some Rust packages failed to install. Check logs for details.")
        logging.warning("Failures encountered during Rust package installation via cargo.")
    
    if shutil.which("cargo"): # Only print if cargo is actually there
        print_info(f"Ensure '{user_home}/.cargo/bin' is in your PATH.")
        print_info("You may need to source your shell configuration file (e.g., .zshrc) or open a new terminal.")
        
    return all_packages_installed_successfully

def run_terminal_enhancement():
    """Main function for Phase 4: Terminal Enhancement."""
    print_header("Phase 4: Terminal Enhancement")

    username, user_home = _get_user_info()
    if not username or not user_home:
        print_error("Critical: Could not determine valid user and home directory. Aborting Phase 4.")
        logging.critical("Phase 4 aborted: Could not determine user/home.")
        return False

    print_info(f"Running terminal enhancements for user: {username} (Home: {user_home})")
    logging.info(f"Starting Phase 4: Terminal Enhancement for user {username}, home {user_home}")

    phase_overall_success = True

    # Step 4.1: Install zoxide
    print_step(4.1, "Installing zoxide")
    if not _install_zoxide(username, user_home):
        print_warning("zoxide installation encountered issues or failed.")
        # Decide if this is critical. For now, let's say it's not fatal for the phase.
        # phase_overall_success = False # Uncomment if zoxide is critical for phase success
        logging.warning("Phase 4: zoxide installation was not successful.")
    
    # Step 4.2: Install Rust-based terminal tools
    print_step(4.2, "Installing Rust-based terminal tools (du-dust, eza, atuin)")
    if not _install_cargo_packages(username, user_home):
        print_warning("Installation of Rust-based terminal tools encountered issues or failed.")
        phase_overall_success = False # These tools are a core part of this phase
        logging.warning("Phase 4: Rust-based terminal tools installation was not successful.")

    if phase_overall_success:
        print_success("\nPhase 4 (Terminal Enhancement) completed successfully.")
        logging.info("Phase 4 (Terminal Enhancement) completed successfully.")
    else:
        print_warning("\nPhase 4 (Terminal Enhancement) completed with some errors or warnings. Please check the logs and output above.")
        logging.warning("Phase 4 (Terminal Enhancement) completed with errors/warnings.")
    
    return phase_overall_success