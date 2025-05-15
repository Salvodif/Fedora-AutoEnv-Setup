# terminal_enhancement.py
import shutil
import os
import logging
from pathlib import Path

from scripts.myrich import (
    console, print_info, print_error, print_success,
    print_step, print_header, print_warning
)
from scripts.utils import run_command

# Cargo packages to install
CARGO_PACKAGES = ["du-dust", "eza", "atuin"]

OMZ_PLUGINS_TO_INSTALL = {
    "zsh-autosuggestions": "https://github.com/zsh-users/zsh-autosuggestions",
    "zsh-syntax-highlighting": "https://github.com/zsh-users/zsh-syntax-highlighting.git",
    "you-should-use": "https://github.com/MichaelAquilina/zsh-you-should-use.git",
    "zsh-eza": "https://github.com/z-shell/zsh-eza.git", # Note: zsh-eza might need specific .zshrc config too
    "fzf-tab": "https://github.com/Aloxaf/fzf-tab"
}
# The 'git' plugin is usually bundled with OMZ, just needs to be enabled in .zshrc

def _get_user_info():
    """Gets username and home directory, preferring SUDO_USER if available."""
    username = os.environ.get('SUDO_USER')
    user_home_str = None

    if username:
        try:
            user_home_str = os.path.expanduser(f"~{username}")
        except Exception as e:
            logging.warning(f"Could not expand ~{username}: {e}. Falling back to /home/{username}")
            user_home_str = f"/home/{username}"
    else:
        username = os.getlogin()
        user_home_str = os.path.expanduser("~")
        print_info(f"SUDO_USER not set. Targeting current user '{username}' with home '{user_home_str}'.")

    if not user_home_str:
        print_error("User home directory could not be determined.")
        return None, None

    user_home = Path(user_home_str)
    if not user_home.is_dir():
        print_error(f"User home directory '{user_home}' for user '{username}' not found or is not a directory.")
        return None, None
        
    return username, user_home

def _run_as_user(cmd_list_or_str, username: str, user_home: Path, shell=False, capture_output=True, check=False, cwd=None):
    """Helper to run a command as the specified user, setting HOME."""
    base_env = {}
    # Ensure minimal PATH if running as sudo -u, some systems clear it too much
    # This assumes common paths; adjust if needed for your target systems.
    minimal_path = f"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:{user_home}/.local/bin:{user_home}/.cargo/bin"

    if os.geteuid() == 0 and username and username != "root":
        # Prepend sudo -u and env for HOME and PATH
        # Convert cmd_list_or_str to string if it's a list for `sh -c` usage with complex commands
        if isinstance(cmd_list_or_str, list):
            cmd_str_for_sh_c = ' '.join([f"'{arg}'" for arg in cmd_list_or_str]) # Basic quoting
        else:
            cmd_str_for_sh_c = cmd_list_or_str
        
        # Using a list for sudo command itself
        effective_cmd_list = [
            "sudo", "-u", username, 
            "env", f"HOME={str(user_home)}", f"PATH={minimal_path}:{os.environ.get('PATH', '')}", # Add existing path too
            "sh", "-c", cmd_str_for_sh_c
        ]
        # For sudo with sh -c, the command passed to sh -c is a string, so the outer run_command shell=False
        # but sh -c itself acts as a shell.
        return run_command(effective_cmd_list, shell=False, capture_output=capture_output, check=check, cwd=cwd)

    else: # Running as the target user directly, or as root for root's own setup
        # Set HOME and PATH in environment for subprocess
        current_env = os.environ.copy()
        current_env['HOME'] = str(user_home)
        current_env['PATH'] = f"{minimal_path}:{current_env.get('PATH', '')}"
        
        if isinstance(cmd_list_or_str, str) and shell is False and " " in cmd_list_or_str:
            # If it's a string with spaces and shell=False, subprocess.run might misinterpret.
            # Convert to list if it looks like a command with args. For simple commands, string is fine.
            # Or, just pass shell=True if the command string requires shell parsing.
            pass # Assuming caller sets shell=True if cmd_list_or_str is a complex shell command string

        # For commands run directly as user, use their existing environment primarily, but ensure HOME
        return run_command(cmd_list_or_str, shell=shell, capture_output=capture_output, check=check, env=current_env, cwd=cwd)


def _install_zoxide(username: str, user_home: Path):
    print_info("Installing zoxide...")
    logging.info(f"Attempting to install zoxide for user {username} in {user_home}")
    zoxide_install_script = "curl -sSfL https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh | sh"
    
    # _run_as_user will handle `sudo -u ... sh -c 'script'`
    stdout, stderr, returncode = _run_as_user(zoxide_install_script, username, user_home, shell=True) # shell=True for the pipe in the script string

    if returncode == 0:
        print_success("zoxide installed successfully.")
        print_info("zoxide init lines should be added to your .zshrc by its installer.")
        logging.info("zoxide installed successfully.")
        return True
    else:
        print_error(f"Failed to install zoxide. RC: {returncode}")
        if stdout: print_info(f"zoxide install stdout:\n{stdout.strip()}")
        if stderr: print_error(f"zoxide install stderr:\n{stderr.strip()}")
        logging.error(f"zoxide installation failed. RC: {returncode}, stderr: {stderr.strip()}")
        return False

def _check_cargo():
    # cargo is installed system-wide or should be in PATH from Phase 2
    print_info("Checking for cargo (Rust's package manager)...")
    if shutil.which("cargo"):
        print_success("cargo is installed and found in PATH.")
        return True
    else:
        print_error("cargo not found in PATH. Ensure it was installed in Phase 2.")
        print_warning("Skipping installation of Rust-based terminal tools.")
        logging.error("cargo not found in PATH.")
        return False

def _install_cargo_packages(username: str, user_home: Path):
    if not _check_cargo():
        return False

    print_info(f"Installing Rust packages using cargo: {', '.join(CARGO_PACKAGES)}")
    all_success = True
    for package in CARGO_PACKAGES:
        print_info(f"Attempting to install '{package}' with cargo...")
        cargo_cmd_list = ["cargo", "install", "--locked", package]
        
        # _run_as_user handles sudo -u if needed
        stdout, stderr, returncode = _run_as_user(cargo_cmd_list, username, user_home, shell=False)

        if returncode == 0:
            print_success(f"'{package}' installed successfully via cargo.")
        else:
            print_error(f"Failed to install '{package}' via cargo. RC: {returncode}")
            if stdout: print_info(f"  Stdout: {stdout.strip()}")
            if stderr: print_error(f"  Stderr: {stderr.strip()}")
            all_success = False
    
    if all_success:
        print_success("All specified Rust packages processed successfully.")
    else:
        print_warning("Some Rust packages failed to install.")
    
    print_info(f"Ensure '{user_home}/.cargo/bin' is in your PATH (typically handled by .zshrc).")
    return all_success

def _install_oh_my_zsh(username: str, user_home: Path):
    omz_dir = user_home / ".oh-my-zsh"
    if omz_dir.exists():
        print_info("Oh My Zsh appears to be already installed.")
        return True

    print_info("Oh My Zsh not found. Attempting to install...")
    # OMZ install script. RUNNER is for non-interactive.
    # It typically changes the default shell to zsh.
    omz_install_script = 'sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended'

    # Check if zsh is the default shell for the user first.
    # The OMZ script might try to chsh. If zsh is already default (set in Phase 2), this is fine.
    
    stdout, stderr, returncode = _run_as_user(omz_install_script, username, user_home, shell=True) # shell=True for the script string with $()

    if returncode == 0 and omz_dir.exists():
        print_success("Oh My Zsh installed successfully.")
        logging.info(f"Oh My Zsh installed for user {username}.")
        print_warning("The Oh My Zsh installer may have backed up your existing .zshrc and created a new one.")
        print_warning("You may need to merge your custom configurations or re-apply the .zshrc deployed by Phase 3.")
        return True
    else:
        print_error(f"Failed to install Oh My Zsh. RC: {returncode}")
        if stdout: print_info(f"OMZ install stdout:\n{stdout.strip()}")
        if stderr: print_error(f"OMZ install stderr:\n{stderr.strip()}")
        logging.error(f"OMZ installation failed for user {username}. RC: {returncode}, stderr: {stderr.strip()}")
        return False

def _install_omz_plugins(username: str, user_home: Path):
    omz_dir = user_home / ".oh-my-zsh"
    if not omz_dir.exists():
        print_warning("Oh My Zsh is not installed. Cannot install OMZ plugins.")
        return False # OMZ is a prerequisite

    # ZSH_CUSTOM is usually ~/.oh-my-zsh/custom, but OMZ sets this env var.
    # We define it explicitly for clarity and robustness if the env var isn't set in _run_as_user's context.
    zsh_custom_dir = omz_dir / "custom"
    plugins_dir = zsh_custom_dir / "plugins"
    
    # Ensure the custom plugins directory exists
    # Must be done as the target user if creating it
    if not plugins_dir.exists():
        print_info(f"Creating OMZ custom plugins directory: {plugins_dir}")
        # Create as user
        _, _, mkdir_retcode = _run_as_user(["mkdir", "-p", str(plugins_dir)], username, user_home, shell=False)
        if mkdir_retcode != 0:
            print_error(f"Failed to create OMZ custom plugins directory: {plugins_dir}")
            return False

    print_info(f"Installing Oh My Zsh plugins into {plugins_dir}...")
    all_success = True

    for plugin_name, repo_url in OMZ_PLUGINS_TO_INSTALL.items():
        plugin_path = plugins_dir / plugin_name
        if plugin_path.exists():
            print_info(f"Plugin '{plugin_name}' already exists. Skipping clone.")
            # Optionally, you could offer to update it here via `git pull`
            continue

        print_info(f"Cloning plugin '{plugin_name}' from {repo_url}...")
        git_clone_cmd = ["git", "clone", "--depth=1", repo_url, str(plugin_path)]
        
        # Clone into the plugins_dir as the user
        stdout, stderr, returncode = _run_as_user(git_clone_cmd, username, user_home, shell=False, cwd=str(plugins_dir.parent)) # cwd to ensure correct relative pathing if any

        if returncode == 0:
            print_success(f"Plugin '{plugin_name}' cloned successfully.")
        else:
            print_error(f"Failed to clone plugin '{plugin_name}'. RC: {returncode}")
            if stdout: print_info(f"  Stdout: {stdout.strip()}")
            if stderr: print_error(f"  Stderr: {stderr.strip()}")
            all_success = False
            # Clean up partially cloned directory if clone failed? (More complex)

    if all_success:
        print_success("All specified OMZ plugins processed.")
    else:
        print_warning("Some OMZ plugins failed to install/clone.")
    
    print_info("To enable these Oh My Zsh plugins, add their names to the 'plugins=(...)' line in your ~/.zshrc file.")
    example_plugins = "git " + " ".join(OMZ_PLUGINS_TO_INSTALL.keys())
    print_info(f"Example: plugins=({example_plugins})")
    return all_success


def run_terminal_enhancement():
    """Main function for Phase 4: Terminal Enhancement."""
    print_header("Phase 4: Terminal Enhancement")

    username, user_home = _get_user_info()
    if not username or not user_home:
        print_error("Critical: Could not determine valid user and home directory. Aborting Phase 4.")
        return False

    print_info(f"Running terminal enhancements for user: {username} (Home: {user_home})")
    phase_overall_success = True

    # Step 4.1: Install zoxide
    print_step(4.1, "Installing zoxide")
    if not _install_zoxide(username, user_home):
        print_warning("zoxide installation encountered issues.")
        # phase_overall_success = False # Decide if critical

    # Step 4.2: Install Rust-based terminal tools
    print_step(4.2, "Installing Rust-based terminal tools (du-dust, eza, atuin)")
    if not _install_cargo_packages(username, user_home):
        print_warning("Installation of Rust-based terminal tools encountered issues.")
        phase_overall_success = False # Cargo tools are key

    # Step 4.3: Install Oh My Zsh (if not present)
    print_step(4.3, "Ensuring Oh My Zsh is installed")
    omz_installed_this_run = False
    if not (user_home / ".oh-my-zsh").exists(): # Check again before calling install
        if _install_oh_my_zsh(username, user_home):
            omz_installed_this_run = True
        else:
            print_warning("Oh My Zsh installation failed. OMZ plugins cannot be installed.")
            phase_overall_success = False # OMZ is key for OMZ plugins
    else:
        print_info("Oh My Zsh already installed.")

    # Step 4.4: Install Oh My Zsh plugins
    # Proceed if OMZ is present (either pre-existing or installed now)
    if (user_home / ".oh-my-zsh").exists():
        print_step(4.4, "Installing Oh My Zsh plugins")
        if not _install_omz_plugins(username, user_home):
            print_warning("Installation of some Oh My Zsh plugins encountered issues.")
            # phase_overall_success = False # Non-critical if some plugins fail? User decision.
    elif omz_installed_this_run is False: # Explicitly if install failed
        print_info("Skipping OMZ plugin installation as OMZ is not installed or installation failed.")


    if phase_overall_success:
        print_success("\nPhase 4 (Terminal Enhancement) completed successfully.")
        print_info("Remember to update your ~/.zshrc to enable new Oh My Zsh plugins and ensure PATH is correct.")
        print_info("A new terminal session will be required for all changes to take effect.")
    else:
        print_warning("\nPhase 4 (Terminal Enhancement) completed with some errors or warnings.")
    
    return phase_overall_success