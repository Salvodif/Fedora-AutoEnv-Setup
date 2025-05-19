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
# GEXT_CLI_MODULE is not strictly needed if we call `gext` or `gnome-extensions-cli` directly
GEXT_EXECUTABLE = "gext" # Or "gnome-extensions-cli" if preferred/more reliable

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
        # Ensure python3-pip is available for the user.
        # The command should be run as the user to install into their local environment.
        # Using `python3 -m pip` is generally recommended over just `pip`.
        cmd_str = f"python3 -m pip install --user --upgrade {shlex.quote(pkg)}"
        try:
            # It's important that the user's environment (PATH for python3) is correctly set up.
            # `run_as_user` with `shell=True` should handle this if ~/.local/bin is in their PATH for subsequent calls.
            system_utils.run_command(
                cmd_str, 
                run_as_user=target_user, 
                shell=True, # shell=True allows python3 to be found in user's PATH
                capture_output=True, 
                check=True, 
                print_fn_info=con.print_info, 
                print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step, # To show pip output summary
                logger=app_logger
            )
            con.print_success(f"Pip package '{pkg}' installed/updated for user '{target_user}'.")
        except subprocess.CalledProcessError as e:
            # Error already logged by run_command
            app_logger.error(f"Failed pip install of '{pkg}' for user '{target_user}'. Exit code: {e.returncode}", exc_info=False)
            all_ok = False
        except Exception as e_unexpected:
            app_logger.error(f"Unexpected error during pip install of '{pkg}' for user '{target_user}': {e_unexpected}", exc_info=True)
            con.print_error(f"Unexpected error installing pip package '{pkg}' for user '{target_user}'.")
            all_ok = False
    return all_ok

def _check_gext_filesystem_usable(target_user: str) -> bool:
    """
    Checks if gnome-extensions-cli can be invoked with --filesystem and shows version.
    This must be run as the target user because --filesystem operates on their ~/.local.
    """
    app_logger.info(f"Verifying gnome-extensions-cli with --filesystem backend for user '{target_user}'.")
    con.print_info(f"Verifying GNOME Extensions CLI (filesystem backend) for user '{target_user}'...")
    
    # Command to check gext version using filesystem (might not need dbus-run-session for version with --filesystem)
    # However, gext might still try to interact with some user session files if not careful.
    # Let's try without dbus-run-session first for a simple version check as user.
    cmd = [GEXT_EXECUTABLE, "--filesystem", "--version"]
    
    try:
        # Run as the target user, as --filesystem operations are typically in their home directory.
        proc = system_utils.run_command(
            cmd, 
            run_as_user=target_user, 
            shell=False, # List of args, no shell needed
            capture_output=True, 
            check=True, 
            print_fn_info=con.print_info, # Show "Executing..."
            logger=app_logger
        )
        version_info = proc.stdout.strip()
        con.print_success(f"GNOME Extensions CLI (filesystem backend) is available for user '{target_user}'. Version: {version_info}")
        app_logger.info(f"gext --filesystem --version successful for {target_user}. Output: {version_info}")
        return True
    except FileNotFoundError:
        con.print_error(f"'{GEXT_EXECUTABLE}' command not found for user '{target_user}'. Is it in their PATH (e.g., ~/.local/bin)?")
        app_logger.error(f"'{GEXT_EXECUTABLE}' not found for user '{target_user}'. Check PATH or installation.")
        return False
    except subprocess.CalledProcessError as e:
        con.print_error(f"Verification of '{GEXT_EXECUTABLE} --filesystem --version' failed for user '{target_user}'.")
        app_logger.error(f"gext --filesystem --version verification failed for {target_user}. Error: {e.stderr or e.stdout}", exc_info=False)
        return False
    except Exception as e_unexpected:
        con.print_error(f"An unexpected error occurred while verifying '{GEXT_EXECUTABLE}' for user '{target_user}'.")
        app_logger.error(f"Unexpected error verifying gext for {target_user}: {e_unexpected}", exc_info=True)
        return False

def _process_extension_filesystem(
    ext_key: str, 
    ext_cfg: Dict[str, any], 
    target_user: str
) -> bool:
    """
    Installs and enables a GNOME Shell extension using `gext --filesystem`.
    Handles both EGO (ID/UUID based) and Git based extensions.
    """
    ext_type = ext_cfg.get("type")
    name = ext_cfg.get("name", ext_key)
    uuid_to_enable = ext_cfg.get("uuid_to_enable") or ext_cfg.get("uuid") # Ensure we have a UUID for enabling

    app_logger.info(f"Processing extension '{name}' (type: {ext_type}, UUID for enable: {uuid_to_enable}) for user '{target_user}' using --filesystem.")
    con.print_sub_step(f"Processing extension: {name} (type: {ext_type}, using filesystem backend)")

    install_successful = False

    if ext_type == "ego":
        numerical_id = ext_cfg.get("numerical_id")
        uuid_from_cfg = ext_cfg.get("uuid") # This is the canonical UUID from EGO
        
        # For `gext install`, pk (numerical_id) or UUID can be used.
        # Let's prefer numerical_id if available, as it's shorter.
        install_identifier = str(numerical_id) if numerical_id else uuid_from_cfg
        
        if not install_identifier:
            con.print_error(f"Missing 'numerical_id' or 'uuid' for EGO extension '{name}'. Cannot install.")
            app_logger.error(f"No numerical_id or uuid for EGO extension '{name}'. Skipping.")
            return False

        install_cmd_list = [GEXT_EXECUTABLE, "--filesystem", "install", install_identifier]
        app_logger.info(f"Install command for '{name}': {' '.join(install_cmd_list)}")
        try:
            system_utils.run_command(
                install_cmd_list, run_as_user=target_user, shell=False, capture_output=True, check=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger
            )
            con.print_success(f"Extension '{name}' (EGO ID: {install_identifier}) installed via filesystem backend.")
            app_logger.info(f"EGO extension '{name}' (ID: {install_identifier}) installed successfully via filesystem for {target_user}.")
            install_successful = True
        except subprocess.CalledProcessError as e:
            stderr_lower = e.stderr.lower() if e.stderr else ""
            if "already installed" in stderr_lower:
                con.print_info(f"Extension '{name}' (EGO ID: {install_identifier}) already installed.")
                app_logger.info(f"EGO extension '{name}' already installed for {target_user} (stderr: {stderr_lower[:100]}).")
                install_successful = True # Already there is a success for installation part
            else:
                # Error logged by run_command
                app_logger.error(f"Failed to install EGO extension '{name}' (ID: {install_identifier}) for {target_user} via filesystem.", exc_info=False)
                # No con.print_error here, run_command handles it.
                return False # Failed to install
        except Exception as e_unexp:
            app_logger.error(f"Unexpected error installing EGO extension '{name}' for {target_user}: {e_unexp}", exc_info=True)
            con.print_error(f"Unexpected error installing EGO extension '{name}'.")
            return False

    elif ext_type == "git":
        git_url = ext_cfg.get("url")
        install_script_name = ext_cfg.get("install_script") # e.g., "make install" or "./install.sh"
        
        if not git_url: # install_script might be optional if extension has a Makefile or standard build
            con.print_error(f"Missing 'url' for Git-based extension '{name}'. Cannot install.")
            app_logger.error(f"No git_url for Git extension '{name}'. Skipping.")
            return False

        repo_name = Path(git_url).name.removesuffix(".git")
        
        # Script to be run as the target user
        # It clones, cds, and runs the install script (or make install if no script given)
        # The install script of the extension itself should handle placing files in ~/.local/share/gnome-shell/extensions/UUID
        git_install_user_script = f"""
            set -e
            PRETTY_NAME={shlex.quote(name)}
            # Use a temporary directory in the user's home or /tmp, ensure user can write
            TMP_EXT_DIR=$(mktemp -d -p "{target_user_home}/.cache" gnome_git_ext_{shlex.quote(ext_key)}_XXXXXX 2>/dev/null || mktemp -d -t gnome_git_ext_{shlex.quote(ext_key)}_XXXXXX)
            
            echo "Cloning $PRETTY_NAME into $TMP_EXT_DIR from {git_url}"
            git clone --depth=1 {shlex.quote(git_url)} "$TMP_EXT_DIR/{shlex.quote(repo_name)}"
            
            cd "$TMP_EXT_DIR/{shlex.quote(repo_name)}"
            echo "Inside $PWD, attempting to install $PRETTY_NAME"
            
            INSTALL_COMMAND=""
            if [ -n "{install_script_name}" ]; then
                if [ -f "{install_script_name}" ] && [[ "{install_script_name}" == *.sh ]]; then
                    chmod +x "{install_script_name}"
                fi
                INSTALL_COMMAND="./{install_script_name}" # Assume relative path if ends with .sh
                if [[ "{install_script_name}" == make* ]]; then # e.g. "make install"
                    INSTALL_COMMAND="{install_script_name}"
                fi
            elif [ -f "Makefile" ] || [ -f "makefile" ]; then
                INSTALL_COMMAND="make install" # Common convention
            elif [ -f "meson.build" ]; then
                echo "Meson build detected for $PRETTY_NAME. Attempting standard Meson install..."
                INSTALL_COMMAND="meson setup --prefix=/usr builddir && meson install -C builddir"
                # Note: Meson install usually needs --prefix=$HOME/.local for user installs,
                # or the extension's meson might handle `make install` target that does this.
                # This part is highly dependent on the extension's build system.
                # For --filesystem, the extension's install script should place it in ~/.local/share/gnome-shell/extensions/
                # A general meson install might not do this by default without specific DESTDIR or prefix.
                # The extension's own `make install` or install script is preferred.
                echo "Meson install for extensions often requires specific DESTDIR or prefix to target user's extension folder."
                echo "This script will attempt a generic meson install if no other install_script is provided."
                echo "If this fails, the extension's README should be consulted for manual install steps."
            else
                echo "No 'install_script' provided for $PRETTY_NAME and no Makefile/meson.build found. Cannot determine how to install."
                # Clean up temp dir before exiting with error
                echo "Cleaning up $TMP_EXT_DIR for $PRETTY_NAME due to missing install method."
                rm -rf "$TMP_EXT_DIR"
                exit 1 # Signal error
            fi

            if [ -n "$INSTALL_COMMAND" ]; then
                echo "Running install command for $PRETTY_NAME: $INSTALL_COMMAND"
                # For filesystem install, the extension's install script MUST install to the user's local extensions dir.
                # `gext --filesystem install` handles this for EGO extensions by downloading and unzipping.
                # For Git, the extension's own install mechanism is responsible.
                # No need for dbus-run-session if the install script is just file operations.
                $INSTALL_COMMAND
            else
                 echo "No install command could be determined for $PRETTY_NAME."
                 rm -rf "$TMP_EXT_DIR"; exit 1
            fi
            
            echo "Install script for $PRETTY_NAME finished."
            echo "Cleaning up $TMP_EXT_DIR for $PRETTY_NAME."
            rm -rf "$TMP_EXT_DIR"
            # trap 'echo "Cleaning $TMP_DIR for $PRETTY_NAME"; rm -rf "$TMP_DIR"' EXIT # Trap might be better
        """
        try:
            system_utils.run_command(
                git_install_user_script, run_as_user=target_user, shell=True, # shell=True for the script block
                capture_output=True, check=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step, # Show output of the user script
                logger=app_logger
            )
            con.print_success(f"Git-based extension '{name}' installation script executed for user '{target_user}'.")
            app_logger.info(f"Git extension '{name}' install script executed successfully for {target_user}.")
            install_successful = True
        except subprocess.CalledProcessError as e:
            app_logger.error(f"Failed to install Git-based extension '{name}' for {target_user}. Script output:\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}", exc_info=False)
            # run_command already prints an error message.
            return False
        except Exception as e_unexp:
            app_logger.error(f"Unexpected error installing Git-based extension '{name}' for {target_user}: {e_unexp}", exc_info=True)
            con.print_error(f"Unexpected error installing Git-based extension '{name}'.")
            return False
    else:
        con.print_error(f"Unknown extension type '{ext_type}' for '{name}'. Skipping.")
        app_logger.error(f"Unknown extension type '{ext_type}' for '{name}'.")
        return False

    # Enable the extension using its UUID (common step for both types if install was successful)
    if install_successful and uuid_to_enable:
        enable_cmd_list = [GEXT_EXECUTABLE, "--filesystem", "enable", uuid_to_enable]
        app_logger.info(f"Enable command for '{name}': {' '.join(enable_cmd_list)}")
        try:
            system_utils.run_command(
                enable_cmd_list, run_as_user=target_user, shell=False, capture_output=True, check=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger
            )
            con.print_success(f"Extension '{name}' (UUID: {uuid_to_enable}) enabled via filesystem backend.")
            app_logger.info(f"Extension '{name}' (UUID: {uuid_to_enable}) enabled successfully for {target_user} via filesystem.")
            return True
        except subprocess.CalledProcessError as e:
            stderr_lower = e.stderr.lower() if e.stderr else ""
            if "already enabled" in stderr_lower: # Check if gext reports already enabled
                con.print_info(f"Extension '{name}' (UUID: {uuid_to_enable}) already enabled.")
                app_logger.info(f"Extension '{name}' (UUID: {uuid_to_enable}) already enabled for {target_user} (stderr: {stderr_lower[:100]}).")
                return True
            # else: Error logged by run_command
            app_logger.error(f"Failed to enable extension '{name}' (UUID: {uuid_to_enable}) for {target_user} via filesystem.", exc_info=False)
            return False # Failed to enable
        except Exception as e_unexp:
            app_logger.error(f"Unexpected error enabling extension '{name}' for {target_user}: {e_unexp}", exc_info=True)
            con.print_error(f"Unexpected error enabling extension '{name}'.")
            return False
    elif install_successful and not uuid_to_enable:
        con.print_warning(f"Extension '{name}' installed, but no 'uuid_to_enable' provided in config. Skipping explicit enable step.")
        app_logger.warning(f"Extension '{name}' installed for {target_user}, but no UUID to enable it with gext.")
        return True # Install was successful
    
    return False # Should not be reached if install_successful was false earlier

def _apply_dark_mode(target_user: str) -> bool:
    """Applies dark mode preference using gsettings, run as target_user."""
    app_logger.info(f"Setting dark mode for user '{target_user}'.")
    con.print_sub_step(f"Setting dark mode for user '{target_user}'...")
    
    schema = "org.gnome.desktop.interface"
    key_color_scheme = "color-scheme"
    value_prefer_dark = "prefer-dark"
    
    # Command to set color-scheme (primary way for dark mode)
    # Needs to run in user's D-Bus session if available, or gsettings might not apply immediately to running session.
    # However, for persistent settings, direct gsettings set as user (without dbus-run-session for this specific call)
    # might also work for next login. `dbus-run-session` creates a temporary session.
    # For applying to the *current running* session, it's more reliable.
    cmd_color_scheme = ["gsettings", "set", schema, key_color_scheme, value_prefer_dark]

    try:
        # Run gsettings commands as the target user, ensuring D-Bus context if possible
        # For `gsettings set`, it's often better to run it within the user's graphical session context.
        # `dbus-run-session` helps if no session is active or to ensure it's a fresh one.
        # If a GNOME session is active, `gsettings` called as the user usually works.
        # Let's try `dbus-run-session` for consistency with gext calls if they were to use it.
        
        system_utils.run_command(
            ["dbus-run-session"] + cmd_color_scheme, # Prepend dbus-run-session
            run_as_user=target_user, 
            shell=False, 
            capture_output=True, 
            check=True, 
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error, 
            logger=app_logger
        )
        con.print_success(f"Dark mode preference (color-scheme) set for user '{target_user}'.")

        # Attempt to set Adwaita-dark GTK theme as a fallback/complement
        key_gtk_theme = "gtk-theme"
        value_adwaita_dark = "Adwaita-dark"
        cmd_gtk_theme = ["gsettings", "set", schema, key_gtk_theme, value_adwaita_dark]
        
        # Run this as best effort, check=False
        system_utils.run_command(
            ["dbus-run-session"] + cmd_gtk_theme,
            run_as_user=target_user, 
            shell=False, 
            capture_output=True, 
            check=False, # Don't fail the phase if this specific theme setting fails
            print_fn_info=None, # Be quieter for this secondary setting
            logger=app_logger
        )
        app_logger.info(f"Attempted to set GTK theme to '{value_adwaita_dark}' for user '{target_user}'.")
        return True
    except subprocess.CalledProcessError as e:
        # Error for color-scheme setting already logged by run_command
        app_logger.error(f"Failed to set dark mode (color-scheme) for user '{target_user}'. Error: {e.stderr or e.stdout}", exc_info=False)
        # No con.print_error here, run_command handles it.
        return False
    except Exception as e_unexp:
        app_logger.error(f"Unexpected error setting dark mode for user '{target_user}': {e_unexp}", exc_info=True)
        con.print_error(f"Unexpected error setting dark mode for user '{target_user}'.")
        return False

# --- Main Phase Function ---
def run_phase4(app_config: dict) -> bool:
    app_logger.info("Starting Phase 4: GNOME Configuration & Extensions.")
    con.print_step("PHASE 4: GNOME Configuration & Extensions")
    overall_success = True # Assume success, set to False on critical errors
    
    phase4_config = config_loader.get_phase_data(app_config, "phase4_gnome_configuration")
    if not isinstance(phase4_config, dict): # Check if config is a dictionary
        app_logger.warning("No valid configuration data (expected a dictionary) found for Phase 4. Skipping phase.")
        con.print_warning("No Phase 4 configuration data found. Skipping GNOME configuration.")
        return True # Successfully did nothing

    target_user = system_utils.get_target_user(
        logger=app_logger,
        print_fn_info=con.print_info,
        print_fn_error=con.print_error,
        print_fn_warning=con.print_warning
    )
    if not target_user: 
        app_logger.error("Target user not determined for Phase 4. Aborting.")
        # Error already logged by get_target_user
        return False 
    
    app_logger.info(f"Running GNOME configurations for user: {target_user}")
    con.print_info(f"Running GNOME configurations for user: [bold cyan]{target_user}[/bold cyan]")

    # --- Step 1: Install DNF, Pip, Flatpak tools needed for this phase ---
    con.print_info("\nStep 1: Installing GNOME management tools (DNF, Pip, Flatpak)...")
    
    # DNF packages (system-wide)
    dnf_packages = phase4_config.get("dnf_packages", [])
    if dnf_packages:
        if not system_utils.install_dnf_packages(
            dnf_packages,
            allow_erasing=True, # Allow erasing for tools if needed
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step,
            logger=app_logger
        ):
            overall_success = False
            app_logger.error("Failed to install one or more DNF packages for Phase 4 tools.")
    else:
        app_logger.info("No system-wide DNF packages specified for Phase 4 tools.")
        con.print_info("No system-wide DNF packages to install for Phase 4 tools.")

    # Pip packages (for the target user)
    pip_user_packages = phase4_config.get("pip_packages", []) # Assuming these are for gext or similar tools
    if pip_user_packages:
        if not _install_pip_packages_for_user(pip_user_packages, target_user):
            overall_success = False
            # Errors logged by _install_pip_packages_for_user
    else:
        app_logger.info("No user-specific pip packages specified for Phase 4 tools.")
        con.print_info("No user-specific pip packages to install for Phase 4 tools.")
    
    # Flatpak applications (system-wide, if any specified for tools)
    flatpak_tool_apps = phase4_config.get("flatpak_apps", {})
    if flatpak_tool_apps:
        if not system_utils.install_flatpak_apps(
            apps_to_install=flatpak_tool_apps, 
            system_wide=True, 
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step, 
            logger=app_logger
        ):
            overall_success = False
            app_logger.error("Failed to install one or more Flatpak tool applications in Phase 4.")
    else:
        app_logger.info("No Flatpak tool applications specified for Phase 4.")
        con.print_info("No Flatpak tool applications to install for Phase 4.")

    # --- Step 2: Verify gext CLI (using --filesystem) ---
    gext_is_ready = False
    # Only verify gext if extensions are actually configured for installation
    if phase4_config.get("gnome_extensions"): 
        con.print_info("\nStep 2: Verifying GNOME Extensions CLI tool (filesystem backend)...")
        gext_is_ready = _check_gext_filesystem_usable(target_user)
        if not gext_is_ready:
            con.print_error("GNOME Extensions CLI (gext) with --filesystem backend is not usable. Extension management will be skipped.")
            app_logger.error("gext with --filesystem not usable. Skipping GNOME extension installation.")
            # Not necessarily a failure for the whole phase if other things (dark mode) can still run.
            # But if extensions were the main point, this is a problem.
            # Let's consider it a significant issue if extensions were configured.
            overall_success = False 
    else:
        app_logger.info("No GNOME extensions configured in Phase 4. Skipping gext verification.")
        gext_is_ready = True # Effectively ready because it's not needed.

    # --- Step 3: Install GNOME Shell Extensions (using --filesystem) ---
    if gext_is_ready and phase4_config.get("gnome_extensions"):
        extensions_to_install_cfg = phase4_config.get("gnome_extensions", {})
        if extensions_to_install_cfg: # Check if there are any extensions to install
            con.print_info("\nStep 3: Installing/Configuring GNOME Shell Extensions (using filesystem backend)...")
            # No interactive prompt needed for --filesystem
            # con.print_panel(...)
            # if not con.confirm_action(...):

            extensions_all_processed_ok = True
            for ext_key, ext_config_dict in extensions_to_install_cfg.items():
                if not isinstance(ext_config_dict, dict):
                    app_logger.warning(f"Invalid configuration for extension '{ext_key}'. Expected a dictionary. Skipping.")
                    con.print_warning(f"Invalid configuration for extension '{ext_key}'. Skipping.")
                    extensions_all_processed_ok = False
                    continue
                
                if not _process_extension_filesystem(ext_key, ext_config_dict, target_user):
                    extensions_all_processed_ok = False
                    # Error already logged by _process_extension_filesystem
            
            if not extensions_all_processed_ok:
                overall_success = False # Mark phase as having errors if any extension failed
                con.print_warning("One or more GNOME extensions encountered issues during processing.")
            else:
                con.print_success("All configured GNOME extensions processed.")
        else:
            app_logger.info("No GNOME extensions listed in Phase 4 configuration.")
            con.print_info("No GNOME extensions to install or configure in Phase 4.")
    elif not gext_is_ready and phase4_config.get("gnome_extensions"):
        # This case handled by the gext_is_ready check above, but good for clarity.
        con.print_warning("Skipped GNOME extension installation as the CLI tool was not usable.")
        
    # --- Step 4: Set Dark Mode ---
    # This can run even if extensions or gext failed, as it uses gsettings directly.
    con.print_info("\nStep 4: Setting Dark Mode...")
    if phase4_config.get("set_dark_mode", True): # Default to True if key exists or not specified
        if not _apply_dark_mode(target_user):
            # This is a preference, not usually critical for overall script success.
            # It will print its own warning/error.
            # overall_success = False # Uncomment if dark mode failure should fail the phase
            app_logger.warning(f"Attempt to set dark mode for user '{target_user}' encountered issues.")
    else:
        app_logger.info("Dark mode setting is disabled in Phase 4 configuration.")
        con.print_info("Dark mode setting skipped as per configuration.")


    # --- Final Summary ---
    if overall_success:
        app_logger.info("Phase 4: GNOME Configuration & Extensions completed successfully.")
        con.print_success("Phase 4: GNOME Configuration & Extensions completed successfully.")
        con.print_warning("IMPORTANT: A logout/login or a GNOME Shell restart (Alt+F2, type 'r', press Enter) "
                          "is likely required for all theme, extension, and settings changes to take full effect.")
    else:
        app_logger.error("Phase 4: GNOME Configuration & Extensions completed with errors.")
        con.print_error("Phase 4: GNOME Configuration & Extensions completed with errors. Please review the output and log files.")
    
    return overall_success