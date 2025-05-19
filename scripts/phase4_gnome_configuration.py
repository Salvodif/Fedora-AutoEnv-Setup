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
GEXT_PYTHON_MODULE_CALL = "python3 -m gnome_extensions_cli.cli"

# --- Helper Functions ---
# _install_pip_packages_for_user is removed, will use system_utils.install_pip_packages

def _check_gext_filesystem_usable(target_user: str) -> bool:
    """
    Checks if gnome-extensions-cli can be invoked via `python3 -m gnome_extensions_cli.cli`
    with --filesystem and shows version. This must be run as the target user.
    """
    app_logger.info(f"Verifying gnome-extensions-cli (as Python module) with --filesystem backend for user '{target_user}'.")
    con.print_info(f"Verifying GNOME Extensions CLI (filesystem backend, as module) for user '{target_user}'...")
    cmd_str = f"{GEXT_PYTHON_MODULE_CALL} --filesystem --version"
    try:
        proc = system_utils.run_command(
            cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, 
            print_fn_info=con.print_info, logger=app_logger
        )
        version_info = proc.stdout.strip()
        con.print_success(f"GNOME Extensions CLI (module, filesystem) is available for user '{target_user}'. Version: {version_info}")
        app_logger.info(f"gext (as module) --filesystem --version successful for {target_user}. Output: {version_info}")
        return True
    except subprocess.CalledProcessError as e:
        con.print_error(f"Verification of GNOME Extensions CLI (as module) failed for user '{target_user}'.")
        app_logger.error(f"gext (as module) verification failed for {target_user}. Exit code: {e.returncode}. Error: {e.stderr or e.stdout}", exc_info=False)
        if e.returncode == 127:
            con.print_error("This might indicate 'python3' is not in PATH for the user's non-interactive session, or the 'gnome-extensions-cli' Python package is not installed correctly for the user.")
        return False
    except Exception as e_unexpected:
        con.print_error(f"An unexpected error occurred while verifying GNOME Extensions CLI (as module) for user '{target_user}'.")
        app_logger.error(f"Unexpected error verifying gext (as module) for {target_user}: {e_unexpected}", exc_info=True)
        return False

def _process_extension_filesystem(
    ext_key: str, ext_cfg: Dict[str, any], target_user: str, target_user_home: Path
) -> bool:
    """
    Installs and enables a GNOME Shell extension using `python3 -m gnome_extensions_cli.cli --filesystem`.
    Requires `target_user_home` for Git extensions to create temporary directories correctly.
    """
    ext_type = ext_cfg.get("type")
    name = ext_cfg.get("name", ext_key)
    uuid_to_enable = ext_cfg.get("uuid_to_enable") or ext_cfg.get("uuid")
    app_logger.info(f"Processing extension '{name}' (type: {ext_type}, UUID for enable: {uuid_to_enable}) for user '{target_user}' using --filesystem (as module).")
    con.print_sub_step(f"Processing extension: {name} (type: {ext_type}, using filesystem backend, as module)")
    install_successful = False

    if ext_type == "ego":
        numerical_id = ext_cfg.get("numerical_id"); uuid_from_cfg = ext_cfg.get("uuid")
        install_identifier = str(numerical_id) if numerical_id else uuid_from_cfg
        if not install_identifier:
            con.print_error(f"Missing ID for EGO extension '{name}'."); app_logger.error(f"No ID for EGO ext '{name}'."); return False
        install_cmd_str = f"{GEXT_PYTHON_MODULE_CALL} --filesystem install {shlex.quote(install_identifier)}"
        app_logger.info(f"Install command for '{name}': {install_cmd_str}")
        try:
            system_utils.run_command(install_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
            con.print_success(f"Ext '{name}' (EGO ID: {install_identifier}) installed."); app_logger.info(f"EGO ext '{name}' (ID: {install_identifier}) installed for {target_user}."); install_successful = True
        except subprocess.CalledProcessError as e:
            stderr_lower = e.stderr.lower() if e.stderr else ""
            if "already installed" in stderr_lower: con.print_info(f"Ext '{name}' already installed."); app_logger.info(f"EGO ext '{name}' already installed for {target_user}."); install_successful = True
            else: app_logger.error(f"Failed to install EGO ext '{name}'.", exc_info=False); return False
        except Exception as e_unexp: app_logger.error(f"Unexpected error EGO ext '{name}': {e_unexp}", exc_info=True); con.print_error(f"Unexpected error EGO ext '{name}'."); return False
    elif ext_type == "git":
        git_url = ext_cfg.get("url"); install_script_name = ext_cfg.get("install_script")
        if not git_url: con.print_error(f"Missing 'url' for Git ext '{name}'."); app_logger.error(f"No git_url for Git ext '{name}'."); return False
        repo_name = Path(git_url).name.removesuffix(".git")
        git_install_user_script = f"""
            set -e; PRETTY_NAME={shlex.quote(name)}
            TMP_EXT_DIR=$(mktemp -d -p "{shlex.quote(str(target_user_home / '.cache'))}" "gnome_git_ext_{shlex.quote(ext_key)}_XXXXXX" 2>/dev/null || mktemp -d -t "gnome_git_ext_{shlex.quote(ext_key)}_XXXXXX")
            trap 'echo "Cleaning up $TMP_EXT_DIR for $PRETTY_NAME"; rm -rf "$TMP_EXT_DIR"' EXIT
            echo "Cloning $PRETTY_NAME into $TMP_EXT_DIR from {git_url}"
            git clone --depth=1 {shlex.quote(git_url)} "$TMP_EXT_DIR/{shlex.quote(repo_name)}"
            cd "$TMP_EXT_DIR/{shlex.quote(repo_name)}"; echo "Inside $PWD, attempting to install $PRETTY_NAME"
            INSTALL_COMMAND=""; 
            if [ -n "{install_script_name}" ]; then
                if [ -f "{install_script_name}" ] && [[ "{install_script_name}" == *.sh ]]; then chmod +x "{install_script_name}"; fi
                INSTALL_COMMAND="./{install_script_name}"; if [[ "{install_script_name}" == make* ]]; then INSTALL_COMMAND="{install_script_name}"; fi
            elif [ -f "Makefile" ] || [ -f "makefile" ]; then INSTALL_COMMAND="make install"; 
            elif [ -f "meson.build" ]; then echo "Meson build detected for $PRETTY_NAME..."; INSTALL_COMMAND="meson setup --prefix={shlex.quote(str(target_user_home / '.local'))} builddir && meson install -C builddir";
            else echo "Error: No install_script/Makefile/meson.build for $PRETTY_NAME."; exit 1; fi
            if [ -n "$INSTALL_COMMAND" ]; then echo "Running: $INSTALL_COMMAND"; $INSTALL_COMMAND; else echo "Error: No install command for $PRETTY_NAME."; exit 1; fi
            echo "Install script for $PRETTY_NAME finished."
        """
        try:
            system_utils.run_command(git_install_user_script, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger)
            con.print_success(f"Git ext '{name}' install script executed."); app_logger.info(f"Git ext '{name}' installed for {target_user}."); install_successful = True
        except subprocess.CalledProcessError as e: app_logger.error(f"Failed Git ext '{name}' install. STDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}", exc_info=False); return False
        except Exception as e_unexp: app_logger.error(f"Unexpected error Git ext '{name}': {e_unexp}", exc_info=True); con.print_error(f"Unexpected error Git ext '{name}'."); return False
    else: con.print_error(f"Unknown ext type '{ext_type}' for '{name}'."); app_logger.error(f"Unknown ext type '{ext_type}'."); return False

    if install_successful and uuid_to_enable:
        enable_cmd_str = f"{GEXT_PYTHON_MODULE_CALL} --filesystem enable {shlex.quote(uuid_to_enable)}"
        app_logger.info(f"Enable command for '{name}': {enable_cmd_str}")
        try:
            system_utils.run_command(enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
            con.print_success(f"Ext '{name}' (UUID: {uuid_to_enable}) enabled."); app_logger.info(f"Ext '{name}' (UUID: {uuid_to_enable}) enabled for {target_user}.")
            return True
        except subprocess.CalledProcessError as e:
            stderr_lower = e.stderr.lower() if e.stderr else ""
            if "already enabled" in stderr_lower: con.print_info(f"Ext '{name}' already enabled."); app_logger.info(f"Ext '{name}' already enabled for {target_user}."); return True
            app_logger.error(f"Failed to enable ext '{name}'.", exc_info=False); return False
        except Exception as e_unexp: app_logger.error(f"Unexpected error enabling ext '{name}': {e_unexp}", exc_info=True); con.print_error(f"Unexpected error enabling ext '{name}'."); return False
    elif install_successful and not uuid_to_enable: con.print_warning(f"Ext '{name}' installed, but no UUID to enable."); app_logger.warning(f"Ext '{name}' installed for {target_user}, no UUID to enable."); return True 
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
    app_logger.info("Starting Phase 4: GNOME Configuration & Extensions.")
    con.print_step("PHASE 4: GNOME Configuration & Extensions")
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

    con.print_info("\nStep 1: Installing GNOME management tools (DNF, Pip, Flatpak)...")
    dnf_packages = phase4_config.get("dnf_packages", [])
    if dnf_packages:
        if not system_utils.install_dnf_packages(dnf_packages, allow_erasing=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger): overall_success = False
    else: app_logger.info("No DNF packages for Ph4 tools."); con.print_info("No DNF packages for Ph4 tools.")

    pip_user_packages = phase4_config.get("pip_packages_user", []) # Changed key to be more specific
    if pip_user_packages:
        if not system_utils.install_pip_packages(pip_user_packages, user_only=True, target_user=target_user, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger):
            overall_success = False
    else: app_logger.info("No user pip packages for Ph4 tools."); con.print_info("No user pip packages for Ph4 tools.")
    
    flatpak_tool_apps = phase4_config.get("flatpak_apps", {})
    if flatpak_tool_apps:
        if not system_utils.install_flatpak_apps(apps_to_install=flatpak_tool_apps, system_wide=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger): overall_success = False
    else: app_logger.info("No Flatpak tools for Ph4."); con.print_info("No Flatpak tools for Ph4.")

    gext_is_ready = False
    if phase4_config.get("gnome_extensions"): 
        con.print_info("\nStep 2: Verifying GNOME Extensions CLI tool (filesystem backend)...")
        gext_is_ready = _check_gext_filesystem_usable(target_user)
        if not gext_is_ready: con.print_error("gext not usable. Extension management skipped."); app_logger.error("gext not usable. Skipping extensions."); overall_success = False 
    else: app_logger.info("No GNOME extensions in config. Skipping gext verification.")

    if gext_is_ready and phase4_config.get("gnome_extensions"):
        extensions_cfg = phase4_config.get("gnome_extensions", {})
        if extensions_cfg:
            con.print_info("\nStep 3: Installing/Configuring GNOME Shell Extensions (filesystem backend)...")
            all_ext_ok = True
            for ext_key, ext_val in extensions_cfg.items():
                if not isinstance(ext_val, dict): app_logger.warning(f"Invalid config for ext '{ext_key}'. Skip."); con.print_warning(f"Invalid config ext '{ext_key}'."); all_ext_ok = False; continue
                if not _process_extension_filesystem(ext_key, ext_val, target_user, target_user_home): all_ext_ok = False
            if not all_ext_ok: overall_success = False; con.print_warning("One or more GNOME extensions had issues.")
            else: con.print_success("All GNOME extensions processed.")
        else: app_logger.info("No GNOME extensions listed for Ph4."); con.print_info("No GNOME extensions to install/configure.")
    elif phase4_config.get("gnome_extensions") and not gext_is_ready: con.print_warning("Skipped GNOME extension install as CLI tool not usable.")
        
    con.print_info("\nStep 4: Setting Dark Mode...")
    if phase4_config.get("set_dark_mode", True):
        if not _apply_dark_mode(target_user): app_logger.warning(f"Dark mode for '{target_user}' had issues.")
    else: app_logger.info("Dark mode setting disabled in Ph4 config."); con.print_info("Dark mode setting skipped.")

    if overall_success:
        app_logger.info("Ph4 completed successfully."); con.print_success("Phase 4: GNOME Configuration & Extensions completed successfully.")
        con.print_warning("IMPORTANT: A logout/login or GNOME Shell restart (Alt+F2, 'r', Enter) is likely required for all changes to take full effect.")
    else:
        app_logger.error("Ph4 completed with errors."); con.print_error("Phase 4: GNOME Configuration & Extensions completed with errors. Review logs.")
    return overall_success