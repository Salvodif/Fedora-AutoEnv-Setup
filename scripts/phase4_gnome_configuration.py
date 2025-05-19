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
# Use the Python module invocation for gext, which is more robust than relying on PATH for the script
GEXT_PYTHON_MODULE_CALL = "python3 -m gnome_extensions_cli.cli"

# --- Helper Functions ---

def _install_pip_packages_for_user(packages: List[str], target_user: str) -> bool:
    """
    Installs specified pip packages for the target_user using `pip install --user`.
    """
    if not packages:
        app_logger.info("No pip packages specified for user installation in Phase 4.")
        con.print_info("No pip packages to install for user.")
        return True

    app_logger.info(f"Installing pip packages for user '{target_user}': {packages}")
    con.print_sub_step(f"Installing pip packages for user '{target_user}': {', '.join(packages)}")
    
    all_ok = True
    for pkg in packages:
        cmd_str = f"python3 -m pip install --user --upgrade {shlex.quote(pkg)}"
        try:
            system_utils.run_command(
                cmd_str, 
                run_as_user=target_user, 
                shell=True, 
                capture_output=True, 
                check=True, 
                print_fn_info=con.print_info, 
                print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step,
                logger=app_logger
            )
            con.print_success(f"Pip package '{pkg}' installed/updated for user '{target_user}'.")
        except subprocess.CalledProcessError as e:
            app_logger.error(f"Failed pip install of '{pkg}' for user '{target_user}'. Exit code: {e.returncode}", exc_info=False)
            all_ok = False
        except Exception as e_unexpected:
            app_logger.error(f"Unexpected error during pip install of '{pkg}' for user '{target_user}': {e_unexpected}", exc_info=True)
            con.print_error(f"Unexpected error installing pip package '{pkg}' for user '{target_user}'.")
            all_ok = False
    return all_ok

def _check_gext_filesystem_usable(target_user: str) -> bool:
    """
    Checks if gnome-extensions-cli can be invoked via `python3 -m gnome_extensions_cli.cli`
    with --filesystem and shows version.
    This must be run as the target user.
    """
    app_logger.info(f"Verifying gnome-extensions-cli (as Python module) with --filesystem backend for user '{target_user}'.")
    con.print_info(f"Verifying GNOME Extensions CLI (filesystem backend, as module) for user '{target_user}'...")
    
    # Construct the command string to be executed by the user's shell
    # This ensures that `python3` is the one from the user's environment.
    # The GEXT_PYTHON_MODULE_CALL already includes "python3 -m ...".
    # We append "--filesystem --version" to it.
    # No need for shlex.quote on GEXT_PYTHON_MODULE_CALL if it's a fixed string.
    # Arguments like --filesystem and --version are safe.
    cmd_str = f"{GEXT_PYTHON_MODULE_CALL} --filesystem --version"
    
    try:
        proc = system_utils.run_command(
            cmd_str,  # Pass the full command string
            run_as_user=target_user, 
            shell=True, # shell=True is needed to interpret the command string with spaces and find python3
            capture_output=True, 
            check=True, 
            print_fn_info=con.print_info,
            logger=app_logger
        )
        version_info = proc.stdout.strip()
        con.print_success(f"GNOME Extensions CLI (module, filesystem) is available for user '{target_user}'. Version: {version_info}")
        app_logger.info(f"gext (as module) --filesystem --version successful for {target_user}. Output: {version_info}")
        return True
    except subprocess.CalledProcessError as e:
        # This error (127 or other) means `python3` or the module itself wasn't found/runnable.
        con.print_error(f"Verification of GNOME Extensions CLI (as module) failed for user '{target_user}'.")
        app_logger.error(f"gext (as module) verification failed for {target_user}. Exit code: {e.returncode}. Error: {e.stderr or e.stdout}", exc_info=False)
        if e.returncode == 127:
            con.print_error("This might indicate 'python3' is not in PATH for the user's non-interactive session, or the 'gnome-extensions-cli' Python package is not installed correctly for the user.")
        return False
    except Exception as e_unexpected: # Catch other errors like permissions if shell=False was used without full path
        con.print_error(f"An unexpected error occurred while verifying GNOME Extensions CLI (as module) for user '{target_user}'.")
        app_logger.error(f"Unexpected error verifying gext (as module) for {target_user}: {e_unexpected}", exc_info=True)
        return False

def _process_extension_filesystem(
    ext_key: str, 
    ext_cfg: Dict[str, any], 
    target_user: str
) -> bool:
    """
    Installs and enables a GNOME Shell extension using `python3 -m gnome_extensions_cli.cli --filesystem`.
    """
    ext_type = ext_cfg.get("type")
    name = ext_cfg.get("name", ext_key)
    uuid_to_enable = ext_cfg.get("uuid_to_enable") or ext_cfg.get("uuid")

    app_logger.info(f"Processing extension '{name}' (type: {ext_type}, UUID for enable: {uuid_to_enable}) for user '{target_user}' using --filesystem (as module).")
    con.print_sub_step(f"Processing extension: {name} (type: {ext_type}, using filesystem backend, as module)")

    install_successful = False

    if ext_type == "ego":
        numerical_id = ext_cfg.get("numerical_id")
        uuid_from_cfg = ext_cfg.get("uuid")
        install_identifier = str(numerical_id) if numerical_id else uuid_from_cfg
        
        if not install_identifier:
            con.print_error(f"Missing 'numerical_id' or 'uuid' for EGO extension '{name}'. Cannot install.")
            app_logger.error(f"No numerical_id or uuid for EGO extension '{name}'. Skipping.")
            return False

        # Command string for installing EGO extension
        install_cmd_str = f"{GEXT_PYTHON_MODULE_CALL} --filesystem install {shlex.quote(install_identifier)}"
        app_logger.info(f"Install command for '{name}': {install_cmd_str}")
        try:
            system_utils.run_command(
                install_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger
            )
            con.print_success(f"Extension '{name}' (EGO ID: {install_identifier}) installed via filesystem (as module).")
            app_logger.info(f"EGO extension '{name}' (ID: {install_identifier}) installed successfully via filesystem for {target_user} (as module).")
            install_successful = True
        except subprocess.CalledProcessError as e:
            stderr_lower = e.stderr.lower() if e.stderr else ""
            if "already installed" in stderr_lower:
                con.print_info(f"Extension '{name}' (EGO ID: {install_identifier}) already installed.")
                app_logger.info(f"EGO extension '{name}' already installed for {target_user} (stderr: {stderr_lower[:100]}).")
                install_successful = True
            else:
                app_logger.error(f"Failed to install EGO extension '{name}' (ID: {install_identifier}) for {target_user} via filesystem (as module).", exc_info=False)
                return False
        except Exception as e_unexp:
            app_logger.error(f"Unexpected error installing EGO extension '{name}' for {target_user} (as module): {e_unexp}", exc_info=True)
            con.print_error(f"Unexpected error installing EGO extension '{name}'.")
            return False

    elif ext_type == "git":
        # Git extension installation logic remains the same, as it calls the extension's own install script,
        # not gext for the installation part itself.
        git_url = ext_cfg.get("url")
        install_script_name = ext_cfg.get("install_script")
        
        if not git_url:
            con.print_error(f"Missing 'url' for Git-based extension '{name}'. Cannot install.")
            app_logger.error(f"No git_url for Git extension '{name}'. Skipping.")
            return False

        repo_name = Path(git_url).name.removesuffix(".git")
        git_install_user_script = f"""
            set -e; PRETTY_NAME={shlex.quote(name)}
            TMP_EXT_DIR=$(mktemp -d -p "{target_user_home}/.cache" gnome_git_ext_{shlex.quote(ext_key)}_XXXXXX 2>/dev/null || mktemp -d -t gnome_git_ext_{shlex.quote(ext_key)}_XXXXXX)
            trap 'echo "Cleaning up $TMP_EXT_DIR for $PRETTY_NAME"; rm -rf "$TMP_EXT_DIR"' EXIT
            echo "Cloning $PRETTY_NAME into $TMP_EXT_DIR from {git_url}"
            git clone --depth=1 {shlex.quote(git_url)} "$TMP_EXT_DIR/{shlex.quote(repo_name)}"
            cd "$TMP_EXT_DIR/{shlex.quote(repo_name)}"
            echo "Inside $PWD, attempting to install $PRETTY_NAME"
            INSTALL_COMMAND=""
            if [ -n "{install_script_name}" ]; then
                if [ -f "{install_script_name}" ] && [[ "{install_script_name}" == *.sh ]]; then chmod +x "{install_script_name}"; fi
                INSTALL_COMMAND="./{install_script_name}"; 
                if [[ "{install_script_name}" == make* ]]; then INSTALL_COMMAND="{install_script_name}"; fi
            elif [ -f "Makefile" ] || [ -f "makefile" ]; then INSTALL_COMMAND="make install"; 
            elif [ -f "meson.build" ]; then 
                echo "Meson build detected for $PRETTY_NAME. Attempting standard Meson install..."; 
                INSTALL_COMMAND="meson setup --prefix={shlex.quote(str(target_user_home / '.local'))} builddir && meson install -C builddir";
                echo "For user-specific meson install, prefix is often $HOME/.local. Ensure extension installs to correct GNOME Shell path."
            else 
                echo "No 'install_script' provided for $PRETTY_NAME and no Makefile/meson.build found. Cannot determine how to install."; 
                exit 1; 
            fi
            if [ -n "$INSTALL_COMMAND" ]; then echo "Running install command for $PRETTY_NAME: $INSTALL_COMMAND"; $INSTALL_COMMAND;
            else echo "No install command could be determined for $PRETTY_NAME."; exit 1; fi
            echo "Install script for $PRETTY_NAME finished."
        """ # Note: Removed explicit rm -rf from script, trap handles it.
        try:
            system_utils.run_command(
                git_install_user_script, run_as_user=target_user, shell=True,
                capture_output=True, check=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step, logger=app_logger
            )
            con.print_success(f"Git-based extension '{name}' installation script executed for user '{target_user}'.")
            app_logger.info(f"Git extension '{name}' install script executed successfully for {target_user}.")
            install_successful = True
        except subprocess.CalledProcessError as e:
            app_logger.error(f"Failed to install Git-based extension '{name}' for {target_user}. Script output:\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}", exc_info=False)
            return False
        except Exception as e_unexp:
            app_logger.error(f"Unexpected error installing Git-based extension '{name}' for {target_user}: {e_unexp}", exc_info=True)
            con.print_error(f"Unexpected error installing Git-based extension '{name}'.")
            return False
    else:
        con.print_error(f"Unknown extension type '{ext_type}' for '{name}'. Skipping.")
        app_logger.error(f"Unknown extension type '{ext_type}' for '{name}'.")
        return False

    if install_successful and uuid_to_enable:
        # Command string for enabling extension
        enable_cmd_str = f"{GEXT_PYTHON_MODULE_CALL} --filesystem enable {shlex.quote(uuid_to_enable)}"
        app_logger.info(f"Enable command for '{name}': {enable_cmd_str}")
        try:
            system_utils.run_command(
                enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger
            )
            con.print_success(f"Extension '{name}' (UUID: {uuid_to_enable}) enabled via filesystem (as module).")
            app_logger.info(f"Extension '{name}' (UUID: {uuid_to_enable}) enabled successfully for {target_user} via filesystem (as module).")
            return True
        except subprocess.CalledProcessError as e:
            stderr_lower = e.stderr.lower() if e.stderr else ""
            if "already enabled" in stderr_lower:
                con.print_info(f"Extension '{name}' (UUID: {uuid_to_enable}) already enabled.")
                app_logger.info(f"Extension '{name}' (UUID: {uuid_to_enable}) already enabled for {target_user} (stderr: {stderr_lower[:100]}).")
                return True
            app_logger.error(f"Failed to enable extension '{name}' (UUID: {uuid_to_enable}) for {target_user} via filesystem (as module).", exc_info=False)
            return False
        except Exception as e_unexp:
            app_logger.error(f"Unexpected error enabling extension '{name}' for {target_user} (as module): {e_unexp}", exc_info=True)
            con.print_error(f"Unexpected error enabling extension '{name}'.")
            return False
    elif install_successful and not uuid_to_enable:
        con.print_warning(f"Extension '{name}' installed, but no 'uuid_to_enable' provided. Skipping explicit enable.")
        app_logger.warning(f"Extension '{name}' installed for {target_user}, but no UUID to enable it with gext.")
        return True 
    
    return False

def _apply_dark_mode(target_user: str) -> bool:
    """Applies dark mode preference using gsettings, run as target_user."""
    app_logger.info(f"Setting dark mode for user '{target_user}'.")
    con.print_sub_step(f"Setting dark mode for user '{target_user}'...")
    
    schema = "org.gnome.desktop.interface"
    key_color_scheme = "color-scheme"
    value_prefer_dark = "prefer-dark"
    cmd_color_scheme_str = f"gsettings set {schema} {key_color_scheme} {value_prefer_dark}"

    try:
        system_utils.run_command(
            f"dbus-run-session -- {cmd_color_scheme_str}", 
            run_as_user=target_user, shell=True, capture_output=True, check=True, 
            print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger
        )
        con.print_success(f"Dark mode preference (color-scheme) set for user '{target_user}'.")

        key_gtk_theme = "gtk-theme"
        value_adwaita_dark = "Adwaita-dark"
        cmd_gtk_theme_str = f"gsettings set {schema} {key_gtk_theme} {value_adwaita_dark}"
        
        system_utils.run_command(
            f"dbus-run-session -- {cmd_gtk_theme_str}",
            run_as_user=target_user, shell=True, capture_output=True, check=False,
            print_fn_info=None, logger=app_logger
        )
        app_logger.info(f"Attempted to set GTK theme to '{value_adwaita_dark}' for user '{target_user}'.")
        return True
    except subprocess.CalledProcessError as e:
        app_logger.error(f"Failed to set dark mode (color-scheme) for user '{target_user}'. Error: {e.stderr or e.stdout}", exc_info=False)
        return False
    except Exception as e_unexp:
        app_logger.error(f"Unexpected error setting dark mode for user '{target_user}': {e_unexp}", exc_info=True)
        con.print_error(f"Unexpected error setting dark mode for user '{target_user}'.")
        return False

# --- Main Phase Function ---
def run_phase4(app_config: dict) -> bool:
    app_logger.info("Starting Phase 4: GNOME Configuration & Extensions.")
    con.print_step("PHASE 4: GNOME Configuration & Extensions")
    overall_success = True
    
    phase4_config = config_loader.get_phase_data(app_config, "phase4_gnome_configuration")
    if not isinstance(phase4_config, dict):
        app_logger.warning("No valid configuration data (expected a dictionary) found for Phase 4. Skipping phase.")
        con.print_warning("No Phase 4 configuration data found. Skipping GNOME configuration.")
        return True

    target_user = system_utils.get_target_user(logger=app_logger, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_warning=con.print_warning)
    if not target_user: return False 
    
    target_user_home = system_utils.run_command(f"getent passwd {shlex.quote(target_user)} | cut -d: -f6", shell=True, capture_output=True, check=True, logger=app_logger).stdout.strip()
    if not target_user_home:
        con.print_error(f"Could not determine home directory for target user {target_user}. Aborting Phase 4.")
        app_logger.error(f"Failed to get home directory for {target_user}.")
        return False
    target_user_home = Path(target_user_home) # Convert to Path object

    app_logger.info(f"Running GNOME configurations for user: {target_user} (Home: {target_user_home})")
    con.print_info(f"Running GNOME configurations for user: [bold cyan]{target_user}[/bold cyan]")

    con.print_info("\nStep 1: Installing GNOME management tools (DNF, Pip, Flatpak)...")
    dnf_packages = phase4_config.get("dnf_packages", [])
    if dnf_packages:
        if not system_utils.install_dnf_packages(dnf_packages, allow_erasing=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger):
            overall_success = False
    else: app_logger.info("No DNF packages for Phase 4 tools."); con.print_info("No DNF packages for Phase 4 tools.")

    pip_user_packages = phase4_config.get("pip_packages", [])
    if pip_user_packages: # Ensure gnome-extensions-cli (or its deps) are in this list if installed via pip
        if "gnome-extensions-cli" not in pip_user_packages and "gext" not in pip_user_packages :
             con.print_warning("'gnome-extensions-cli' not found in pip_packages list for Phase 4. If it's a DNF package, this is fine.")
             app_logger.warning("'gnome-extensions-cli' not in pip_packages for Phase 4.")
        if not _install_pip_packages_for_user(pip_user_packages, target_user):
            overall_success = False
    else: app_logger.info("No pip packages for Phase 4 tools."); con.print_info("No pip packages for Phase 4 tools.")
    
    flatpak_tool_apps = phase4_config.get("flatpak_apps", {})
    if flatpak_tool_apps:
        if not system_utils.install_flatpak_apps(apps_to_install=flatpak_tool_apps, system_wide=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger):
            overall_success = False
    else: app_logger.info("No Flatpak tools for Phase 4."); con.print_info("No Flatpak tools for Phase 4.")

    gext_is_ready = False
    if phase4_config.get("gnome_extensions"): 
        con.print_info("\nStep 2: Verifying GNOME Extensions CLI tool (filesystem backend)...")
        gext_is_ready = _check_gext_filesystem_usable(target_user)
        if not gext_is_ready:
            con.print_error("GNOME Extensions CLI (gext) with --filesystem is not usable. Extension management will be skipped.")
            app_logger.error("gext with --filesystem not usable. Skipping GNOME extension installation.")
            if overall_success: # If tools installed OK but gext fails, this phase has errors.
                overall_success = False 
    else:
        app_logger.info("No GNOME extensions configured in Phase 4. Skipping gext verification.")
        # gext_is_ready remains False, but it's fine as it won't be used.

    if gext_is_ready and phase4_config.get("gnome_extensions"): # Double check gext_is_ready
        extensions_to_install_cfg = phase4_config.get("gnome_extensions", {})
        if extensions_to_install_cfg:
            con.print_info("\nStep 3: Installing/Configuring GNOME Shell Extensions (using filesystem backend)...")
            extensions_all_processed_ok = True
            for ext_key, ext_config_dict in extensions_to_install_cfg.items():
                if not isinstance(ext_config_dict, dict):
                    app_logger.warning(f"Invalid configuration for extension '{ext_key}'. Skipping."); con.print_warning(f"Invalid config for ext '{ext_key}'."); extensions_all_processed_ok = False; continue
                if not _process_extension_filesystem(ext_key, ext_config_dict, target_user):
                    extensions_all_processed_ok = False
            if not extensions_all_processed_ok: overall_success = False; con.print_warning("One or more GNOME extensions had issues.")
            else: con.print_success("All configured GNOME extensions processed.")
        else: app_logger.info("No GNOME extensions listed for Phase 4."); con.print_info("No GNOME extensions to install/configure.")
    elif phase4_config.get("gnome_extensions") and not gext_is_ready : # If extensions were desired but gext is not ready
         con.print_warning("Skipped GNOME extension installation as the CLI tool was not usable or verified.")


    con.print_info("\nStep 4: Setting Dark Mode...")
    if phase4_config.get("set_dark_mode", True):
        if not _apply_dark_mode(target_user):
            app_logger.warning(f"Attempt to set dark mode for user '{target_user}' encountered issues.")
    else:
        app_logger.info("Dark mode setting is disabled in Phase 4 configuration."); con.print_info("Dark mode setting skipped.")

    if overall_success:
        app_logger.info("Phase 4: GNOME Configuration & Extensions completed successfully."); con.print_success("Phase 4: GNOME Configuration & Extensions completed successfully.")
        con.print_warning("IMPORTANT: A logout/login or a GNOME Shell restart (Alt+F2, type 'r', press Enter) is likely required for all changes to take full effect.")
    else:
        app_logger.error("Phase 4: GNOME Configuration & Extensions completed with errors."); con.print_error("Phase 4: GNOME Configuration & Extensions completed with errors. Review logs.")
    
    return overall_success