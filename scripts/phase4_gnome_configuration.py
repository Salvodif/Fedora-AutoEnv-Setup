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

# --- Helper Functions (some copied/adapted from phase3_terminal_enhancement) ---

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

def _check_or_install_gext_cli(target_user: str, target_user_home: Path) -> bool:
    """Checks if gnome-extensions-cli is installed for the user, installs it via pip if not."""
    con.print_sub_step(f"Checking/installing gnome-extensions-cli for user '{target_user}'...")

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

    install_cmd = "python3 -m pip install --user --upgrade gnome-extensions-cli"
    try:
        system_utils.run_command(
            install_cmd, run_as_user=target_user, shell=True, capture_output=True, check=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"gnome-extensions-cli installed successfully for user '{target_user}' via pip.")
        
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
        cmd = ["sudo", "dnf", "install", "-y"] + packages
        system_utils.run_command(
            cmd, capture_output=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"DNF packages installed: {', '.join(packages)}")
        return True
    except Exception: # Error already logged
        return False

def _install_flatpak_apps_ph4(apps_dict: Dict[str, str]) -> bool:
    """Installs Flatpak applications system-wide. Assumes sudo context."""
    if not apps_dict:
        con.print_info("No Flatpak applications specified for Phase 4.")
        return True
    
    all_success = True
    app_ids = list(apps_dict.keys())
    con.print_sub_step(f"Installing Flatpak applications (system-wide): {', '.join(app_ids)}")

    for app_id, app_name in apps_dict.items():
        con.print_info(f"Installing '{app_name}' ({app_id})...")
        try:
            cmd = ["sudo", "flatpak", "install", "--system", "--noninteractive", "--or-update", "flathub", app_id]
            system_utils.run_command(
                cmd, capture_output=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
            )
            con.print_success(f"Flatpak app '{app_name}' ({app_id}) installed/updated successfully.")
        except FileNotFoundError:
            con.print_error("'flatpak' command not found. Is Flatpak installed and Flathub remote added (Phase 1)?")
            all_success = False
            break 
        except Exception: 
            con.print_warning(f"Failed to install Flatpak app '{app_name}' ({app_id}).")
            all_success = False
    return all_success

def _install_ego_extension(ext_name: str, ext_cfg: Dict, target_user: str) -> bool:
    """Installs and enables a GNOME extension from extensions.gnome.org (EGO)."""
    uuid = ext_cfg.get("uuid")
    numerical_id = ext_cfg.get("numerical_id")
    pretty_name = ext_cfg.get("name", ext_name)

    if not uuid:
        con.print_error(f"Missing 'uuid' for EGO extension '{pretty_name}'. Skipping.")
        return False

    install_target = str(numerical_id) if numerical_id else uuid
    con.print_info(f"Attempting to install EGO extension '{pretty_name}' (ID: {install_target}) for user '{target_user}'.")

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
    except Exception as e:
        con.print_error(f"Failed to install or enable EGO extension '{pretty_name}': {e}")
        # Check if it's an "already enabled" type of non-error, though check=True usually means real failure
        if "already enabled" in str(e).lower() and isinstance(e, subprocess.CalledProcessError) and e.stderr:
             if "already enabled" in e.stderr.lower():
                con.print_info(f"Extension '{pretty_name}' was already enabled.")
                return True # Count as success if already enabled
        return False

def _install_git_extension(ext_name: str, ext_cfg: Dict, target_user: str, target_user_home: Path) -> bool:
    """Installs and enables a GNOME extension from a Git repository."""
    git_url = ext_cfg.get("url")
    install_script_name = ext_cfg.get("install_script")
    uuid_to_enable = ext_cfg.get("uuid_to_enable") 
    pretty_name = ext_cfg.get("name", ext_name)

    if not git_url or not install_script_name:
        con.print_error(f"Missing 'url' or 'install_script' for Git extension '{pretty_name}'. Skipping.")
        return False

    con.print_info(f"Attempting to install Git extension '{pretty_name}' from {git_url} for user '{target_user}'.")

    try:
        with tempfile.TemporaryDirectory(prefix=f"gnome_ext_{ext_name}_") as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            repo_dir_name = Path(git_url).stem 
            repo_path = tmp_dir / repo_dir_name

            clone_cmd = ["git", "clone", "--depth=1", git_url, str(repo_path)]
            system_utils.run_command(
                clone_cmd, run_as_user=target_user, capture_output=True, check=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error
            )
            con.print_info(f"Repository for '{pretty_name}' cloned to temporary location.")

            install_script_path = repo_path / install_script_name
            if not system_utils.run_command(f"test -f {shlex.quote(str(install_script_path))}", run_as_user=target_user, shell=True, check=False).returncode == 0:
                 con.print_error(f"Install script '{install_script_name}' not found in cloned repo for '{pretty_name}'. Looked for: {install_script_path}")
                 return False

            if install_script_name.endswith(".sh"):
                 system_utils.run_command(f"chmod +x {shlex.quote(str(install_script_path))}", run_as_user=target_user, shell=True, check=True)
            
            install_cmd_str_in_repo: str
            if install_script_name.endswith(".sh"):
                install_cmd_str_in_repo = f"./{install_script_name}"
            else: 
                install_cmd_str_in_repo = install_script_name
            
            full_install_script_cmd = f"dbus-run-session -- {install_cmd_str_in_repo}"

            system_utils.run_command(
                full_install_script_cmd, run_as_user=target_user, shell=True,
                cwd=repo_path, capture_output=True, check=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error
            )
            con.print_success(f"Git extension '{pretty_name}' installed via script '{install_script_name}'.")

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
        con.print_error(f"File not found during Git extension installation for '{pretty_name}': {e}. Is git installed?")
        return False
    except subprocess.CalledProcessError as e:
        # Specific check for "already enabled" which might come from the enable step
        if "already enabled" in str(e).lower() and e.stderr and "already enabled" in e.stderr.lower():
            con.print_info(f"Extension '{pretty_name}' was already enabled.")
            return True # Count as success
        con.print_error(f"Failed to install or enable Git extension '{pretty_name}': {e}")
        if e.stdout: con.print_error(f"STDOUT: {e.stdout.strip()}")
        if e.stderr: con.print_error(f"STDERR: {e.stderr.strip()}")
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
    
    target_user_home = _get_user_home(target_user)
    if not target_user_home:
        con.print_error(f"Cannot determine home directory for user '{target_user}'. Aborting Phase 4.")
        return False
        
    con.print_info(f"Running GNOME configurations for user: [bold cyan]{target_user}[/bold cyan] (Home: {target_user_home})")

    con.print_info("\nStep 1: Installing DNF packages for GNOME...")
    dnf_packages = phase4_config_data.get("dnf_packages", [])
    if not _install_dnf_packages_ph4(dnf_packages):
        overall_success = False
        con.print_error("Failed to install some DNF packages for Phase 4.")

    con.print_info("\nStep 2: Ensuring gnome-extensions-cli is available...")
    gext_cli_ready = _check_or_install_gext_cli(target_user, target_user_home)
    if not gext_cli_ready:
        con.print_error("gnome-extensions-cli setup failed. GNOME extension installation will be skipped.")
        # Not setting overall_success to False here yet, other parts might succeed.
        # But if extensions are critical, this could be overall_success = False

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
                    success_current_ext = _install_git_extension(ext_key_name, ext_config_dict, target_user, target_user_home)
                else:
                    con.print_warning(f"Unknown GNOME extension type '{ext_type}' for '{ext_pretty_name}'. Skipping.")
                    extensions_success_all = False 
                
                if not success_current_ext:
                    extensions_success_all = False 
            
            if not extensions_success_all:
                overall_success = False # If any extension step failed, mark overall phase as problematic
                con.print_warning("Some GNOME extensions could not be installed/enabled.")
            else:
                con.print_success("All specified GNOME extensions processed successfully.")
        else:
            con.print_info("No GNOME extensions listed in configuration for Phase 4.")
    else: # gext_cli_ready is False
        if phase4_config_data.get("gnome_extensions"): # If there were extensions to install
            overall_success = False # Mark as failure if extensions were specified but CLI tool failed
            con.print_warning("Skipped GNOME extension installation due to gnome-extensions-cli setup failure.")


    con.print_info("\nStep 4: Installing Flatpak applications (system-wide)...")
    flatpak_apps = phase4_config_data.get("flatpak_apps", {})
    if flatpak_apps: # Only run if there are apps specified
        if not _install_flatpak_apps_ph4(flatpak_apps):
            overall_success = False
            con.print_error("Failed to install some Flatpak applications for Phase 4.")
    else:
        con.print_info("No Flatpak applications listed for installation in Phase 4.")


    if overall_success:
        con.print_success("Phase 4: GNOME Configuration & Extensions completed successfully.")
    else:
        con.print_error("Phase 4: GNOME Configuration & Extensions completed with errors. Please review the output.")
    
    return overall_success