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

def _get_target_user() -> Optional[str]:
    """Determines the target user, typically from SUDO_USER when script is run as root."""
    if os.geteuid() == 0: 
        target_user = os.environ.get("SUDO_USER")
        if not target_user:
            con.print_error(
                "Script is running as root, but SUDO_USER environment variable is not set. "
                "Cannot determine the target user for GNOME configuration."
            )
            con.print_info("Tip: Run 'sudo ./install.py' from a regular user account with an active GUI session.")
            return None
        try:
            system_utils.run_command(["id", "-u", target_user], capture_output=True, check=True, print_fn_info=con.print_info)
        except (subprocess.CalledProcessError, FileNotFoundError):
            con.print_error(f"The user '{target_user}' (from SUDO_USER) does not appear to be a valid system user.")
            return None
        return target_user
    else:
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
            print_fn_info=con.print_info 
        )
        home_dir_str = proc.stdout.strip().split(":")[5]
        if not home_dir_str: 
            con.print_error(f"Could not determine home directory for user '{username}'.")
            return None
        return Path(home_dir_str)
    except Exception as e:
        con.print_error(f"Error getting home directory for user '{username}': {e}")
        return None

def _install_dnf_packages_ph4(packages: List[str]) -> bool:
    """Installs DNF packages for Phase 4."""
    if not packages:
        con.print_info("No DNF packages specified for Phase 4.")
        return True
    con.print_sub_step(f"Installing DNF packages: {', '.join(packages)}")
    try:
        cmd = ["sudo", "dnf", "install", "-y", "--allowerasing"] + packages
        system_utils.run_command(
            cmd, capture_output=True, 
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
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
        install_cmd = f"python3 -m pip install --user --upgrade {shlex.quote(package_name)}"
        try:
            system_utils.run_command(
                install_cmd, 
                run_as_user=target_user, 
                shell=True, 
                capture_output=True, 
                check=True,
                print_fn_info=con.print_info, 
                print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step
            )
            con.print_success(f"Pip package '{package_name}' installed/updated successfully for user '{target_user}'.")
        except FileNotFoundError: 
            con.print_error(f"'python3' or 'pip' command not found for user '{target_user}'. Cannot install '{package_name}'.")
            con.print_info("Please ensure 'python3-pip' is installed system-wide (e.g., in Phase 2).")
            all_success = False
            break 
        except Exception as e:
            con.print_error(f"Failed to install pip package '{package_name}' for user '{target_user}': {e}")
            all_success = False
    return all_success

def _verify_gext_cli_usability(target_user: str) -> bool:
    """Verifies if gnome-extensions-cli is usable by the target user."""
    con.print_info(f"Verifying gnome-extensions-cli usability for user '{target_user}'...")
    check_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} --version"
    try:
        system_utils.run_command(
            check_cmd_str, 
            run_as_user=target_user, 
            shell=True, 
            capture_output=True, 
            check=True,
            print_fn_info=con.print_info
        )
        con.print_success(f"gnome-extensions-cli is available and usable for user '{target_user}'.")
        return True
    except Exception as e:
        con.print_error(f"gnome-extensions-cli verification failed for user '{target_user}': {e}")
        con.print_info(f"Attempted to run: {check_cmd_str} (as {target_user})")
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
            install_cmd_str, run_as_user=target_user, shell=True, 
            capture_output=True, check=True, 
            print_fn_info=con.print_info, print_fn_error=con.print_error
        )
        con.print_success(f"EGO extension '{pretty_name}' installed successfully.")

        con.print_info(f"Attempting to enable EGO extension '{pretty_name}' (UUID: {uuid})...")
        enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid)}"
        system_utils.run_command(
            enable_cmd_str, run_as_user=target_user, shell=True, 
            capture_output=True, check=True, 
            print_fn_info=con.print_info, print_fn_error=con.print_error
        )
        con.print_success(f"EGO extension '{pretty_name}' (UUID: {uuid}) enabled successfully.")
        return True
    except subprocess.CalledProcessError as e:
        err_lower = str(e).lower()
        stderr_lower = e.stderr.lower() if e.stderr else ""
        if "already enabled" in err_lower or "already enabled" in stderr_lower:
            con.print_info(f"Extension '{pretty_name}' was already enabled.")
            return True 
        if "already installed" in err_lower or "already installed" in stderr_lower:
            con.print_info(f"Extension '{pretty_name}' was already installed. Attempting to enable...")
            try:
                enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid)}"
                system_utils.run_command(
                    enable_cmd_str, run_as_user=target_user, shell=True, 
                    capture_output=True, check=True,
                    print_fn_info=con.print_info,print_fn_error=con.print_error
                )
                con.print_success(f"EGO extension '{pretty_name}' (UUID: {uuid}) enabled successfully after 'already installed' message.")
                return True
            except Exception as e_enable:
                con.print_error(f"Failed to enable EGO extension '{pretty_name}' after 'already installed' message: {e_enable}")
                return False
        con.print_error(f"Failed to install or enable EGO extension '{pretty_name}': {e}")
        return False
    except Exception as e: 
        con.print_error(f"An unexpected error occurred with EGO extension '{pretty_name}': {e}")
        return False

def _install_git_extension(ext_name: str, ext_cfg: Dict, target_user: str) -> bool:
    """Installs and enables a GNOME extension from a Git repository."""
    git_url = ext_cfg.get("url")
    install_script_name = ext_cfg.get("install_script") 
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
        install_script_command_part = shlex.quote(install_script_name) 
    
    repo_name_from_url = Path(git_url).name.removesuffix(".git") if Path(git_url).name.endswith(".git") else Path(git_url).name
    shell_safe_pretty_name = shlex.quote(pretty_name)

    script_to_run_as_user = f"""
        set -e
        SHELL_PRETTY_NAME={shell_safe_pretty_name}
        TMP_EXT_DIR=$(mktemp -d -t gnome_ext_{shlex.quote(ext_name)}_XXXXXX)
        
        trap 'echo "Cleaning up temporary directory $TMP_EXT_DIR for $SHELL_PRETTY_NAME (user $(whoami))"; rm -rf "$TMP_EXT_DIR"' EXIT

        echo "Cloning {shlex.quote(git_url)} into $TMP_EXT_DIR/{shlex.quote(repo_name_from_url)} (as user $(whoami))..."
        git clone --depth=1 {shlex.quote(git_url)} "$TMP_EXT_DIR/{shlex.quote(repo_name_from_url)}"
        
        cd "$TMP_EXT_DIR/{shlex.quote(repo_name_from_url)}"
        echo "Current directory for install: $(pwd)"
        echo "Running install script command: {install_script_command_part}..."
        
        if [ -f "{install_script_name}" ] && [[ "{install_script_name}" == *.sh ]]; then
            chmod +x "{install_script_name}"
        fi
        
        dbus-run-session -- {install_script_command_part}
        
        echo "Install script for $SHELL_PRETTY_NAME finished."
    """
    try:
        con.print_sub_step(f"Executing installation script for '{pretty_name}' as user '{target_user}'.")
        system_utils.run_command(
            script_to_run_as_user, 
            run_as_user=target_user, 
            shell=True, 
            capture_output=True, 
            check=True, 
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"Git extension '{pretty_name}' installed successfully via script.")
        
        if uuid_to_enable:
            con.print_info(f"Attempting to enable '{pretty_name}' (UUID: {uuid_to_enable})...")
            enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid_to_enable)}"
            system_utils.run_command(
                enable_cmd_str, run_as_user=target_user, shell=True, 
                capture_output=True, check=True, 
                print_fn_info=con.print_info, print_fn_error=con.print_error
            )
            con.print_success(f"Git extension '{pretty_name}' (UUID: {uuid_to_enable}) enabled successfully.")
        else: 
            con.print_info(f"No 'uuid_to_enable' specified for '{pretty_name}'. Manual check or enabling might be needed.")
        return True
    except FileNotFoundError as e: 
        con.print_error(f"File not found during Git extension '{pretty_name}' install: {e}. Is git, mktemp, or a command in its install script missing for user '{target_user}'?")
        return False
    except subprocess.CalledProcessError as e:
        err_lower = str(e).lower()
        stderr_lower = e.stderr.lower() if e.stderr else ""
        if "already enabled" in err_lower or "already enabled" in stderr_lower:
            con.print_info(f"Extension '{pretty_name}' was already enabled.")
            return True 
        con.print_error(f"Failed to install or enable Git extension '{pretty_name}'. Review script output above.")
        return False
    except Exception as e:
        con.print_error(f"An unexpected error occurred installing Git extension '{pretty_name}': {e}")
        return False

def _set_dark_theme_preference(target_user: str) -> bool:
    """Sets the GNOME desktop interface color-scheme to 'prefer-dark' and attempts to set Adwaita-dark GTK theme."""
    con.print_sub_step(f"Attempting to set system appearance to dark mode for user '{target_user}'...")
    
    schema = "org.gnome.desktop.interface"
    
    # 1. Set color-scheme to prefer-dark
    color_scheme_key = "color-scheme"
    color_scheme_value = "prefer-dark" 
    
    con.print_info(f"Setting GSettings: {schema} {color_scheme_key} to '{color_scheme_value}' (as {target_user})")
    # Construct command as a list of arguments for dbus-run-session
    cmd_color_scheme = ["dbus-run-session", "--", "gsettings", "set", schema, color_scheme_key, color_scheme_value]
    
    success_color_scheme = False
    try:
        system_utils.run_command(
            cmd_color_scheme,
            run_as_user=target_user,
            shell=False, # dbus-run-session is the executable, args are passed directly
            capture_output=True,
            check=True, # Fail if this primary setting cannot be applied
            print_fn_info=con.print_info,
            print_fn_error=con.print_error
        )
        con.print_success(f"GSettings: '{schema} {color_scheme_key}' successfully set to '{color_scheme_value}'.")
        success_color_scheme = True
    except FileNotFoundError: 
        con.print_error(f"'gsettings' or 'dbus-run-session' command not found. Cannot set dark theme for '{target_user}'.")
        return False 
    except subprocess.CalledProcessError as e:
        con.print_error(f"Failed to set GSettings '{schema} {color_scheme_key}'. Command: {' '.join(e.cmd)}")
        if e.stdout: con.print_error(f"STDOUT: {e.stdout.strip()}")
        if e.stderr: con.print_error(f"STDERR: {e.stderr.strip()}")
        # This is considered a failure for setting the dark theme preference.
    except Exception as e:
        con.print_error(f"An unexpected error occurred while setting '{color_scheme_key}' for '{target_user}': {e}")
        # This is also a failure.

    # 2. Optionally, attempt to set GTK theme to Adwaita-dark for better consistency
    # This is a "best effort" and not critical if it fails, as 'prefer-dark' is the main switch.
    # We try this regardless of previous specific error, as long as gsettings was found.
    gtk_theme_key = "gtk-theme"
    gtk_theme_value = "Adwaita-dark" 

    con.print_info(f"Attempting to set GSettings: {schema} {gtk_theme_key} to '{gtk_theme_value}' (as {target_user})")
    cmd_gtk_theme = ["dbus-run-session", "--", "gsettings", "set", schema, gtk_theme_key, gtk_theme_value]
    try:
        system_utils.run_command(
            cmd_gtk_theme,
            run_as_user=target_user,
            shell=False, 
            capture_output=True,
            check=False, # Do not make the entire phase fail if Adwaita-dark isn't found or settable
            print_fn_info=con.print_info,
            print_fn_error=con.print_error 
        )
        con.print_info(f"Attempt to set GSettings '{gtk_theme_key}' to '{gtk_theme_value}' completed.")
    except FileNotFoundError:
        # This path is unlikely if the first gsettings call didn't hit it,
        # but included for theoretical completeness.
        con.print_warning(f"Could not attempt to set '{gtk_theme_key}' due to missing command (unexpected).")
    except Exception as e: # Includes CalledProcessError if check=True, but here check=False
        con.print_warning(f"Could not set '{gtk_theme_key}' for '{target_user}': {e}. This might be non-critical.")

    if success_color_scheme:
        con.print_info("GNOME dark mode preference applied. A logout/login or restart of GNOME Shell might be needed for changes to fully reflect everywhere.")
    else:
        con.print_warning("Setting primary dark mode (color-scheme) failed. Appearance might not change.")
        
    return success_color_scheme


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

    # Step 1: Install DNF packages
    con.print_info("\nStep 1: Installing DNF packages for GNOME...")
    dnf_packages = phase4_config_data.get("dnf_packages", [])
    if dnf_packages:
        if not _install_dnf_packages_ph4(dnf_packages): overall_success = False
    else: con.print_info("No DNF packages specified for Phase 4 in configuration.")

    # Step 2: Install pip packages
    con.print_info(f"\nStep 2: Installing pip packages for user '{target_user}'...")
    pip_packages_to_install = phase4_config_data.get("pip_packages", []) 
    if pip_packages_to_install:
        if not _install_pip_packages_ph4(pip_packages_to_install, target_user): overall_success = False
    else: con.print_info("No pip packages specified for Phase 4 in configuration.")

    # Step 3: Verify gnome-extensions-cli usability
    gext_cli_ready = False
    if phase4_config_data.get("gnome_extensions"): 
        gext_cli_ready = _verify_gext_cli_usability(target_user)
        if not gext_cli_ready:
            con.print_error("gnome-extensions-cli not usable. GNOME extension installation will be skipped.")
            overall_success = False 
    else: 
        gext_cli_ready = True 

    # Step 4: Install GNOME Extensions
    if gext_cli_ready and phase4_config_data.get("gnome_extensions"):
        gnome_extensions_cfg = phase4_config_data.get("gnome_extensions", {})
        if gnome_extensions_cfg: 
            con.print_info(f"\nStep 4: Installing and enabling GNOME Shell Extensions for user '{target_user}'...")
            extensions_success_all = True
            for ext_key__name, ext_config_dict in gnome_extensions_cfg.items(): # Renamed ext_key_name to avoid conflict
                ext_type = ext_config_dict.get("type"); pretty_name = ext_config_dict.get("name", ext_key_name) # Used ext_key_name from loop
                con.print_sub_step(f"Processing extension: {pretty_name} (Type: {ext_type})")
                success_current_ext = False
                if ext_type == "ego": success_current_ext = _install_ego_extension(ext_key_name, ext_config_dict, target_user) # Used ext_key_name from loop
                elif ext_type == "git": success_current_ext = _install_git_extension(ext_key_name, ext_config_dict, target_user) # Used ext_key_name from loop
                else: con.print_warning(f"Unknown GNOME ext type '{ext_type}' for '{pretty_name}'. Skip."); extensions_success_all = False 
                if not success_current_ext: extensions_success_all = False 
            if not extensions_success_all: overall_success = False; con.print_warning("Some GNOME extensions failed.")
            else: con.print_success("All specified GNOME extensions processed.")
    elif not gext_cli_ready and phase4_config_data.get("gnome_extensions"):
         con.print_warning("Skipped GNOME extension installation due to gnome-extensions-cli setup/usability failure.")

    # Step 5: Install Flatpak applications
    con.print_info("\nStep 5: Installing Flatpak applications (system-wide)...")
    flatpak_apps_to_install = phase4_config_data.get("flatpak_apps", {})
    if flatpak_apps_to_install:
        if not system_utils.install_flatpak_apps(apps_to_install=flatpak_apps_to_install, system_wide=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step):
            overall_success = False; con.print_error("Phase 4 Flatpak installation encountered issues.")
    else: con.print_info("No Flatpak applications listed for installation in Phase 4.")

    # Step 6: Set dark theme preference
    con.print_info("\nStep 6: Setting system theme preference to dark mode...")
    if not _set_dark_theme_preference(target_user):
        con.print_warning(f"Failed to fully set dark theme preference for user '{target_user}'. Appearance might not be dark.")
        # overall_success = False # Uncomment if this is critical for phase success

    if overall_success:
        con.print_success("Phase 4: GNOME Configuration & Extensions completed successfully.")
    else:
        con.print_error("Phase 4: GNOME Configuration & Extensions completed with errors. Please review the output.")
    
    return overall_success