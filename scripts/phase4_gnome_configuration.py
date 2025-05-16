# Fedora-AutoEnv-Setup/scripts/phase4_gnome_configuration.py

import subprocess
import sys
import os
import shutil
import shlex # For shlex.quote
import tempfile
from pathlib import Path
from typing import Optional, Dict, List

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils

# --- Constants ---
GEXT_CLI_MODULE = "gnome_extensions_cli.cli" # Module path for `python3 -m gnome_extensions_cli.cli`

# --- Helper Functions ---

def _get_target_user() -> Optional[str]:
    """Determines the target user, typically from SUDO_USER when script is run as root."""
    if os.geteuid() == 0: # Script is running as root
        target_user = os.environ.get("SUDO_USER")
        if not target_user:
            con.print_error(
                "Script is running as root, but SUDO_USER environment variable is not set. "
                "Cannot determine the target user for GNOME configuration."
            )
            con.print_info("Tip: Run 'sudo ./install.py' from a regular user account with an active GUI session.")
            return None
        try:
            # Verify user exists
            system_utils.run_command(["id", "-u", target_user], capture_output=True, check=True, print_fn_info=con.print_info)
        except (subprocess.CalledProcessError, FileNotFoundError):
            con.print_error(f"The user '{target_user}' (from SUDO_USER) does not appear to be a valid system user.")
            return None
        return target_user
    else:
        # If not root, assume current user is the target, but warn that sudo might be needed by script
        current_user = os.getlogin()
        con.print_warning(
            f"Script is not running as root. Assuming current user '{current_user}' for GNOME configurations. "
            "Ensure this script is run with sudo for DNF/Flatpak system installs."
        )
        return current_user

def _get_user_home(username: str) -> Optional[Path]:
    """Gets the home directory of a specified user."""
    try:
        proc = system_utils.run_command(
            ["getent", "passwd", username], capture_output=True, check=True,
            print_fn_info=con.print_info # Minimal logging for this utility call
        )
        home_dir_str = proc.stdout.strip().split(":")[5]
        if not home_dir_str:
            con.print_error(f"Could not determine home directory for user '{username}'.")
            return None
        return Path(home_dir_str)
    except Exception as e:
        con.print_error(f"Error getting home directory for user '{username}': {e}")
        return None

def _check_or_install_gext_cli(target_user: str) -> bool:
    """
    Checks if gnome-extensions-cli is installed for the user via pip, installs it if not.
    Note: target_user_home is not strictly needed here anymore if $HOME is reliable.
    """
    con.print_sub_step(f"Checking/installing gnome-extensions-cli for user '{target_user}'...")

    # Check if already callable via python3 -m
    # Use dbus-run-session to ensure it has a D-Bus environment
    check_cmd = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} --version"
    try:
        system_utils.run_command(
            check_cmd, run_as_user=target_user, shell=True, capture_output=True, check=True,
            print_fn_info=con.print_info
        )
        con.print_info(f"gnome-extensions-cli is already available for user '{target_user}'.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        con.print_info(f"gnome-extensions-cli not found or not working for '{target_user}'. Attempting installation via pip.")

    # Install pip package for the user
    install_cmd = "python3 -m pip install --user --upgrade gnome-extensions-cli"
    try:
        system_utils.run_command(
            install_cmd, run_as_user=target_user, shell=True, capture_output=True, check=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"gnome-extensions-cli installed successfully for user '{target_user}' via pip.")
        
        # Verify installation
        system_utils.run_command(
            check_cmd, run_as_user=target_user, shell=True, capture_output=True, check=True,
            print_fn_info=con.print_info
        )
        con.print_info(f"gnome-extensions-cli confirmed working after installation for '{target_user}'.")
        return True
    except Exception as e:
        con.print_error(f"Failed to install or verify gnome-extensions-cli for user '{target_user}': {e}")
        con.print_error("Please ensure 'python3-pip' is installed system-wide and the user can run pip.")
        return False

def _install_dnf_packages_ph4(packages: List[str]) -> bool:
    """Installs DNF packages. Assumes sudo context or passwordless sudo for dnf."""
    if not packages:
        con.print_info("No DNF packages specified for Phase 4.")
        return True
    con.print_sub_step(f"Installing DNF packages: {', '.join(packages)}")
    try:
        # Adding --allowerasing for robustness, in case of minor conflicts.
        cmd = ["sudo", "dnf", "install", "-y", "--allowerasing"] + packages
        system_utils.run_command(
            cmd, capture_output=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"DNF packages installed/verified: {', '.join(packages)}")
        return True
    except Exception: # Error already logged
        return False

def _install_ego_extension(ext_name: str, ext_cfg: Dict, target_user: str) -> bool:
    """Installs and enables a GNOME extension from extensions.gnome.org (EGO)."""
    uuid = ext_cfg.get("uuid")
    numerical_id = ext_cfg.get("numerical_id")
    pretty_name = ext_cfg.get("name", ext_name)

    if not uuid:
        con.print_error(f"Missing 'uuid' for EGO extension '{pretty_name}'. Skipping.")
        return False

    install_target = str(numerical_id) if numerical_id else uuid
    con.print_info(f"Attempting to install EGO extension '{pretty_name}' (ID/UUID: {install_target}) for user '{target_user}'.")

    try:
        install_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} install {shlex.quote(install_target)}"
        system_utils.run_command(
            install_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error
        )
        con.print_success(f"EGO extension '{pretty_name}' installed successfully.")

        con.print_info(f"Attempting to enable EGO extension '{pretty_name}' (UUID: {uuid})...")
        enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid)}"
        system_utils.run_command(
            enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error
        )
        con.print_success(f"EGO extension '{pretty_name}' (UUID: {uuid}) enabled successfully.")
        return True
    except subprocess.CalledProcessError as e:
        # Check if it's an "already enabled" or "already installed" type of non-error
        err_lower = str(e).lower()
        stderr_lower = e.stderr.lower() if e.stderr else ""
        if "already enabled" in err_lower or "already enabled" in stderr_lower:
            con.print_info(f"Extension '{pretty_name}' was already enabled.")
            return True 
        if "already installed" in err_lower or "already installed" in stderr_lower:
            con.print_info(f"Extension '{pretty_name}' was already installed. Attempting to enable...")
            # Try enabling again, as install might have been skipped but enable is desired
            try:
                enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid)}"
                system_utils.run_command(
                    enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True,
                    print_fn_info=con.print_info, print_fn_error=con.print_error
                )
                con.print_success(f"EGO extension '{pretty_name}' (UUID: {uuid}) enabled successfully.")
                return True
            except Exception as e_enable:
                con.print_error(f"Failed to enable EGO extension '{pretty_name}' after 'already installed' message: {e_enable}")
                return False
        con.print_error(f"Failed to install or enable EGO extension '{pretty_name}': {e}")
        return False
    except Exception as e: # Catch other errors like FileNotFoundError for python3 -m ...
        con.print_error(f"An unexpected error occurred with EGO extension '{pretty_name}': {e}")
        return False


def _install_git_extension(ext_name: str, ext_cfg: Dict, target_user: str) -> bool:
    """Installs and enables a GNOME extension from a Git repository."""
    # target_user_home parameter removed as $HOME is used in script_to_run_as_user
    git_url = ext_cfg.get("url")
    install_script_name = ext_cfg.get("install_script") # e.g., "install.sh" or "make install"
    uuid_to_enable = ext_cfg.get("uuid_to_enable") 
    pretty_name = ext_cfg.get("name", ext_name)

    if not git_url or not install_script_name:
        con.print_error(f"Missing 'url' or 'install_script' for Git extension '{pretty_name}'. Skipping.")
        return False

    con.print_info(f"Attempting to install Git extension '{pretty_name}' from {git_url} for user '{target_user}'.")

    install_script_command_part = ""
    if install_script_name.lower() == "make install":
        install_script_command_part = "make install"
    elif install_script_name.lower() == "make":
        install_script_command_part = "make"
    elif install_script_name.endswith(".sh"):
        install_script_command_part = f"./{shlex.quote(install_script_name)}"
    else:
        con.print_warning(f"Install script '{install_script_name}' for '{pretty_name}' has an unrecognized format. Assuming it's directly executable relative to repo root.")
        install_script_command_part = shlex.quote(install_script_name) # Might need ./ prefix generally

    repo_name_from_url = Path(git_url).name.removesuffix(".git") if Path(git_url).name.endswith(".git") else Path(git_url).name

    # Script to be run by the target user in their own context
    script_to_run_as_user = f"""
        set -e
        # Create a temporary directory; mktemp places it in $TMPDIR if set, else /tmp
        # This directory will be owned by {target_user}
        TMP_EXT_DIR=$(mktemp -d -t gnome_ext_{shlex.quote(ext_name)}_XXXXXX)
        
        # Ensure cleanup of the temp directory on script exit (success or failure)
        trap 'echo "Cleaning up temporary directory $TMP_EXT_DIR for {shlex.quote(pretty_name)}"; rm -rf "$TMP_EXT_DIR"' EXIT

        echo "Cloning {shlex.quote(git_url)} into $TMP_EXT_DIR/{shlex.quote(repo_name_from_url)} (as user $(whoami))..."
        git clone --depth=1 {shlex.quote(git_url)} "$TMP_EXT_DIR/{shlex.quote(repo_name_from_url)}"
        
        cd "$TMP_EXT_DIR/{shlex.quote(repo_name_from_url)}"
        echo "Current directory for install: $(pwd)"
        echo "Running install script command: {install_script_command_part}..."
        
        # Make .sh scripts executable if they are not already
        if [ -f {shlex.quote(install_script_name)} ] && [[ "{install_script_name}" == *.sh ]]; then
            chmod +x {shlex.quote(install_script_name)}
        fi
        
        # Execute the install script within a D-Bus session for GSettings/GNOME Shell interaction
        dbus-run-session -- {install_script_command_part}
        
        echo "Install script for {shlex.quote(pretty_name)} finished."
    """

    try:
        # The system_utils.run_command will show the script_to_run_as_user if print_fn_info is verbose enough.
        # For multi-line scripts, it's better to log the intent here and let run_command log execution details.
        con.print_sub_step(f"Executing installation script for '{pretty_name}' as user '{target_user}'.")
        system_utils.run_command(
            script_to_run_as_user,
            run_as_user=target_user,
            shell=True, 
            capture_output=True, 
            check=True,
            print_fn_info=con.print_info, # Will show the (as user) bash -c <script>
            print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step # For STDOUT/STDERR of the script
        )
        con.print_success(f"Git extension '{pretty_name}' installed successfully via script.")

        if uuid_to_enable:
            con.print_info(f"Attempting to enable '{pretty_name}' (UUID: {uuid_to_enable})...")
            enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid_to_enable)}"
            system_utils.run_command(
                enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error
            )
            con.print_success(f"Git extension '{pretty_name}' (UUID: {uuid_to_enable}) enabled successfully.")
        else:
            con.print_info(f"No 'uuid_to_enable' specified for '{pretty_name}'. Manual check or enabling might be needed.")
        return True

    except FileNotFoundError as e: 
        con.print_error(f"File not found during Git extension installation for '{pretty_name}': {e}. Is git, mktemp, or a command within the install script missing for user '{target_user}'?")
        return False
    except subprocess.CalledProcessError as e:
        # run_command already prints STDOUT/STDERR of the failed user script.
        err_lower = str(e).lower()
        stderr_lower = e.stderr.lower() if e.stderr else ""
        if "already enabled" in err_lower or "already enabled" in stderr_lower: # Check if enable step failed due to already enabled
            con.print_info(f"Extension '{pretty_name}' was already enabled.")
            return True 
        con.print_error(f"Failed to install or enable Git extension '{pretty_name}'. Review script output above.")
        return False
    except Exception as e:
        con.print_error(f"An unexpected error occurred installing Git extension '{pretty_name}': {e}")
        return False

# --- Main Phase Function ---

def run_phase4(app_config: dict) -> bool:
    """Executes Phase 4: GNOME Configuration & Extensions."""
    con.print_step("PHASE 4: GNOME Configuration & Extensions")
    overall_success = True
    
    phase4_config_data = config_loader.get_phase_data(app_config, "phase4_gnome_configuration")
    if not phase4_config_data:
        con.print_warning("No configuration found for Phase 4. Skipping.")
        return True 

    target_user = _get_target_user()
    if not target_user:
        con.print_error("Cannot determine target user for GNOME configurations. Aborting Phase 4.")
        return False
    
    # target_user_home is not strictly needed by all helpers anymore, but good to have for context.
    target_user_home = _get_user_home(target_user) 
    if not target_user_home:
        # This is not fatal for all operations if $HOME is used, but good to warn.
        con.print_warning(f"Could not determine home directory for user '{target_user}'. Some operations might rely on it implicitly.")
        # For this phase, primary operations rely on run_as_user which sets $HOME.
        
    con.print_info(f"Running GNOME configurations for user: [bold cyan]{target_user}[/bold cyan]")

    # 1. Install DNF packages
    con.print_info("\nStep 1: Installing DNF packages for GNOME...")
    dnf_packages = phase4_config_data.get("dnf_packages", [])
    if dnf_packages: # Only run if there are packages specified
        if not _install_dnf_packages_ph4(dnf_packages):
            overall_success = False
            # _install_dnf_packages_ph4 logs specific errors
    else:
        con.print_info("No DNF packages specified for Phase 4 in configuration.")


    # 2. Check/Install gnome-extensions-cli via pip for the target user
    con.print_info("\nStep 2: Ensuring gnome-extensions-cli is available...")
    gext_cli_ready = _check_or_install_gext_cli(target_user) # Removed target_user_home here
    if not gext_cli_ready:
        con.print_error("gnome-extensions-cli setup failed. GNOME extension installation will be skipped.")
        # If extensions were configured, this should be considered a partial failure of the phase.
        if phase4_config_data.get("gnome_extensions"):
            overall_success = False 
    
    # 3. Install GNOME Extensions (only if gext_cli_ready)
    if gext_cli_ready:
        gnome_extensions_cfg = phase4_config_data.get("gnome_extensions", {})
        if gnome_extensions_cfg:
            con.print_info(f"\nStep 3: Installing and enabling GNOME Shell Extensions for user '{target_user}'...")
            extensions_success_all = True
            for ext_key_name, ext_config_dict in gnome_extensions_cfg.items():
                ext_type = ext_config_dict.get("type")
                ext_pretty_name = ext_config_dict.get("name", ext_key_name)
                con.print_sub_step(f"Processing extension: {ext_pretty_name} (Type: {ext_type})")

                success_current_ext = False
                if ext_type == "ego":
                    success_current_ext = _install_ego_extension(ext_key_name, ext_config_dict, target_user)
                elif ext_type == "git":
                    success_current_ext = _install_git_extension(ext_key_name, ext_config_dict, target_user)
                else:
                    con.print_warning(f"Unknown GNOME extension type '{ext_type}' for '{ext_pretty_name}'. Skipping.")
                    extensions_success_all = False 
                
                if not success_current_ext:
                    extensions_success_all = False 
            
            if not extensions_success_all:
                overall_success = False 
                con.print_warning("Some GNOME extensions could not be installed/enabled.")
            else:
                con.print_success("All specified GNOME extensions processed successfully.")
        else:
            con.print_info("No GNOME extensions listed in configuration for Phase 4.")
    elif phase4_config_data.get("gnome_extensions"): # If CLI failed AND extensions were planned
         con.print_warning("Skipped GNOME extension installation due to gnome-extensions-cli setup failure.")
         # overall_success is already False if this path is taken and extensions were specified.


    # 4. Install Flatpak applications
    con.print_info("\nStep 4: Installing Flatpak applications (system-wide)...")
    flatpak_apps_to_install = phase4_config_data.get("flatpak_apps", {})
    if flatpak_apps_to_install:
        if not system_utils.install_flatpak_apps(
            apps_to_install=flatpak_apps_to_install,
            system_wide=True, 
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step
        ):
            overall_success = False
            con.print_error("Phase 4 Flatpak installation encountered issues.")
    else:
        con.print_info("No Flatpak applications listed for installation in Phase 4.")

    if overall_success:
        con.print_success("Phase 4: GNOME Configuration & Extensions completed successfully.")
    else:
        con.print_error("Phase 4: GNOME Configuration & Extensions completed with errors. Please review the output.")
    
    return overall_success