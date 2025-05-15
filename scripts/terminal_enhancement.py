# scripts/terminal_enhancement.py
import logging
import os
import shutil
import pwd
from pathlib import Path

from scripts.myrich import (
    print_header, print_info, print_error, print_success,
    print_step, print_warning
)
from scripts.utils import run_command # Assuming utils.py is in scripts/

# SCRIPT_DIR needs to be defined relative to *this* file's location if used by functions here.
# If functions expect it from install.py, it needs to be passed.
# For deploy_user_configs, SCRIPT_DIR usually refers to the root of the project.
# Let's define it to point to the project root, assuming terminal_enhancement.py is in a 'scripts' subdirectory.
PROJ_ROOT_DIR = Path(__file__).resolve().parent.parent 

def get_real_user_home_for_terminal(): # Renamed to avoid conflict if imported elsewhere
    """Determines the real user's home directory, even when run with sudo."""
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user:
        try:
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except KeyError:
            # Fallback for systems where SUDO_USER might not be in pwd (e.g., containers, unusual setups)
            home_path = Path(f"/home/{sudo_user}")
            if home_path.is_dir():
                return home_path
            print_warning(f"Could not determine home directory for SUDO_USER '{sudo_user}' via pwd. Falling back to current user's home.")
            return Path.home() # Last resort
    return Path.home()

USER_HOME_DIR_FOR_TERMINAL = get_real_user_home_for_terminal()

def deploy_user_configs_for_terminal():
    """Deploys .zshrc and .nanorc to the target user's home directory."""
    # This function is now part of Terminal Enhancement phase
    # print_step("3.1", "Deploying user configuration files (.zshrc, .nanorc)") # Step numbering handled by caller
    print_info("Deploying user configuration files (.zshrc, .nanorc)...")

    if not USER_HOME_DIR_FOR_TERMINAL or not USER_HOME_DIR_FOR_TERMINAL.is_dir():
        print_error(f"Target user home '{USER_HOME_DIR_FOR_TERMINAL}' is invalid. Cannot deploy terminal configs.")
        return False
    
    print_info(f"Target user home for terminal configs: {USER_HOME_DIR_FOR_TERMINAL}")
    all_copied = True
    # Configs are relative to PROJ_ROOT_DIR
    configs_to_deploy = {
        PROJ_ROOT_DIR / "zsh" / ".zshrc": USER_HOME_DIR_FOR_TERMINAL / ".zshrc",
        PROJ_ROOT_DIR / "nano" / ".nanorc": USER_HOME_DIR_FOR_TERMINAL / ".nanorc"
    }

    for src, dest in configs_to_deploy.items():
        if not src.exists():
            print_warning(f"Source configuration file '{src}' not found. Skipping its deployment.")
            all_copied = False # Consider this a partial failure
            continue # Skip to the next file

        try:
            dest.parent.mkdir(parents=True, exist_ok=True) # Ensure parent directory exists
            shutil.copy2(src, dest)
            print_success(f"Copied '{src.name}' to '{dest}'")

            # Set ownership if running as root and SUDO_USER is set
            if os.geteuid() == 0 and os.environ.get('SUDO_UID') and os.environ.get('SUDO_GID'):
                try:
                    os.chown(dest, int(os.environ['SUDO_UID']), int(os.environ['SUDO_GID']))
                    print_info(f"Set ownership of '{dest.name}' to SUDO_USER.")
                except Exception as e_chown:
                    print_warning(f"Could not set ownership for '{dest}': {e_chown}")
                    # Not necessarily a fatal error for the copy itself, but good to note.
        except Exception as e_copy:
            print_error(f"Failed to copy '{src.name}' to '{dest}': {e_copy}")
            all_copied = False
            
    if not all_copied:
        print_error("One or more terminal configuration files failed to deploy or were not found.")
    return all_copied

def _install_starship():
    """Installs Starship prompt."""
    print_info("Installing Starship prompt...")
    # Determine if running as root to install for SUDO_USER, or as the user themselves.
    # Starship install script handles user context well.
    
    # Check if already installed by looking for the binary in common user paths or system paths
    # This is a basic check; Starship's own script might be more robust.
    # Common install path is ~/.cargo/bin/starship
    starship_user_path = USER_HOME_DIR_FOR_TERMINAL / ".cargo" / "bin" / "starship"
    if starship_user_path.exists() or shutil.which("starship"):
        print_info("Starship appears to be already installed.")
        # Optionally, offer to update or reinstall. For now, skip if found.
        return True

    # Command to install Starship using their official script
    # The script tries to install for the current user. If run as root, it might install for root.
    # We need to ensure it installs for SUDO_USER if that's the context.
    # `curl -sS https://starship.rs/install.sh | sh -s -- -y`
    # The `sh -s -- -y` part passes arguments to the script downloaded by curl. `-y` for non-interactive.
    
    cmd_list = ["curl", "-sS", "https://starship.rs/install.sh"]
    # We need to pipe this to sh. run_command currently doesn't support piping directly in a list.
    # So, we construct a shell command string.
    
    shell_command = "curl -sS https://starship.rs/install.sh | sh -s -- -y -b " + str(USER_HOME_DIR_FOR_TERMINAL / ".local" / "bin")
    # Specify install directory with -b to ensure it's in user's path

    print_info(f"Executing Starship install script: {shell_command}")

    success = False
    if os.geteuid() == 0 and os.environ.get('SUDO_USER'):
        # Run the shell command as the SUDO_USER
        # Need to be careful with how shell and sudo interact here.
        # `sudo -u user sh -c "curl ... | sh -s -- -y"`
        sudo_user = os.environ.get('SUDO_USER')
        # To ensure paths like ~/.cargo/bin are correct for SUDO_USER, their HOME needs to be set.
        # `sudo -i -u username` helps, or explicitly setting HOME.
        # Let _run_command_as_user handle user context if we adapt it for shell=True
        # For now, direct shell command:
        final_shell_cmd = f"export HOME='{USER_HOME_DIR_FOR_TERMINAL}'; export CARGO_HOME='{USER_HOME_DIR_FOR_TERMINAL}/.cargo'; {shell_command}"
        
        # Using _run_command_as_user (if it can handle shell=True or complex commands)
        # Or simpler:
        user_context_cmd = ["sudo", "-i", "-u", sudo_user, "sh", "-c", shell_command]
        if run_command(user_context_cmd, check=False): # Check=False as success is determined by Starship binary
            success = True
    else:
        # Running as the user directly, or as root without SUDO_USER (installs for root)
        if run_command(shell_command, shell=True, check=False):
            success = True
    
    if success and ( (USER_HOME_DIR_FOR_TERMINAL / ".local" / "bin" / "starship").exists() or shutil.which("starship")):
        print_success("Starship installed successfully.")
        print_info("Ensure ~/.local/bin is in your PATH if not already.")
        return True
    else:
        print_error("Starship installation failed or binary not found after installation.")
        print_info("Starship may need to be installed manually: https://starship.rs/#installation")
        return False

def run_terminal_enhancement():
    """Main function for terminal enhancement phase."""
    print_header("Terminal Enhancement Configuration")
    overall_success = True

    # Step 1: Deploy .zshrc and .nanorc
    print_step("TE.1", "Deploying user configuration files")
    if not deploy_user_configs_for_terminal():
        print_error("Failed to deploy essential terminal configuration files (.zshrc, .nanorc).")
        print_warning("Subsequent terminal enhancements might not work as expected.")
        overall_success = False
        # If .zshrc is critical (e.g., for starship init), we might return False here.
        # For now, let's assume it's a strong warning but not a complete blocker for trying other steps.

    # Step 2: Install Starship prompt
    print_step("TE.2", "Installing Starship prompt")
    if not _install_starship():
        print_warning("Starship prompt installation failed or was skipped.")
        # This is an enhancement, so not necessarily a critical failure for the phase.
        # overall_success = False # Uncomment if Starship is considered critical for this phase.
    
    # Add other terminal enhancement steps here (e.g., zsh plugins, etc.)
    # For example:
    # print_step("TE.3", "Installing Zsh plugins (e.g., zsh-autosuggestions, zsh-syntax-highlighting)")
    # success_plugins = _install_zsh_plugins() # Implement this function
    # if not success_plugins: overall_success = False

    if overall_success:
        print_success("Terminal Enhancement phase completed.")
        print_info("Please restart your terminal or source your .zshrc (e.g., 'source ~/.zshrc') for changes to take effect.")
    else:
        print_error("Terminal Enhancement phase completed with errors or warnings.")
    
    return overall_success

if __name__ == '__main__':
    # For testing terminal_enhancement.py directly
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    # Ensure SUDO_USER, SUDO_UID, SUDO_GID are set if testing with sudo
    # Example: sudo SUDO_USER=$USER SUDO_UID=$(id -u $USER) SUDO_GID=$(id -g $USER) python scripts/terminal_enhancement.py
    if run_terminal_enhancement():
        print_success("Terminal enhancement script test completed successfully.")
    else:
        print_error("Terminal enhancement script test completed with errors.")