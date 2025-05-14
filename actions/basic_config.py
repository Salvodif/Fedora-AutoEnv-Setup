# fedora_config_app/actions/basic_config.py
# English: This file handles the "basic configuration" tasks,
# specifically installing DNF packages and setting Zsh as default.

import subprocess
from typing import List
import os
import shutil # For shutil.which
import getpass # For getpass.getuser

from ..myrich import console, print_message, print_panel, confirm_action # Relative import
from ..logging_setup import logger # Relative import

# Packages to be installed during basic configuration
PACKAGES_TO_INSTALL: List[str] = [
    "git",
    "curl",
    "cargo", # Rust's package manager and build system
    "zsh",   # Z Shell - ensure this is installed before trying to set it
    "python3",
    "python3-pip",
    "stow",
    "dnf-plugins-core",
    "powerline-fonts",
    "btop",
    "bat",
    "fzf",
    # "google-chrome-stable" # Handled separately
]

def _run_command(command: List[str], description: str, use_sudo: bool = True) -> bool:
    """
    Runs a system command and handles output.
    Args:
        command (List[str]): The command and its arguments.
        description (str): A description of what the command does, for logging/messaging.
        use_sudo (bool): Whether to prepend 'sudo' to the command. Default True.
    Returns:
        bool: True if successful, False otherwise.
    """
    final_command = command
    if use_sudo:
        final_command = ["sudo"] + command
        
    try:
        print_message(f"Executing: {' '.join(final_command)} ({description})", style="info")
        logger.info(f"Executing: {' '.join(final_command)} ({description})")
        
        process = subprocess.Popen(final_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        stdout_lines = []
        stderr_lines = []

        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    console.print(f"[dim cyan]  [STDOUT] {line}[/dim cyan]")
                    stdout_lines.append(line)
                    logger.debug(f"STDOUT: {line}")
        
        if process.stderr:
            for line in iter(process.stderr.readline, ''):
                line = line.strip()
                if line:
                    console.print(f"[dim orange3]  [STDERR] {line}[/dim orange3]")
                    stderr_lines.append(line)
                    logger.warning(f"STDERR: {line}")

        process.wait()

        if process.returncode == 0:
            print_message(f"{description} completed successfully.", style="success")
            logger.info(f"{description} completed successfully. RC: {process.returncode}")
            return True
        else:
            print_message(f"{description} failed with error code {process.returncode}.", style="error")
            logger.error(f"{description} failed. RC: {process.returncode}")
            logger.error(f"STDOUT:\n{''.join(stdout_lines)}")
            logger.error(f"STDERR:\n{''.join(stderr_lines)}")
            print_panel("\n".join(stderr_lines), title="Error Details", border_style="red")
            return False
    except FileNotFoundError:
        err_msg = f"Command not found: {final_command[0]}. Is it installed and in PATH?"
        print_message(err_msg, style="error")
        logger.error(err_msg)
        return False
    except Exception as e:
        err_msg = f"An unexpected error occurred while running '{' '.join(final_command)}': {e}"
        print_message(err_msg, style="error")
        logger.exception(err_msg)
        return False

def _install_google_chrome():
    """Handles the specific steps to install Google Chrome."""
    print_message("Setting up Google Chrome...", style="info")
    
    # 1. Add Google Chrome GPG Key
    # `rpm --import` is usually run as root, so `sudo` is appropriate via _run_command
    gpg_key_cmd = ["rpm", "--import", "https://dl.google.com/linux/linux_signing_key.pub"]
    if not _run_command(gpg_key_cmd, "Importing Google GPG key"): # implicitly uses sudo
        print_message("Failed to import Google GPG key. Skipping Chrome installation.", style="error")
        return False

    # 2. Add Google Chrome repository
    add_repo_cmd = ["dnf", "config-manager", "--add-repo", "https://dl.google.com/linux/chrome/rpm/stable/x86_64"]
    if not _run_command(add_repo_cmd, "Adding Google Chrome repository"): # implicitly uses sudo
        print_message("Failed to add Google Chrome repository. Skipping Chrome installation.", style="error")
        return False
        
    # 3. Install Google Chrome
    chrome_install_cmd = ["dnf", "install", "-y", "google-chrome-stable"]
    if not _run_command(chrome_install_cmd, "Installing Google Chrome"): # implicitly uses sudo
        print_message("Failed to install Google Chrome.", style="error")
        return False
    
    print_message("Google Chrome setup completed.", style="success")
    return True

def _set_default_shell_to_zsh():
    """Attempts to set Zsh as the default shell for the user."""
    console.line()
    print_message("Attempting to set Zsh as the default shell...", style="info")

    zsh_path = shutil.which("zsh")
    if not zsh_path:
        print_message("Zsh executable not found. Skipping setting default shell.", style="error")
        logger.error("Zsh not found in PATH, cannot set as default shell.")
        return False

    # Determine the username of the user who invoked the script, even if sudo was used.
    # If SUDO_USER is set, it means the script was run with sudo by that user.
    # Otherwise, get the current logged-in user.
    try:
        target_user = os.environ.get('SUDO_USER')
        if not target_user:
            target_user = getpass.getuser() # Gets the current user's login name
    except Exception as e:
        print_message(f"Could not determine target username: {e}", style="error")
        logger.error(f"Failed to determine target username for chsh: {e}")
        return False

    print_message(f"Zsh path: {zsh_path}", style="info")
    print_message(f"Target user for shell change: {target_user}", style="info")

    # The chsh command usually requires root privileges to change another user's shell,
    # or the user's own password if changing their own shell without root.
    # _run_command prepends sudo, which should cover both cases if script has sudo rights.
    chsh_command = ["chsh", "-s", zsh_path, target_user]
    
    if not _run_command(chsh_command, f"Setting Zsh as default shell for {target_user}"):
        print_message(f"Failed to set Zsh as default shell for {target_user}.", style="error")
        logger.error(f"chsh command failed for user {target_user} with Zsh path {zsh_path}.")
        return False

    print_message(f"Successfully set Zsh as the default shell for {target_user}.", style="success")
    print_message("You may need to log out and log back in for the change to take effect.", style="warning")
    logger.info(f"Zsh set as default shell for user {target_user}.")
    return True


def run_basic_configuration():
    """
    Runs the basic configuration steps: installing DNF packages and setting Zsh.
    """
    all_packages_installed_successfully = True
    print_message("Starting basic DNF package installation...", style="info")
    
    if not PACKAGES_TO_INSTALL:
        print_message("No packages specified for basic installation.", style="warning")
        logger.warning("Package list for basic installation is empty.")
    else:
        install_cmd = ["dnf", "install", "-y"] + PACKAGES_TO_INSTALL
        # _run_command will add sudo
        if not _run_command(install_cmd, f"Installing packages: {', '.join(PACKAGES_TO_INSTALL)}"):
            print_message("Some general packages failed to install. Check logs for details.", style="error")
            all_packages_installed_successfully = False
            # We might still want to try installing Chrome and setting Zsh if Zsh itself installed.

    console.line() # Visual separator
    if not _install_google_chrome():
        print_message("Google Chrome installation was not successful.", style="warning")
        # Not critical for other steps, so we don't set all_packages_installed_successfully to False here necessarily
        # unless Chrome is considered essential for "success" of this whole function.

    # Set Zsh as default shell, but only if Zsh is in the list and likely installed
    # Or, more robustly, check if zsh command is now available.
    if "zsh" in PACKAGES_TO_INSTALL: # A basic check
        if confirm_action(f"Do you want to set Zsh as the default shell?", default=True):
            _set_default_shell_to_zsh()
        else:
            print_message("Skipping setting Zsh as default shell.", style="info")
            logger.info("User skipped setting Zsh as default shell.")
    else:
        logger.info("Zsh not in the main package list, skipping setting it as default.")
    
    console.line()
    if all_packages_installed_successfully:
        print_message("Basic configuration process finished successfully.", style="success")
        logger.info("Basic configuration process finished successfully.")
    else:
        print_message("Basic configuration process finished, but some steps may have failed. Please review the output and logs.", style="warning")
        logger.warning("Basic configuration process finished with some failures.")


if __name__ == "__main__":
    from ..myrich import print_header # Adjust import for direct run
    
    print_header("Test Basic Configuration")
    run_basic_configuration()
    print_message("Test completed. Check output and fedora_config_app.log.", style="info")