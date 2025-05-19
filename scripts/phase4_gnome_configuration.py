# Fedora-AutoEnv-Setup/scripts/phase4_gnome_configuration.py

import subprocess
import sys
import os
import shlex 
from pathlib import Path
from typing import Optional, Dict, List

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils 
from scripts.logger_utils import app_logger 

# --- Constants ---
# No longer directly using gext CLI for installation of specific extensions.
# We will install the "GNOME Extension Manager" Flatpak.
EXTENSION_MANAGER_FLATPAK_ID = "com.mattjakeman.ExtensionManager"

# --- Helper Functions ---
# _check_gext_filesystem_usable and _process_extension_filesystem are removed as we are not using gext CLI for install.

def _apply_gnome_setting(
    target_user: str, 
    schema: str, 
    key: str, 
    value: str,
    setting_description: str
) -> bool:
    """Applies a GSettings key for the target user."""
    app_logger.info(f"Applying GSetting for user '{target_user}': {schema} {key} = {value} ({setting_description})")
    con.print_sub_step(f"Applying GSetting: {setting_description}...")
    
    # Use full command string with shlex.quote for safety, executed via dbus-run-session
    # Ensure value is quoted if it's a string and might contain spaces, though gsettings handles types.
    # For simple string, boolean, or int values, direct insertion is often fine.
    # Let's quote the value just in case it's a string that might need it.
    cmd_str = f"gsettings set {shlex.quote(schema)} {shlex.quote(key)} {shlex.quote(value)}"
    
    try:
        system_utils.run_command(
            f"dbus-run-session -- {cmd_str}", 
            run_as_user=target_user, 
            shell=True, # dbus-run-session -- command often requires shell=True
            capture_output=True, 
            check=True, 
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error, 
            logger=app_logger
        )
        con.print_success(f"GSetting '{setting_description}' applied successfully for user '{target_user}'.")
        app_logger.info(f"GSetting '{schema} {key} = {value}' applied for {target_user}.")
        return True
    except subprocess.CalledProcessError as e:
        app_logger.error(f"Failed to apply GSetting '{setting_description}' for user '{target_user}'. Error: {e.stderr or e.stdout}", exc_info=False)
        # run_command already prints an error via print_fn_error
        return False
    except Exception as e_unexp:
        app_logger.error(f"Unexpected error applying GSetting '{setting_description}' for user '{target_user}': {e_unexp}", exc_info=True)
        con.print_error(f"Unexpected error applying GSetting '{setting_description}' for user '{target_user}'.")
        return False

def _apply_dark_mode(target_user: str) -> bool:
    """Applies dark mode preference using gsettings."""
    app_logger.info(f"Setting dark mode for user '{target_user}'.")
    # con.print_sub_step(f"Setting dark mode for user '{target_user}'...") # _apply_gnome_setting will print sub_step

    dark_mode_set = _apply_gnome_setting(
        target_user,
        "org.gnome.desktop.interface",
        "color-scheme",
        "prefer-dark",
        "Prefer Dark Appearance (color-scheme)"
    )
    if not dark_mode_set:
        # Error already logged by _apply_gnome_setting
        return False # Primary dark mode setting failed

    # Attempt to set Adwaita-dark GTK theme as a fallback/complement (best effort)
    _apply_gnome_setting(
        target_user,
        "org.gnome.desktop.interface",
        "gtk-theme",
        "Adwaita-dark",
        "Adwaita-dark GTK Theme (Best Effort)"
    ) # We don't check the return value of this one strictly for overall dark mode success
    
    return dark_mode_set # Return status of the primary color-scheme setting

# --- Main Phase Function ---
def run_phase4(app_config: dict) -> bool:
    app_logger.info("Starting Phase 4: GNOME Configuration & Extension Manager Setup.")
    con.print_step("PHASE 4: GNOME Configuration & Extension Manager Setup")
    overall_success = True
    
    phase4_config = config_loader.get_phase_data(app_config, "phase4_gnome_configuration")
    if not isinstance(phase4_config, dict):
        app_logger.warning("No valid Phase 4 config (expected dict). Skipping."); 
        con.print_warning("No Phase 4 configuration data found. Skipping GNOME configuration."); 
        return True

    target_user = system_utils.get_target_user(logger=app_logger, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_warning=con.print_warning)
    if not target_user: return False 
    
    # target_user_home is not strictly needed by this revised script as much,
    # but good to have if any future helpers need it.
    target_user_home: Optional[Path] = None
    try:
        home_dir_str_proc = system_utils.run_command(f"getent passwd {shlex.quote(target_user)} | cut -d: -f6", shell=True, capture_output=True, check=True, logger=app_logger, print_fn_info=None)
        home_dir_str = home_dir_str_proc.stdout.strip()
        if not home_dir_str: raise ValueError("Home directory string is empty.")
        target_user_home = Path(home_dir_str) # Not used directly in this version, but good practice
    except Exception as e: 
        con.print_warning(f"Could not determine home directory for target user '{target_user}': {e}. Some operations might be affected if they rely on it.")
        app_logger.warning(f"Failed to get home directory for '{target_user}': {e}", exc_info=True)
        # Not returning False here, as current script flow might not critically need it.

    app_logger.info(f"Running GNOME configurations for user: {target_user}")
    con.print_info(f"Running GNOME configurations for user: [bold cyan]{target_user}[/bold cyan]")

    # --- Step 1: Install DNF packages & GNOME Extension Manager (Flatpak) ---
    con.print_info("\nStep 1: Installing support tools and GNOME Extension Manager...")
    
    # DNF packages (e.g., gnome-tweaks, or any other system dependencies)
    dnf_packages = phase4_config.get("dnf_packages", [])
    if dnf_packages:
        if not system_utils.install_dnf_packages(dnf_packages, allow_erasing=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger):
            overall_success = False 
    else: 
        app_logger.info("No DNF packages specified for Phase 4 tools.")
        con.print_info("No DNF packages to install for Phase 4 tools.")

    # Pip packages (if any are still needed, e.g., for other utilities not related to gext)
    # If gext was the only pip package here, this section might become empty.
    pip_user_packages = phase4_config.get("pip_packages_user", []) 
    if pip_user_packages:
        if not system_utils.install_pip_packages(pip_user_packages, user_only=True, target_user=target_user, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger):
            overall_success = False
    else: 
        app_logger.info("No user pip packages specified for Phase 4 tools.")
        con.print_info("No user pip packages for Phase 4 tools.")
    
    # Install GNOME Extension Manager Flatpak
    # The config file should specify EXTENSION_MANAGER_FLATPAK_ID under "flatpak_apps_gnome_specific" or similar.
    # For this example, I'll assume a dedicated key or it's part of a general flatpak_apps list.
    
    flatpak_apps_config = phase4_config.get("flatpak_apps", {}) # General flatpak apps for this phase
    extension_manager_specific_config = phase4_config.get("extension_manager_flatpak", {}) # e.g., {"id": "com.mattjakeman.ExtensionManager", "name": "Extension Manager"}
    
    apps_to_install_flatpak = {}
    if isinstance(flatpak_apps_config, dict):
        apps_to_install_flatpak.update(flatpak_apps_config)
    
    # Ensure Extension Manager is in the list if specified separately or by default
    # If extension_manager_specific_config has an ID, use it.
    em_id = extension_manager_specific_config.get("id", EXTENSION_MANAGER_FLATPAK_ID)
    em_name = extension_manager_specific_config.get("name", "GNOME Extension Manager")
    if em_id not in apps_to_install_flatpak: # Add it if not already listed
        apps_to_install_flatpak[em_id] = em_name
        app_logger.info(f"Ensuring '{em_name}' ({em_id}) is in Flatpak installation list.")

    if apps_to_install_flatpak:
        if not system_utils.install_flatpak_apps(
            apps_to_install=apps_to_install_flatpak, 
            system_wide=True, # Extension Manager is typically system-wide if via Flathub for all users
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step, 
            logger=app_logger
        ):
            overall_success = False
            if EXTENSION_MANAGER_FLATPAK_ID in apps_to_install_flatpak: # Check if EM was part of the failed batch
                con.print_error(f"Failed to install '{EXTENSION_MANAGER_FLATPAK_ID}' (GNOME Extension Manager). Manual extension management will be required.")
                app_logger.error(f"Failed to install GNOME Extension Manager Flatpak.")
    else: 
        app_logger.info("No Flatpak applications (including Extension Manager by default) specified for Phase 4.")
        con.print_info("No Flatpak applications to install for Phase 4.")


    # --- Step 2: Configure GNOME Shell Version Validation (Optional) ---
    con.print_info("\nStep 2: Configuring GNOME Shell Extension Version Validation...")
    disable_validation = phase4_config.get("gnome_shell_disable_extension_validation", False) # Default to False

    if isinstance(disable_validation, bool):
        if disable_validation:
            if con.confirm_action(
                "Do you want to disable GNOME Shell's extension version validation? "
                "This allows trying unsupported extensions but may cause instability.", 
                default=False
            ):
                if _apply_gnome_setting(
                    target_user, "org.gnome.shell", "disable-extension-version-validation", "true", 
                    "Disable Extension Version Validation"
                ):
                    con.print_success("GNOME Shell extension version validation disabled.")
                else:
                    con.print_warning("Failed to disable GNOME Shell extension version validation.")
                    overall_success = False # This setting change failed
            else:
                con.print_info("GNOME Shell extension version validation remains enabled (default).")
        else:
            # Optionally, ensure it's reset if the config explicitly says false (or not present, handled by default=False above)
            # This is useful if it was previously true and user wants to revert.
            # _apply_gnome_setting(target_user, "org.gnome.shell", "disable-extension-version-validation", "false", "Enable Extension Version Validation (Reset)")
            con.print_info("GNOME Shell extension version validation is enabled (or not explicitly disabled).")
    else:
        con.print_warning("Invalid value for 'gnome_shell_disable_extension_validation' in config. Should be boolean. Using default (False).")


    # --- Step 3: User Guidance for Manual Extension Installation ---
    con.print_info("\nStep 3: Manual GNOME Shell Extension Installation Guidance")
    con.print_panel(
        "[bold cyan]Action Required:[/]\n\n"
        "This script has installed [bold]'GNOME Extension Manager'[/] (if configured and successful).\n\n"
        "To install specific GNOME Shell extensions, please:\n"
        "1. Open 'Extension Manager' from your applications menu after this script completes and you have logged back in/restarted GNOME Shell.\n"
        "2. Use the 'Browse' tab within Extension Manager to search for and install your desired extensions (e.g., Dash to Panel, User Themes, etc.).\n\n"
        "This script no longer automatically installs a predefined list of extensions.",
        title="GNOME Shell Extensions - Manual Installation",
        style="blue"
    )
    # We cannot list specific extensions from config here as we are not installing them.
    # configured_extensions = phase4_config.get("gnome_extensions", {})
    # if configured_extensions:
    # con.print_info("You might want to look for extensions like:")
    # for ext_name in configured_extensions.values():
    # if isinstance(ext_name, dict) and ext_name.get("name"):
    # con.print_info(f"  - {ext_name.get('name')}")


    # --- Step 4: Set Dark Mode ---
    con.print_info("\nStep 4: Setting Dark Mode...")
    if phase4_config.get("set_dark_mode", True): 
        if not _apply_dark_mode(target_user):
            app_logger.warning(f"Attempt to set dark mode for user '{target_user}' encountered issues.")
            # Not failing overall_success for dark mode preference failure.
    else:
        app_logger.info("Dark mode setting is disabled in Phase 4 configuration.")
        con.print_info("Dark mode setting skipped as per configuration.")

    # --- Final Summary ---
    if overall_success:
        app_logger.info("Phase 4: GNOME Configuration & Extension Manager Setup completed successfully.")
        con.print_success("Phase 4: GNOME Configuration & Extension Manager Setup completed successfully.")
        con.print_warning("IMPORTANT: A logout/login or a GNOME Shell restart (Alt+F2, type 'r', press Enter) "
                          "is likely required for all settings and Extension Manager to be fully available/functional.")
    else:
        app_logger.error("Phase 4: GNOME Configuration & Extension Manager Setup completed with errors.")
        con.print_error("Phase 4: GNOME Configuration & Extension Manager Setup completed with errors. Please review the output and log files.")
    
    return overall_success