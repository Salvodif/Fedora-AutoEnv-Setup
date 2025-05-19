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
GEXT_PYTHON_MODULE_CALL = "python3 -m gnome_extensions_cli.cli" # For enable/disable
USER_EXTENSIONS_PATH_PATTERN = ".local/share/gnome-shell/extensions" 

# --- Helper Functions ---

def _check_gext_usable_for_enable_disable(target_user: str) -> bool:
    """
    Checks if gnome-extensions-cli (gext) is usable for enable/disable operations.
    """
    app_logger.info(f"Verifying gnome-extensions-cli (for enable/disable) for user '{target_user}'.")
    con.print_info(f"Verifying GNOME Extensions CLI (for enable/disable) for user '{target_user}'...")
    cmd_str = f"{GEXT_PYTHON_MODULE_CALL} --filesystem --version" 
    try:
        proc = system_utils.run_command(
            cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, 
            print_fn_info=con.print_info, logger=app_logger
        )
        version_info = proc.stdout.strip()
        con.print_success(f"GNOME Extensions CLI is available for user '{target_user}'. Version: {version_info}")
        app_logger.info(f"gext (as module) --filesystem --version successful for {target_user}. Output: {version_info}")
        return True
    except subprocess.CalledProcessError as e:
        con.print_error(f"Verification of GNOME Extensions CLI failed for user '{target_user}'.")
        app_logger.error(f"gext (as module) verification failed for {target_user}. Exit code: {e.returncode}. Error: {e.stderr or e.stdout}", exc_info=False)
        if e.returncode == 127:
            con.print_error("This might mean 'python3' is not in PATH, or 'gnome-extensions-cli' Python package is not installed correctly for the user.")
        return False
    except Exception as e_unexpected:
        con.print_error(f"Unexpected error verifying GNOME Extensions CLI for user '{target_user}'.")
        app_logger.error(f"Unexpected error verifying gext for {target_user}: {e_unexpected}", exc_info=True)
        return False

def _check_extension_directory_exists(
    target_user: str, 
    target_user_home: Path, 
    extension_uuid: str,
    logger: Optional[logging.Logger] = None # Corrected type hint
) -> bool:
    """Checks if the directory for a given extension UUID exists in the user's extensions folder."""
    _log = logger or app_logger # Use app_logger if no specific logger is passed
    # Construct the full path to the user's extension directory for the given UUID
    user_ext_dir = target_user_home / USER_EXTENSIONS_PATH_PATTERN / extension_uuid
    
    _log.debug(f"Checking for extension directory (as user '{target_user}'): {user_ext_dir}")
    check_cmd = f"test -d {shlex.quote(str(user_ext_dir))}"
    try:
        proc = system_utils.run_command(
            check_cmd, run_as_user=target_user, shell=True,
            capture_output=True, check=False, print_fn_info=None, logger=_log
        )
        if proc.returncode == 0:
            _log.info(f"Extension directory found: {user_ext_dir}")
            return True
        else:
            _log.warning(f"Extension directory NOT found: {user_ext_dir} (test -d exit code: {proc.returncode})")
            return False
    except Exception as e:
        _log.error(f"Error checking for extension directory {user_ext_dir}: {e}", exc_info=True)
        return False

def _install_and_enable_git_extension(
    ext_key: str, 
    ext_cfg: Dict[str, any], 
    target_user: str,
    target_user_home: Path,
    gext_is_ready: bool 
) -> bool:
    """
    Clones a GNOME Shell extension from Git, runs its install command,
    verifies directory creation, and optionally tries to enable it using gext.
    """
    name = ext_cfg.get("name", ext_key)
    git_url = ext_cfg.get("url")
    install_command_from_config = ext_cfg.get("install_command", "make install") 
    uuid_to_enable = ext_cfg.get("uuid_to_enable") or ext_cfg.get("uuid")

    if not git_url:
        con.print_error(f"Missing 'url' for Git-based extension '{name}'."); return False
    
    if not uuid_to_enable: # Needed for directory verification and enabling
        con.print_warning(f"No 'uuid' or 'uuid_to_enable' for Git extension '{name}'. Directory verification and enabling via gext will be skipped. Installation will proceed based on its script.")
        app_logger.warning(f"No UUID for Git extension '{name}'. Cannot verify dir or enable with gext.")

    app_logger.info(f"Processing Git-based extension '{name}' from URL '{git_url}' for user '{target_user}'.")
    con.print_sub_step(f"Processing Git-based extension: {name} (Install cmd: '{install_command_from_config}')")

    repo_name = Path(git_url).name.removesuffix(".git")
    git_install_user_script = f"""
        set -e; PRETTY_NAME={shlex.quote(name)}
        TMP_EXT_DIR=$(mktemp -d -p "{shlex.quote(str(target_user_home / '.cache'))}" "gnome_git_ext_{shlex.quote(ext_key)}_XXXXXX" 2>/dev/null || mktemp -d -t "gnome_git_ext_{shlex.quote(ext_key)}_XXXXXX")
        trap 'echo "Cleaning up $TMP_EXT_DIR for $PRETTY_NAME"; rm -rf "$TMP_EXT_DIR"' EXIT
        echo "Cloning $PRETTY_NAME into $TMP_EXT_DIR from {git_url}"
        git clone --depth=1 {shlex.quote(git_url)} "$TMP_EXT_DIR/{shlex.quote(repo_name)}"
        cd "$TMP_EXT_DIR/{shlex.quote(repo_name)}"; echo "Inside $PWD, attempting to install $PRETTY_NAME"
        ACTUAL_INSTALL_COMMAND="{install_command_from_config}"
        if [[ "{install_command_from_config}" == *.sh ]] && [ -f "{install_command_from_config}" ]; then chmod +x "{install_command_from_config}"; if [[ "{install_command_from_config}" != ./* ]]; then ACTUAL_INSTALL_COMMAND="./{install_command_from_config}";fi; fi
        echo "Executing install command: $ACTUAL_INSTALL_COMMAND"; $ACTUAL_INSTALL_COMMAND
        echo "Installation script/command for '$PRETTY_NAME' finished."
    """
    install_script_succeeded = False
    try:
        system_utils.run_command(git_install_user_script, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error,print_fn_sub_step=con.print_sub_step, logger=app_logger)
        con.print_success(f"Installation script for Git extension '{name}' executed."); install_script_succeeded = True
    except subprocess.CalledProcessError as e: app_logger.error(f"Failed Git ext '{name}' install. STDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}", exc_info=False); return False
    except Exception as e_unexp: app_logger.error(f"Unexpected error Git ext '{name}': {e_unexp}", exc_info=True); con.print_error(f"Unexpected Git ext error '{name}'."); return False

    if install_script_succeeded and uuid_to_enable:
        if not _check_extension_directory_exists(target_user, target_user_home, uuid_to_enable, logger=app_logger):
            con.print_error(f"Install script for '{name}' (UUID: {uuid_to_enable}) seemed to succeed, but its directory was NOT found. Extension's install script might be faulty."); return False
        con.print_success(f"Extension '{name}' (UUID: {uuid_to_enable}) directory verified after Git install.")

        if gext_is_ready:
            enable_cmd_str = f"{GEXT_PYTHON_MODULE_CALL} --filesystem enable {shlex.quote(uuid_to_enable)}"
            app_logger.info(f"Attempting to enable extension '{name}' using gext: {enable_cmd_str}")
            try:
                system_utils.run_command(enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
                con.print_success(f"Extension '{name}' (UUID: {uuid_to_enable}) enabled successfully via gext.")
            except subprocess.CalledProcessError as e:
                stderr_lower = e.stderr.lower() if e.stderr else ""
                if "already enabled" in stderr_lower: con.print_info(f"Ext '{name}' (UUID: {uuid_to_enable}) already enabled by gext.")
                else: con.print_warning(f"Failed to enable ext '{name}' via gext. It might need manual enabling or its script handles it."); app_logger.warning(f"gext failed to enable ext '{name}'. Error: {e.stderr}", exc_info=False)
            except Exception as e_unexp_enable: con.print_warning(f"Unexpected error enabling ext '{name}' with gext: {e_unexp_enable}"); app_logger.warning(f"Unexpected error enabling ext '{name}' with gext: {e_unexp_enable}", exc_info=True)
        else: con.print_info(f"gext not available. Skipping explicit enable for '{name}'.")
        return True
    elif install_script_succeeded and not uuid_to_enable:
        con.print_success(f"Install script for Git ext '{name}' executed. No UUID for enabling/verification."); return True
    return False


def _apply_dark_mode(target_user: str) -> bool:
    app_logger.info(f"Setting dark mode for user '{target_user}'."); con.print_sub_step(f"Setting dark mode for user '{target_user}'...")
    schema = "org.gnome.desktop.interface"; key_color_scheme = "color-scheme"; value_prefer_dark = "prefer-dark"
    cmd_color_scheme_str = f"gsettings set {schema} {key_color_scheme} {value_prefer_dark}"
    try:
        system_utils.run_command(f"dbus-run-session -- {cmd_color_scheme_str}", run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
        con.print_success(f"Dark mode (color-scheme) set for '{target_user}'.")
        key_gtk_theme = "gtk-theme"; value_adwaita_dark = "Adwaita-dark"
        cmd_gtk_theme_str = f"gsettings set {schema} {key_gtk_theme} {value_adwaita_dark}"
        system_utils.run_command(f"dbus-run-session -- {cmd_gtk_theme_str}", run_as_user=target_user, shell=True, capture_output=True, check=False, print_fn_info=None, logger=app_logger)
        app_logger.info(f"Attempted to set GTK theme to '{value_adwaita_dark}' for '{target_user}'."); return True
    except subprocess.CalledProcessError as e: app_logger.error(f"Failed to set dark mode for '{target_user}'. Error: {e.stderr or e.stdout}", exc_info=False); return False
    except Exception as e_unexp: app_logger.error(f"Unexpected error setting dark mode for '{target_user}': {e_unexp}", exc_info=True); con.print_error(f"Unexpected error setting dark mode for '{target_user}'."); return False

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
    con.print_info("\nStep 1: Installing support tools (git, build tools, pip packages, flatpaks)...")
    
    # DNF Packages (e.g., git, make, gcc, gnome-tweaks, gnome-shell-extension-common)
    dnf_packages = phase4_config.get("dnf_packages", [])
    # Ensure git (git-core) is included if Git extensions are planned
    if phase4_config.get("gnome_extensions_manual_git") and "git-core" not in dnf_packages and "git" not in dnf_packages:
        app_logger.info("Adding 'git-core' to DNF packages as Git extensions are configured.")
        dnf_packages.append("git-core")
            
    if dnf_packages:
        if not system_utils.install_dnf_packages(
            dnf_packages, allow_erasing=True, 
            print_fn_info=con.print_info, print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step, logger=app_logger
        ): 
            overall_success = False
            con.print_warning("Failed to install some DNF packages. Subsequent steps might be affected.")
    else: 
        app_logger.info("No DNF packages specified for Phase 4 tools.")
        con.print_info("No DNF packages specified for Phase 4 tools (ensure git, build tools are present if needed for extensions).")

    # User Pip Packages (e.g., gnome-extensions-cli for enabling)
    pip_user_packages = phase4_config.get("pip_packages_user", []) 
    gext_in_pip_config = any(p in ["gnome-extensions-cli", "gext"] for p in pip_user_packages)
    if pip_user_packages:
        if not system_utils.install_pip_packages(
            pip_user_packages, user_only=True, target_user=target_user, 
            print_fn_info=con.print_info, print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step, logger=app_logger
        ):
            overall_success = False
            if gext_in_pip_config:
                con.print_warning("Failed to install pip packages; 'gnome-extensions-cli' might not be available for enabling extensions.")
    else: 
        app_logger.info("No user-specific pip packages specified for Phase 4 tools.")
        if phase4_config.get("gnome_extensions_manual_git"):
             con.print_info("If 'gnome-extensions-cli' is needed for enabling extensions, ensure it's installed (e.g., via DNF system package).")

    # Flatpak Apps (e.g., GNOME Extension Manager for user's convenience, or other tools)
    flatpak_apps = phase4_config.get("flatpak_apps", {})
    if flatpak_apps:
        if not system_utils.install_flatpak_apps(
            apps_to_install=flatpak_apps, system_wide=True, 
            print_fn_info=con.print_info, print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step, logger=app_logger
        ): 
            overall_success = False
            # Check if Extension Manager was specifically in the list that failed
            if "com.mattjakeman.ExtensionManager" in flatpak_apps:
                con.print_warning("Failed to install 'com.mattjakeman.ExtensionManager' (GNOME Extension Manager) via Flatpak.")
    else: 
        app_logger.info("No Flatpak applications specified for Phase 4.")
        con.print_info("No Flatpak applications to install in Phase 4.")


    # --- Step 2: Verify gext CLI (if it was intended to be installed for enable/disable) ---
    gext_is_ready_for_enable = False 
    git_extensions_planned = bool(phase4_config.get("gnome_extensions_manual_git"))

    if git_extensions_planned: # Only care about gext if we have git extensions that might need enabling
        gext_in_dnf_config = any(p in ["gnome-extensions-cli", "gext"] for p in dnf_packages) # Check against effective dnf_packages
        # gext_in_pip_config is already defined above

        if gext_in_dnf_config or gext_in_pip_config:
            con.print_info("\nStep 2: Verifying GNOME Extensions CLI tool (for enable/disable functionality)...")
            gext_is_ready_for_enable = _check_gext_usable_for_enable_disable(target_user)
            if not gext_is_ready_for_enable:
                con.print_warning("GNOME Extensions CLI (gext) is not usable. Extensions will be installed via their scripts, but explicit enabling via gext will be skipped.")
                app_logger.warning("gext not usable. Will skip using it for 'enable' commands.")
        else:
            app_logger.info("gnome-extensions-cli not specified in DNF/Pip packages for Phase 4. Enable/disable via gext will be skipped.")
            con.print_info("gnome-extensions-cli not configured for install. Extensions will be installed via their scripts; gext 'enable' will be skipped.")
    else:
        app_logger.info("No Git-based GNOME extensions configured. gext verification for enabling is not applicable.")


    # --- Step 3: Install GNOME Shell Extensions from Git ---
    git_extensions_cfg = phase4_config.get("gnome_extensions_manual_git", {})
    if git_extensions_cfg:
        con.print_info("\nStep 3: Installing GNOME Shell Extensions from Git repositories...")
        all_ext_ok = True
        for ext_key, ext_val_cfg in git_extensions_cfg.items():
            if not isinstance(ext_val_cfg, dict): 
                app_logger.warning(f"Invalid config for Git ext '{ext_key}'. Skip."); con.print_warning(f"Invalid config Git ext '{ext_key}'."); all_ext_ok = False; continue
            if not _install_and_enable_git_extension(ext_key, ext_val_cfg, target_user, target_user_home, gext_is_ready_for_enable): 
                all_ext_ok = False
        if not all_ext_ok: overall_success = False; con.print_warning("One or more Git-based GNOME extensions encountered issues during installation.")
        else: con.print_success("All configured Git-based GNOME extensions processed.")
    else: 
        app_logger.info("No Git-based GNOME extensions listed in Phase 4 configuration."); 
        con.print_info("No Git-based GNOME extensions to install.")
        
    # --- Step 4: Set Dark Mode ---
    con.print_info("\nStep 4: Setting Dark Mode...")
    if phase4_config.get("set_dark_mode", True):
        if not _apply_dark_mode(target_user): app_logger.warning(f"Dark mode setting for '{target_user}' encountered issues.")
    else: app_logger.info("Dark mode setting disabled in Ph4 config."); con.print_info("Dark mode setting skipped.")

    # --- Final Summary ---
    if overall_success:
        app_logger.info("Ph4 (manual Git extensions) completed successfully."); 
        con.print_success("Phase 4: GNOME Configuration & Manual Git Extensions Install completed successfully.")
        con.print_warning("IMPORTANT: A logout/login or GNOME Shell restart (Alt+F2, 'r', Enter) is likely required for all changes to take full effect.")
    else:
        app_logger.error("Ph4 (manual Git extensions) completed with errors."); 
        con.print_error("Phase 4: GNOME Configuration & Manual Git Extensions Install completed with errors. Review logs.")
    return overall_success