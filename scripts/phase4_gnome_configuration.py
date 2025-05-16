# Fedora-AutoEnv-Setup/scripts/phase4_gnome_configuration.py

import subprocess
import sys
import os
import shutil
import shlex 
import tempfile 
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
# _get_target_user, _get_user_home, _install_dnf_packages_ph4, 
# _install_pip_packages_ph4, _verify_gext_cli_usability,
# _install_ego_extension, _install_git_extension
# (These functions remain as per the last complete version)

def _get_target_user() -> Optional[str]:
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
    try:
        proc = system_utils.run_command(["getent", "passwd", username], capture_output=True, check=True, print_fn_info=con.print_info)
        home_dir_str = proc.stdout.strip().split(":")[5]
        if not home_dir_str: return None
        return Path(home_dir_str)
    except Exception as e:
        con.print_error(f"Error getting home dir for '{username}': {e}")
        return None

def _install_dnf_packages_ph4(packages: List[str]) -> bool:
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
    if not packages:
        con.print_info("No pip packages specified for installation in Phase 4.")
        return True
    con.print_sub_step(f"Installing pip packages for user '{target_user}': {', '.join(packages)}")
    all_success = True
    for package_name in packages:
        con.print_info(f"Installing pip package '{package_name}' for user '{target_user}'...")
        install_cmd = f"python3 -m pip install --user --upgrade {shlex.quote(package_name)}"
        try:
            system_utils.run_command(install_cmd, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step)
            con.print_success(f"Pip package '{package_name}' installed/updated successfully for user '{target_user}'.")
        except FileNotFoundError:
            con.print_error(f"'python3' or 'pip' command not found for user '{target_user}'. Cannot install '{package_name}'.")
            all_success = False; break
        except Exception as e:
            con.print_error(f"Failed to install pip package '{package_name}' for user '{target_user}': {e}")
            all_success = False
    return all_success

def _verify_gext_cli_usability(target_user: str) -> bool:
    con.print_info(f"Verifying gnome-extensions-cli usability for user '{target_user}'...")
    check_cmd = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} --version"
    try:
        system_utils.run_command(check_cmd, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info)
        con.print_success(f"gnome-extensions-cli is available and usable for user '{target_user}'.")
        return True
    except Exception as e:
        con.print_error(f"gnome-extensions-cli verification failed for user '{target_user}': {e}")
        return False

def _install_ego_extension(ext_name: str, ext_cfg: Dict, target_user: str) -> bool:
    uuid = ext_cfg.get("uuid"); numerical_id = ext_cfg.get("numerical_id"); pretty_name = ext_cfg.get("name", ext_name)
    if not uuid: con.print_error(f"Missing 'uuid' for EGO ext '{pretty_name}'. Skip."); return False
    install_target = str(numerical_id) if numerical_id else uuid
    con.print_info(f"Install EGO ext '{pretty_name}' (ID/UUID: {install_target}) for '{target_user}'.")
    try:
        install_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} install {shlex.quote(install_target)}"
        system_utils.run_command(install_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error)
        con.print_success(f"EGO ext '{pretty_name}' installed."); con.print_info(f"Enable EGO ext '{pretty_name}' (UUID: {uuid})...")
        enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid)}"
        system_utils.run_command(enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error)
        con.print_success(f"EGO ext '{pretty_name}' (UUID: {uuid}) enabled."); return True
    except subprocess.CalledProcessError as e:
        err_lower = str(e).lower(); stderr_lower = e.stderr.lower() if e.stderr else ""
        if "already enabled" in err_lower or "already enabled" in stderr_lower: con.print_info(f"Ext '{pretty_name}' already enabled."); return True 
        if "already installed" in err_lower or "already installed" in stderr_lower:
            con.print_info(f"Ext '{pretty_name}' already installed. Try enable...")
            try:
                enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid)}"
                system_utils.run_command(enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True,print_fn_info=con.print_info,print_fn_error=con.print_error)
                con.print_success(f"EGO ext '{pretty_name}' (UUID: {uuid}) enabled."); return True
            except Exception as e_enable: con.print_error(f"Failed to enable EGO ext '{pretty_name}' after 'already installed': {e_enable}"); return False
        con.print_error(f"Failed EGO ext '{pretty_name}': {e}"); return False
    except Exception as e: con.print_error(f"Unexpected error EGO ext '{pretty_name}': {e}"); return False

def _install_git_extension(ext_name: str, ext_cfg: Dict, target_user: str) -> bool:
    git_url = ext_cfg.get("url"); install_script_name = ext_cfg.get("install_script") 
    uuid_to_enable = ext_cfg.get("uuid_to_enable"); pretty_name = ext_cfg.get("name", ext_name)
    if not git_url or not install_script_name: con.print_error(f"Missing 'url'/'script' for Git ext '{pretty_name}'. Skip."); return False
    con.print_info(f"Install Git ext '{pretty_name}' from {git_url} for '{target_user}'.")
    install_script_command_part = ""
    if install_script_name.lower() == "make install": install_script_command_part = "make install"
    elif install_script_name.lower() == "make": install_script_command_part = "make"
    elif install_script_name.endswith(".sh"): install_script_command_part = f"./{shlex.quote(install_script_name)}"
    else: install_script_command_part = shlex.quote(install_script_name)
    repo_name_from_url = Path(git_url).name.removesuffix(".git") if Path(git_url).name.endswith(".git") else Path(git_url).name
    shell_safe_pretty_name = shlex.quote(pretty_name)
    script_to_run_as_user = f"""
        set -e; SHELL_PRETTY_NAME={shell_safe_pretty_name}
        TMP_EXT_DIR=$(mktemp -d -t gnome_ext_{shlex.quote(ext_name)}_XXXXXX)
        trap 'echo "Cleaning up $TMP_EXT_DIR for $SHELL_PRETTY_NAME"; rm -rf "$TMP_EXT_DIR"' EXIT
        echo "Cloning {shlex.quote(git_url)} into $TMP_EXT_DIR/{shlex.quote(repo_name_from_url)} (user $(whoami))..."
        git clone --depth=1 {shlex.quote(git_url)} "$TMP_EXT_DIR/{shlex.quote(repo_name_from_url)}"
        cd "$TMP_EXT_DIR/{shlex.quote(repo_name_from_url)}"
        echo "CWD for install: $(pwd)"; echo "Run install script: {install_script_command_part}..."
        if [ -f "{install_script_name}" ] && [[ "{install_script_name}" == *.sh ]]; then chmod +x "{install_script_name}"; fi
        dbus-run-session -- {install_script_command_part}
        echo "Install script for $SHELL_PRETTY_NAME finished."
    """
    try:
        con.print_sub_step(f"Exec install script for '{pretty_name}' as '{target_user}'.")
        system_utils.run_command(script_to_run_as_user, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step)
        con.print_success(f"Git ext '{pretty_name}' installed via script.")
        if uuid_to_enable:
            con.print_info(f"Enable '{pretty_name}' (UUID: {uuid_to_enable})...")
            enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid_to_enable)}"
            system_utils.run_command(enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error)
            con.print_success(f"Git ext '{pretty_name}' (UUID: {uuid_to_enable}) enabled.")
        else: con.print_info(f"No 'uuid_to_enable' for '{pretty_name}'.")
        return True
    except FileNotFoundError as e: con.print_error(f"File not found Git ext '{pretty_name}': {e}. git/mktemp missing?"); return False
    except subprocess.CalledProcessError as e:
        err_lower = str(e).lower(); stderr_lower = e.stderr.lower() if e.stderr else ""
        if "already enabled" in err_lower or "already enabled" in stderr_lower: con.print_info(f"Ext '{pretty_name}' already enabled."); return True 
        con.print_error(f"Failed Git ext '{pretty_name}'. Review output."); return False
    except Exception as e: con.print_error(f"Unexpected error Git ext '{pretty_name}': {e}"); return False

def _set_dark_theme_preference(target_user: str) -> bool:
    """Sets the GNOME desktop interface color-scheme to 'prefer-dark'."""
    con.print_sub_step(f"Setting color-scheme to 'prefer-dark' for user '{target_user}'...")
    gsettings_cmd = "gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'"
    
    # This command needs to run within the user's D-Bus session to take effect.
    # Wrapping with dbus-run-session ensures this, similar to gnome-extensions-cli calls.
    full_cmd = f"dbus-run-session -- {gsettings_cmd}"
    try:
        system_utils.run_command(
            full_cmd,
            run_as_user=target_user,
            shell=True, # for dbus-run-session and the gsettings command string
            capture_output=True, # gsettings set is usually silent on success
            check=True,
            print_fn_info=con.print_info,
            print_fn_error=con.print_error
        )
        con.print_success(f"Color-scheme set to 'prefer-dark' for user '{target_user}'.")
        return True
    except FileNotFoundError: # gsettings or dbus-run-session not found
        con.print_error(f"'gsettings' or 'dbus-run-session' command not found for user '{target_user}'. Cannot set dark theme.")
        return False
    except Exception as e:
        con.print_error(f"Failed to set dark theme for user '{target_user}': {e}")
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
    
    _ = _get_user_home(target_user) 
        
    con.print_info(f"Running GNOME configurations for user: [bold cyan]{target_user}[/bold cyan]")

    # 1. Install DNF packages
    con.print_info("\nStep 1: Installing DNF packages for GNOME...")
    dnf_packages = phase4_config_data.get("dnf_packages", [])
    if dnf_packages:
        if not _install_dnf_packages_ph4(dnf_packages): overall_success = False
    else: con.print_info("No DNF packages specified for Phase 4 in configuration.")

    # 2. Install pip packages
    con.print_info(f"\nStep 2: Installing pip packages for user '{target_user}'...")
    pip_packages_to_install = phase4_config_data.get("pip_packages", [])
    if pip_packages_to_install:
        if not _install_pip_packages_ph4(pip_packages_to_install, target_user): overall_success = False
    else: con.print_info("No pip packages specified for Phase 4 in configuration.")

    # 3. Verify gnome-extensions-cli usability
    gext_cli_ready = False
    if phase4_config_data.get("gnome_extensions"): # Only verify if we plan to install extensions
        gext_cli_ready = _verify_gext_cli_usability(target_user)
        if not gext_cli_ready:
            con.print_error("gnome-extensions-cli not usable. GNOME extension installation will be skipped.")
            overall_success = False # This is a failure if extensions were specified
    else: # No GNOME extensions configured, so CLI readiness is not critical for this phase.
        gext_cli_ready = True 

    # 4. Install GNOME Extensions
    if gext_cli_ready and phase4_config_data.get("gnome_extensions"):
        gnome_extensions_cfg = phase4_config_data.get("gnome_extensions", {})
        if gnome_extensions_cfg: 
            con.print_info(f"\nStep 4: Installing and enabling GNOME Shell Extensions for user '{target_user}'...")
            extensions_success_all = True
            for ext_key_name, ext_config_dict in gnome_extensions_cfg.items():
                ext_type = ext_config_dict.get("type"); pretty_name = ext_config_dict.get("name", ext_key_name)
                con.print_sub_step(f"Processing extension: {pretty_name} (Type: {ext_type})")
                success_current_ext = False
                if ext_type == "ego": success_current_ext = _install_ego_extension(ext_key_name, ext_config_dict, target_user)
                elif ext_type == "git": success_current_ext = _install_git_extension(ext_key_name, ext_config_dict, target_user)
                else: con.print_warning(f"Unknown GNOME ext type '{ext_type}' for '{pretty_name}'. Skip."); extensions_success_all = False 
                if not success_current_ext: extensions_success_all = False 
            if not extensions_success_all: overall_success = False; con.print_warning("Some GNOME extensions failed.")
            else: con.print_success("All specified GNOME extensions processed.")
    elif not gext_cli_ready and phase4_config_data.get("gnome_extensions"):
         con.print_warning("Skipped GNOME extension installation due to gnome-extensions-cli setup/usability failure.")

    # 5. Install Flatpak applications
    con.print_info("\nStep 5: Installing Flatpak applications (system-wide)...")
    flatpak_apps_to_install = phase4_config_data.get("flatpak_apps", {})
    if flatpak_apps_to_install:
        if not system_utils.install_flatpak_apps(apps_to_install=flatpak_apps_to_install, system_wide=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step):
            overall_success = False; con.print_error("Phase 4 Flatpak installation encountered issues.")
    else: con.print_info("No Flatpak applications listed for installation in Phase 4.")

    # 6. Set dark theme preference
    con.print_info("\nStep 6: Setting system theme preference...")
    if not _set_dark_theme_preference(target_user):
        # This is a cosmetic preference, so a failure here might not make the whole phase fail,
        # but it's good to note it. User can decide if this is critical.
        con.print_warning(f"Failed to set dark theme preference for user '{target_user}'.")
        # overall_success = False # Uncomment if this should be a critical failure

    if overall_success:
        con.print_success("Phase 4: GNOME Configuration & Extensions completed successfully.")
    else:
        con.print_error("Phase 4: GNOME Configuration & Extensions completed with errors. Please review the output.")
    
    return overall_success