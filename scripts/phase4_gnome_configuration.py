# Fedora-AutoEnv-Setup/scripts/phase4_gnome_configuration.py

import subprocess
import sys
import os
import shlex 
from pathlib import Path
from typing import Optional, Dict, List
import logging # For type hinting Optional[logging.Logger]

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils 
from scripts.logger_utils import app_logger 

# --- Constants ---
# GEXT_PYTHON_MODULE_CALL is no longer needed as gext is not used.
USER_EXTENSIONS_PATH_PATTERN = ".local/share/gnome-shell/extensions" 

# --- Helper Functions ---

# _check_gext_usable_for_enable_disable is REMOVED

def _check_extension_directory_exists(
    target_user: str, 
    target_user_home: Path, 
    extension_uuid: str, # UUID of the extension to check
    logger: Optional[logging.Logger] = None 
) -> bool:
    """
    Checks if the directory for a given extension UUID exists in the user's extensions folder.
    This is a crucial verification step after an extension's install script runs.
    """
    _log = logger or app_logger 
    user_ext_dir = target_user_home / USER_EXTENSIONS_PATH_PATTERN / extension_uuid
    
    _log.debug(f"Verifying existence of extension directory (as user '{target_user}'): {user_ext_dir}")
    check_cmd = f"test -d {shlex.quote(str(user_ext_dir))}"
    try:
        proc = system_utils.run_command(
            check_cmd, run_as_user=target_user, shell=True,
            capture_output=True, check=False, # We check returncode manually
            print_fn_info=None, # Silent check
            logger=_log
        )
        if proc.returncode == 0: # 0 means directory exists
            _log.info(f"Extension directory successfully verified: {user_ext_dir}")
            return True
        else: # Non-zero means directory not found or error in 'test -d'
            _log.warning(f"Extension directory NOT found after install attempt: {user_ext_dir} ('test -d' exit code: {proc.returncode})")
            return False
    except Exception as e: # Catch any other errors during the check
        _log.error(f"Error occurred while checking for extension directory {user_ext_dir}: {e}", exc_info=True)
        return False

def _install_git_extension( # Renamed from _install_and_enable_git_extension
    ext_key: str, 
    ext_cfg: Dict[str, any], 
    target_user: str,
    target_user_home: Path
) -> bool:
    """
    Clones a GNOME Shell extension from Git and runs its install command (e.g., make install).
    The extension's own install script is responsible for file placement and enabling.
    Verifies directory creation if a UUID is provided.
    """
    name = ext_cfg.get("name", ext_key)
    git_url = ext_cfg.get("url")
    install_command_from_config = ext_cfg.get("install_command", "make install") 
    # UUID is primarily for directory verification post-install. Enabling is up to the extension's script.
    extension_uuid_for_verification = ext_cfg.get("uuid_to_enable") or ext_cfg.get("uuid") 

    if not git_url:
        con.print_error(f"Missing 'url' for Git-based extension '{name}'. Cannot install.")
        app_logger.error(f"No git_url for Git extension '{name}'. Skipping."); return False
    
    if not extension_uuid_for_verification:
        con.print_warning(f"No 'uuid' or 'uuid_to_enable' specified for Git extension '{name}'. The installation script will be run, but post-install directory verification will be skipped.")
        app_logger.warning(f"No UUID for Git extension '{name}'. Cannot verify directory post-install.")

    app_logger.info(f"Processing Git-based extension '{name}' from URL '{git_url}' for user '{target_user}'.")
    con.print_sub_step(f"Installing Git-based extension: {name} (Install cmd: '{install_command_from_config}')")

    repo_name = Path(git_url).name.removesuffix(".git")
    
    git_install_user_script = f"""
        set -e 
        PRETTY_NAME={shlex.quote(name)}
        TMP_EXT_DIR=$(mktemp -d -p "{shlex.quote(str(target_user_home / '.cache'))}" "gnome_git_ext_{shlex.quote(ext_key)}_XXXXXX" 2>/dev/null || mktemp -d -t "gnome_git_ext_{shlex.quote(ext_key)}_XXXXXX")
        trap 'echo "Cleaning up temporary directory $TMP_EXT_DIR for $PRETTY_NAME"; rm -rf "$TMP_EXT_DIR"' EXIT
        
        echo "Cloning extension '$PRETTY_NAME' into '$TMP_EXT_DIR' from URL: {git_url}"
        git clone --depth=1 {shlex.quote(git_url)} "$TMP_EXT_DIR/{shlex.quote(repo_name)}"
        
        cd "$TMP_EXT_DIR/{shlex.quote(repo_name)}"
        echo "Current directory: $PWD. Preparing to install '$PRETTY_NAME' using configured command: '{install_command_from_config}'"
        
        INSTALL_SCRIPT_PATH="{install_command_from_config}"
        
        if [[ "$INSTALL_SCRIPT_PATH" == *.sh ]] && [ -f "$INSTALL_SCRIPT_PATH" ]; then
            echo "Making script '$INSTALL_SCRIPT_PATH' executable..."
            chmod +x "$INSTALL_SCRIPT_PATH"
            if [[ "$INSTALL_SCRIPT_PATH" != ./* && "$INSTALL_SCRIPT_PATH" != /* ]]; then
                ACTUAL_INSTALL_EXEC_COMMAND="./$INSTALL_SCRIPT_PATH"
            else
                ACTUAL_INSTALL_EXEC_COMMAND="$INSTALL_SCRIPT_PATH"
            fi
        else
            ACTUAL_INSTALL_EXEC_COMMAND="{install_command_from_config}" 
        fi
        
        echo "Executing install command for '$PRETTY_NAME': $ACTUAL_INSTALL_EXEC_COMMAND"
        $ACTUAL_INSTALL_EXEC_COMMAND
        
        echo "Installation script/command for '$PRETTY_NAME' finished."
    """
    install_script_succeeded = False
    try:
        system_utils.run_command(
            git_install_user_script, run_as_user=target_user, shell=True, 
            capture_output=True, check=True, 
            print_fn_info=con.print_info, print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step, logger=app_logger
        )
        con.print_success(f"Installation script for Git-based extension '{name}' executed successfully.")
        app_logger.info(f"Git extension '{name}' install script executed for {target_user}.")
        install_script_succeeded = True
    except subprocess.CalledProcessError as e:
        app_logger.error(f"Failed to install Git-based extension '{name}' for user '{target_user}'. Install script failed. STDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}", exc_info=False)
        # Error message already printed by run_command.
        return False # Installation script failed
    except Exception as e_unexp:
        app_logger.error(f"Unexpected error during installation of Git-based extension '{name}' for user '{target_user}': {e_unexp}", exc_info=True)
        con.print_error(f"Unexpected error installing Git-based extension '{name}'.")
        return False

    # If install script succeeded and we have a UUID, verify directory.
    # Enabling is now up to the extension's script or manual action.
    if install_script_succeeded and extension_uuid_for_verification:
        if not _check_extension_directory_exists(target_user, target_user_home, extension_uuid_for_verification, logger=app_logger):
            con.print_error(f"Install script for '{name}' (UUID: {extension_uuid_for_verification}) seemed to succeed, but its directory was NOT found in the user's extensions folder. The extension's install script might be faulty or did not install to the expected location (e.g., {target_user_home / USER_EXTENSIONS_PATH_PATTERN / extension_uuid_for_verification}).")
            app_logger.error(f"Post-install check failed: Directory for {extension_uuid_for_verification} not found after git install of '{name}'.")
            return False # Installation is considered failed if directory isn't there
        else:
            con.print_success(f"Extension '{name}' (UUID: {extension_uuid_for_verification}) directory verified after Git install. Enabling is up to the extension or user.")
            app_logger.info(f"Extension '{name}' directory for UUID {extension_uuid_for_verification} verified. Enabling not handled by this script.")
            return True # Successfully installed and verified
    elif install_script_succeeded and not extension_uuid_for_verification:
        con.print_success(f"Installation script for Git-based extension '{name}' executed. No UUID was provided for post-install directory verification.")
        app_logger.info(f"Git extension '{name}' install script executed. No UUID for directory verification provided.")
        return True # Install script itself was the goal and it succeeded
    
    return False # Should be reached if install_script_succeeded was false.

def _apply_gnome_setting(
    target_user: str, schema: str, key: str, value: str, setting_description: str
) -> bool:
    app_logger.info(f"Applying GSetting for user '{target_user}': {schema} {key} = {value} ({setting_description})")
    con.print_sub_step(f"Applying GSetting: {setting_description}...")
    cmd_to_gsettings = f"gsettings set {shlex.quote(schema)} {shlex.quote(key)} {value}"
    try:
        system_utils.run_command(f"dbus-run-session -- {cmd_to_gsettings}", run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
        con.print_success(f"GSetting '{setting_description}' applied successfully for user '{target_user}'."); return True
    except subprocess.CalledProcessError as e: app_logger.error(f"Failed to apply GSetting '{setting_description}'. Error: {e.stderr or e.stdout}", exc_info=False); return False
    except Exception as e_unexp: app_logger.error(f"Unexpected error GSetting '{setting_description}': {e_unexp}", exc_info=True); con.print_error(f"Unexpected error GSetting '{setting_description}'."); return False

def _apply_dark_mode(target_user: str) -> bool:
    app_logger.info(f"Setting dark mode for user '{target_user}'.")
    color_scheme_success = _apply_gnome_setting(target_user, "org.gnome.desktop.interface", "color-scheme", "'prefer-dark'", "Prefer Dark Appearance (color-scheme)")
    if not color_scheme_success: app_logger.warning("Failed to set 'color-scheme' to 'prefer-dark'.")
    gtk_theme_success = _apply_gnome_setting(target_user, "org.gnome.desktop.interface", "gtk-theme", "'Adwaita-dark'", "Adwaita-dark GTK Theme")
    if not gtk_theme_success: app_logger.warning("Failed to set 'gtk-theme' to 'Adwaita-dark'.")
    return color_scheme_success # Primary setting determines overall success of dark mode attempt

# --- Main Phase Function ---
def run_phase4(app_config: dict) -> bool:
    app_logger.info("Starting Phase 4: GNOME Configuration & Manual Extensions Install.")
    con.print_step("PHASE 4: GNOME Configuration & Manual Extensions Install")
    overall_success = True
    
    phase4_config = config_loader.get_phase_data(app_config, "phase4_gnome_configuration")
    if not isinstance(phase4_config, dict):
        app_logger.warning("No valid Phase 4 config. Skipping."); con.print_warning("No Phase 4 config. Skipping."); return True

    target_user = system_utils.get_target_user(logger=app_logger, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_warning=con.print_warning)
    if not target_user: return False 
    
    target_user_home: Optional[Path] = None
    try:
        home_dir_str_proc = system_utils.run_command(f"getent passwd {shlex.quote(target_user)} | cut -d: -f6", shell=True, capture_output=True, check=True, logger=app_logger, print_fn_info=None)
        home_dir_str = home_dir_str_proc.stdout.strip()
        if not home_dir_str: raise ValueError("Home directory string is empty.")
        target_user_home = Path(home_dir_str)
    except Exception as e: con.print_error(f"CRITICAL: No home dir for '{target_user}': {e}"); app_logger.error(f"CRITICAL: No home dir for '{target_user}': {e}", exc_info=True); return False

    app_logger.info(f"Run GNOME configs for: {target_user} (Home: {target_user_home})"); con.print_info(f"Run GNOME configs for: [bold cyan]{target_user}[/bold cyan]")

    # --- Step 1: Install support tools (DNF, Pip, Flatpak) ---
    # Note: gnome-extensions-cli is no longer a primary tool for this phase's extension installation.
    # Users might still want it for their own management, so it can remain in config if desired.
    con.print_info("\nStep 1: Installing support tools (git, build tools, optional utilities)...")
    
    dnf_packages = phase4_config.get("dnf_packages", [])
    if phase4_config.get("gnome_extensions_manual_git") and "git-core" not in dnf_packages and "git" not in dnf_packages:
        app_logger.info("Adding 'git-core' to DNF packages as Git extensions are configured.")
        dnf_packages.append("git-core")
            
    if dnf_packages:
        if not system_utils.install_dnf_packages(dnf_packages, allow_erasing=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger): 
            overall_success = False; con.print_warning("DNF package installation encountered issues.")
    else: app_logger.info("No DNF packages for Phase 4 tools."); con.print_info("No DNF packages for Phase 4 tools.")

    pip_user_packages = phase4_config.get("pip_packages_user", []) 
    if pip_user_packages:
        if not system_utils.install_pip_packages(pip_user_packages, user_only=True, target_user=target_user, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger):
            overall_success = False; con.print_warning("User pip package installation encountered issues.")
    else: app_logger.info("No user pip packages for Phase 4 tools."); con.print_info("No user pip packages for Phase 4 tools.")
    
    flatpak_apps = phase4_config.get("flatpak_apps", {})
    if flatpak_apps: # e.g., GNOME Extension Manager for user convenience
        if not system_utils.install_flatpak_apps(apps_to_install=flatpak_apps, system_wide=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger): 
            overall_success = False; con.print_warning("Flatpak app installation encountered issues.")
    else: app_logger.info("No Flatpak apps for Phase 4."); con.print_info("No Flatpak apps for Phase 4.")

    # Step 2 is removed as gext verification is no longer a gating factor for extension installation.
    # Enabling is now dependent on the extension's own script or manual action.

    # --- Step 2 (was 3): Install GNOME Shell Extensions from Git ---
    # Renumbering step for clarity.
    git_extensions_cfg = phase4_config.get("gnome_extensions_manual_git", {})
    if git_extensions_cfg:
        con.print_info("\nStep 2: Installing GNOME Shell Extensions from Git repositories...")
        all_ext_ok = True
        for ext_key, ext_val_cfg in git_extensions_cfg.items():
            if not isinstance(ext_val_cfg, dict): 
                app_logger.warning(f"Invalid config for Git ext '{ext_key}'. Skip."); con.print_warning(f"Invalid config Git ext '{ext_key}'."); all_ext_ok = False; continue
            # gext_is_ready is no longer passed as gext is not used for enabling by this script.
            if not _install_git_extension(ext_key, ext_val_cfg, target_user, target_user_home): 
                all_ext_ok = False
        if not all_ext_ok: overall_success = False; con.print_warning("One or more Git-based GNOME extensions had install issues.")
        else: con.print_success("All configured Git-based GNOME extensions processed.")
    else: 
        app_logger.info("No Git-based GNOME extensions listed for Phase 4."); 
        con.print_info("No Git-based GNOME extensions to install.")
        
    # --- Step 3 (was 4): Set Dark Mode ---
    con.print_info("\nStep 3: Setting Dark Mode...")
    if phase4_config.get("set_dark_mode", True):
        if not _apply_dark_mode(target_user): app_logger.warning(f"Dark mode setting for '{target_user}' had issues.")
    else: app_logger.info("Dark mode setting disabled in Ph4 config."); con.print_info("Dark mode setting skipped.")

    # --- Final Summary ---
    if overall_success:
        app_logger.info("Phase 4 (manual Git extensions) completed successfully."); 
        con.print_success("Phase 4: GNOME Configuration & Manual Git Extensions Install completed successfully.")
        con.print_warning("IMPORTANT: A logout/login or GNOME Shell restart (Alt+F2, type 'r', press Enter) "
                          "is likely required for all changes to take full effect, especially for extensions.")
    else:
        app_logger.error("Phase 4 (manual Git extensions) completed with errors."); 
        con.print_error("Phase 4: GNOME Configuration & Manual Git Extensions Install completed with errors. Review logs.")
    return overall_success