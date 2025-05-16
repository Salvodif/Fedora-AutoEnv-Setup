# Fedora-AutoEnv-Setup/scripts/phase4_gnome_configuration.py

import subprocess
import sys
import os
import shutil
import shlex 
import tempfile # Keep for _install_git_extension if it still uses it internally
from pathlib import Path
from typing import Optional, Dict, List

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils

# --- Constants ---
GEXT_CLI_MODULE = "gnome_extensions_cli.cli" 

# --- Helper Functions ---

def _get_target_user() -> Optional[str]:
    # (Keep this function as is from previous version)
    if os.geteuid() == 0: 
        target_user = os.environ.get("SUDO_USER")
        if not target_user:
            con.print_error("Script is running as root, but SUDO_USER is not set...")
            return None
        try:
            system_utils.run_command(["id", "-u", target_user], capture_output=True, check=True, print_fn_info=con.print_info)
        except (subprocess.CalledProcessError, FileNotFoundError):
            con.print_error(f"User '{target_user}' (from SUDO_USER) does not appear to be a valid system user.")
            return None
        return target_user
    else:
        current_user = os.getlogin()
        con.print_warning(f"Script not root. Assuming current user '{current_user}' for GNOME configs...")
        return current_user

def _get_user_home(username: str) -> Optional[Path]:
    # (Keep this function as is from previous version)
    try:
        proc = system_utils.run_command(["getent", "passwd", username], capture_output=True, check=True, print_fn_info=con.print_info)
        home_dir_str = proc.stdout.strip().split(":")[5]
        if not home_dir_str: return None
        return Path(home_dir_str)
    except Exception as e:
        con.print_error(f"Error getting home dir for '{username}': {e}")
        return None

def _install_dnf_packages_ph4(packages: List[str]) -> bool:
    # (Keep this function as is from previous version, ensuring --allowerasing)
    if not packages:
        con.print_info("No DNF packages specified for Phase 4.")
        return True
    con.print_sub_step(f"Installing DNF packages: {', '.join(packages)}")
    try:
        cmd = ["sudo", "dnf", "install", "-y", "--allowerasing"] + packages
        system_utils.run_command(cmd, capture_output=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step)
        con.print_success(f"DNF packages installed/verified: {', '.join(packages)}")
        return True
    except Exception: 
        return False

def _install_pip_packages_ph4(packages: List[str], target_user: str) -> bool:
    """Installs a list of pip packages for the target user (--user)."""
    if not packages:
        con.print_info("No pip packages specified for installation in Phase 4.")
        return True

    con.print_sub_step(f"Installing pip packages for user '{target_user}': {', '.join(packages)}")
    all_success = True
    for package_name in packages:
        con.print_info(f"Installing pip package '{package_name}' for user '{target_user}'...")
        # Ensure python3-pip is installed (should be done by Phase 2 or earlier)
        # We could add a check for pip3 availability here if desired.
        install_cmd = f"python3 -m pip install --user --upgrade {shlex.quote(package_name)}"
        try:
            system_utils.run_command(
                install_cmd, 
                run_as_user=target_user, 
                shell=True, # shell=True needed for complex commands if any, but simple here
                capture_output=True, 
                check=True,
                print_fn_info=con.print_info, 
                print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step
            )
            con.print_success(f"Pip package '{package_name}' installed/updated successfully for user '{target_user}'.")
        except FileNotFoundError: # python3 or pip not found
            con.print_error(f"'python3' or 'pip' command not found for user '{target_user}'. Cannot install '{package_name}'.")
            con.print_info("Please ensure 'python3-pip' is installed system-wide (e.g., in Phase 2).")
            all_success = False
            break # Stop if pip is missing
        except Exception as e:
            con.print_error(f"Failed to install pip package '{package_name}' for user '{target_user}': {e}")
            all_success = False
    return all_success

def _verify_gext_cli_usability(target_user: str) -> bool:
    """Verifies if gnome-extensions-cli is usable by the target user."""
    con.print_info(f"Verifying gnome-extensions-cli usability for user '{target_user}'...")
    check_cmd = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} --version"
    try:
        system_utils.run_command(
            check_cmd, run_as_user=target_user, shell=True, capture_output=True, check=True,
            print_fn_info=con.print_info
        )
        con.print_success(f"gnome-extensions-cli is available and usable for user '{target_user}'.")
        return True
    except Exception as e:
        con.print_error(f"gnome-extensions-cli verification failed for user '{target_user}': {e}")
        con.print_info(f"Attempted to run: {check_cmd}")
        return False

# _install_ego_extension and _install_git_extension remain the same as the previous "complete and correct" version
# Make sure they are present in your actual file. I'll include them here for completeness.

def _install_ego_extension(ext_name: str, ext_cfg: Dict, target_user: str) -> bool:
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
        system_utils.run_command(install_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error)
        con.print_success(f"EGO extension '{pretty_name}' installed successfully.")
        con.print_info(f"Attempting to enable EGO extension '{pretty_name}' (UUID: {uuid})...")
        enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid)}"
        system_utils.run_command(enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error)
        con.print_success(f"EGO extension '{pretty_name}' (UUID: {uuid}) enabled successfully.")
        return True
    except subprocess.CalledProcessError as e:
        err_lower = str(e).lower(); stderr_lower = e.stderr.lower() if e.stderr else ""
        if "already enabled" in err_lower or "already enabled" in stderr_lower:
            con.print_info(f"Extension '{pretty_name}' was already enabled."); return True 
        if "already installed" in err_lower or "already installed" in stderr_lower:
            con.print_info(f"Extension '{pretty_name}' was already installed. Attempting to enable...")
            try:
                enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid)}"
                system_utils.run_command(enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error)
                con.print_success(f"EGO extension '{pretty_name}' (UUID: {uuid}) enabled successfully."); return True
            except Exception as e_enable:
                con.print_error(f"Failed to enable EGO extension '{pretty_name}' after 'already installed': {e_enable}"); return False
        con.print_error(f"Failed to install or enable EGO extension '{pretty_name}': {e}"); return False
    except Exception as e:
        con.print_error(f"An unexpected error occurred with EGO extension '{pretty_name}': {e}"); return False

def _install_git_extension(ext_name: str, ext_cfg: Dict, target_user: str) -> bool:
    git_url = ext_cfg.get("url"); install_script_name = ext_cfg.get("install_script") 
    uuid_to_enable = ext_cfg.get("uuid_to_enable"); pretty_name = ext_cfg.get("name", ext_name)
    if not git_url or not install_script_name:
        con.print_error(f"Missing 'url' or 'install_script' for Git extension '{pretty_name}'. Skipping."); return False
    con.print_info(f"Attempting to install Git extension '{pretty_name}' from {git_url} for user '{target_user}'.")
    install_script_command_part = ""
    if install_script_name.lower() == "make install": install_script_command_part = "make install"
    elif install_script_name.lower() == "make": install_script_command_part = "make"
    elif install_script_name.endswith(".sh"): install_script_command_part = f"./{shlex.quote(install_script_name)}"
    else: install_script_command_part = shlex.quote(install_script_name)
    repo_name_from_url = Path(git_url).name.removesuffix(".git") if Path(git_url).name.endswith(".git") else Path(git_url).name
    script_to_run_as_user = f"""
        set -e
        TMP_EXT_DIR=$(mktemp -d -t gnome_ext_{shlex.quote(ext_name)}_XXXXXX)
        trap 'echo "Cleaning up $TMP_EXT_DIR for {shlex.quote(pretty_name)}"; rm -rf "$TMP_EXT_DIR"' EXIT
        echo "Cloning {shlex.quote(git_url)} into $TMP_EXT_DIR/{shlex.quote(repo_name_from_url)} (as user $(whoami))..."
        git clone --depth=1 {shlex.quote(git_url)} "$TMP_EXT_DIR/{shlex.quote(repo_name_from_url)}"
        cd "$TMP_EXT_DIR/{shlex.quote(repo_name_from_url)}"
        echo "Current directory for install: $(pwd)"; echo "Running install script command: {install_script_command_part}..."
        if [ -f {shlex.quote(install_script_name)} ] && [[ "{install_script_name}" == *.sh ]]; then
            chmod +x {shlex.quote(install_script_name)}
        fi
        dbus-run-session -- {install_script_command_part}
        echo "Install script for {shlex.quote(pretty_name)} finished."
    """
    try:
        con.print_sub_step(f"Executing installation script for '{pretty_name}' as user '{target_user}'.")
        system_utils.run_command(script_to_run_as_user, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step)
        con.print_success(f"Git extension '{pretty_name}' installed successfully via script.")
        if uuid_to_enable:
            con.print_info(f"Attempting to enable '{pretty_name}' (UUID: {uuid_to_enable})...")
            enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid_to_enable)}"
            system_utils.run_command(enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error)
            con.print_success(f"Git extension '{pretty_name}' (UUID: {uuid_to_enable}) enabled successfully.")
        else: con.print_info(f"No 'uuid_to_enable' specified for '{pretty_name}'.")
        return True
    except FileNotFoundError as e: 
        con.print_error(f"File not found for Git ext '{pretty_name}': {e}. Is git/mktemp missing for '{target_user}'?"); return False
    except subprocess.CalledProcessError as e:
        err_lower = str(e).lower(); stderr_lower = e.stderr.lower() if e.stderr else ""
        if "already enabled" in err_lower or "already enabled" in stderr_lower:
            con.print_info(f"Extension '{pretty_name}' was already enabled."); return True 
        con.print_error(f"Failed to install/enable Git ext '{pretty_name}'. Review script output."); return False
    except Exception as e:
        con.print_error(f"Unexpected error installing Git ext '{pretty_name}': {e}"); return False

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
    _ = _get_user_home(target_user) # Call to get warning if not found, but not strictly used by all funcs.
        
    con.print_info(f"Running GNOME configurations for user: [bold cyan]{target_user}[/bold cyan]")

    # 1. Install DNF packages
    con.print_info("\nStep 1: Installing DNF packages for GNOME...")
    dnf_packages = phase4_config_data.get("dnf_packages", [])
    if dnf_packages:
        if not _install_dnf_packages_ph4(dnf_packages):
            overall_success = False
    else:
        con.print_info("No DNF packages specified for Phase 4 in configuration.")

    # 2. Install pip packages for the target user
    con.print_info(f"\nStep 2: Installing pip packages for user '{target_user}'...")
    pip_packages_to_install = phase4_config_data.get("pip_packages", []) # Read 'pip_packages' from YAML
    if pip_packages_to_install:
        if not _install_pip_packages_ph4(pip_packages_to_install, target_user):
            overall_success = False
            # If pip install fails, gext_cli might not be available.
    else:
        con.print_info("No pip packages specified for Phase 4 in configuration.")

    # 3. Verify gnome-extensions-cli usability (after attempting pip install)
    gext_cli_ready = False
    if "gnome-extensions-cli" in pip_packages_to_install or True: # Always verify if extensions are planned
        # The 'True' condition is a placeholder if you want to verify even if not in pip_packages (e.g. system installed)
        # For now, let's assume if 'gnome_extensions' are defined, we need to verify.
        if phase4_config_data.get("gnome_extensions"):
            gext_cli_ready = _verify_gext_cli_usability(target_user)
            if not gext_cli_ready:
                con.print_error("gnome-extensions-cli is not usable. GNOME extension installation will be skipped.")
                if phase4_config_data.get("gnome_extensions"): # If extensions were actually configured
                    overall_success = False 
        else: # No GNOME extensions configured, so CLI readiness is not critical for this phase.
            gext_cli_ready = True # Effectively skip if no extensions are to be installed
    
    # 4. Install GNOME Extensions (only if gext_cli_ready)
    if gext_cli_ready and phase4_config_data.get("gnome_extensions"):
        gnome_extensions_cfg = phase4_config_data.get("gnome_extensions", {})
        if gnome_extensions_cfg: # Check again in case it was empty
            con.print_info(f"\nStep 4: Installing and enabling GNOME Shell Extensions for user '{target_user}'...")
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
        # else: # This case is covered by the outer 'if phase4_config_data.get("gnome_extensions")'
            # con.print_info("No GNOME extensions listed in configuration for Phase 4.")
    elif not gext_cli_ready and phase4_config_data.get("gnome_extensions"):
         con.print_warning("Skipped GNOME extension installation due to gnome-extensions-cli setup/usability failure.")


    # 5. Install Flatpak applications (Step number adjusted)
    con.print_info("\nStep 5: Installing Flatpak applications (system-wide)...")
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