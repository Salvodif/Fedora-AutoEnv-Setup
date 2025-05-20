# Fedora-AutoEnv-Setup/scripts/phase4_gnome_configuration.py

import subprocess
import sys
import os
import shlex 
from pathlib import Path
from typing import Optional, Dict, List
import logging 

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils 
from scripts.logger_utils import app_logger 

# --- Constants ---
USER_EXTENSIONS_BASE_DIR_REL_PATH = Path(".local/share/gnome-shell/extensions") # Relative to user's home

# --- Helper Functions ---

def _ensure_user_extensions_base_dir_exists(target_user: str, target_user_home: Path) -> bool:
    """Ensures the base directory for user GNOME Shell extensions exists."""
    user_extensions_path = target_user_home / USER_EXTENSIONS_BASE_DIR_REL_PATH
    app_logger.info(f"Ensuring base GNOME Shell extension directory exists for user '{target_user}': {user_extensions_path}")
    
    # Check if it exists as the target_user
    check_cmd = f"test -d {shlex.quote(str(user_extensions_path))}"
    try:
        proc = system_utils.run_command(
            check_cmd, run_as_user=target_user, shell=True,
            capture_output=True, check=False, print_fn_info=None, logger=app_logger
        )
        if proc.returncode == 0:
            app_logger.info(f"User extensions base directory already exists: {user_extensions_path}")
            return True
        
        # Directory does not exist, attempt to create it
        con.print_info(f"User extensions base directory not found. Creating: {user_extensions_path}")
        mkdir_cmd = f"mkdir -p {shlex.quote(str(user_extensions_path))}"
        system_utils.run_command(
            mkdir_cmd, run_as_user=target_user, shell=True,
            capture_output=True, check=True, print_fn_info=con.print_info, logger=app_logger
        )
        con.print_success(f"Successfully created user extensions base directory: {user_extensions_path}")
        return True
    except Exception as e:
        con.print_error(f"Failed to ensure user extensions base directory exists at {user_extensions_path}: {e}")
        app_logger.error(f"Error ensuring/creating extensions base dir for {target_user}: {e}", exc_info=True)
        return False

def _install_git_extension_direct_move(
    ext_key: str, 
    ext_cfg: Dict[str, any], 
    target_user: str,
    target_user_home: Path
) -> bool:
    """
    Clones a GNOME Shell extension from Git, optionally runs a build command,
    renames the cloned/built directory to the extension's UUID, and moves it
    to the user's local extensions directory.
    Enabling is NOT handled by this function.
    """
    name = ext_cfg.get("name", ext_key)
    git_url = ext_cfg.get("url")
    # `build_command` is optional. If present, it's run in the cloned dir before moving.
    # Examples: "make", "meson compile -C build" (if build output is in root after), "" (no build needed)
    build_command = ext_cfg.get("build_command", "") 
    # `extension_subdir` is optional. If specified, this subdirectory within the clone is what gets renamed/moved.
    # If empty, the root of the clone is used.
    extension_source_subdir = ext_cfg.get("extension_source_subdir", "") 
    
    # UUID is CRITICAL for the destination directory name.
    uuid = ext_cfg.get("uuid_to_enable") or ext_cfg.get("uuid") 

    if not git_url:
        con.print_error(f"Missing 'url' for Git-based extension '{name}'."); return False
    if not uuid:
        con.print_error(f"Missing 'uuid' or 'uuid_to_enable' for Git-based extension '{name}'. Cannot determine destination directory name."); return False

    app_logger.info(f"Processing Git-based extension '{name}' (UUID: {uuid}) from URL '{git_url}' for user '{target_user}'.")
    con.print_sub_step(f"Installing Git-based extension: {name} (UUID: {uuid})")

    repo_name_default = Path(git_url).name.removesuffix(".git") # Default name of cloned directory
    
    # Destination path for the extension
    user_extensions_dir = target_user_home / USER_EXTENSIONS_BASE_DIR_REL_PATH
    final_extension_path = user_extensions_dir / uuid # e.g., ~/.local/share/gnome-shell/extensions/my-uuid@author

    # Shell script to be executed as the target_user
    # This script handles cloning, optional building, renaming (implicitly via move target), and moving.
    install_script_for_user = f"""
        set -e 
        PRETTY_NAME={shlex.quote(name)}
        GIT_URL={shlex.quote(git_url)}
        CLONED_REPO_NAME_DEFAULT={shlex.quote(repo_name_default)}
        BUILD_COMMAND="{build_command}" # Use double quotes to preserve empty string or command with spaces
        EXTENSION_SOURCE_SUBDIR="{extension_source_subdir}" # Subdir within clone that is the actual extension
        
        FINAL_DESTINATION_PATH={shlex.quote(str(final_extension_path))}
        
        # Create a unique temporary directory for cloning
        # Prefer user's .cache, fallback to system /tmp
        TMP_CLONE_PARENT_DIR=$(mktemp -d -p "{shlex.quote(str(target_user_home / '.cache'))}" "gnome_ext_clone_{shlex.quote(ext_key)}_XXXXXX" 2>/dev/null || mktemp -d -t "gnome_ext_clone_{shlex.quote(ext_key)}_XXXXXX")
        trap 'echo "Cleaning up temporary clone parent directory $TMP_CLONE_PARENT_DIR for $PRETTY_NAME"; rm -rf "$TMP_CLONE_PARENT_DIR"' EXIT
        
        TMP_CLONE_PATH="$TMP_CLONE_PARENT_DIR/$CLONED_REPO_NAME_DEFAULT"
        
        echo "Cloning extension '$PRETTY_NAME' into '$TMP_CLONE_PATH'..."
        git clone --depth=1 "$GIT_URL" "$TMP_CLONE_PATH"
        
        cd "$TMP_CLONE_PATH"
        echo "Current directory: $PWD"
        
        if [ -n "$BUILD_COMMAND" ]; then
            echo "Running build command for '$PRETTY_NAME': $BUILD_COMMAND"
            # Execute the build command. Output will be captured.
            # Ensure build command can handle being run from the root of the clone.
            eval $BUILD_COMMAND 
            echo "Build command finished for '$PRETTY_NAME'."
        else
            echo "No build command specified for '$PRETTY_NAME'."
        fi

        # Determine the actual source path of the extension files after clone/build
        # This could be the root of the clone, or a subdirectory specified in config
        EFFECTIVE_SOURCE_PATH="$TMP_CLONE_PATH" # Default to root of clone
        if [ -n "$EXTENSION_SOURCE_SUBDIR" ]; then
            EFFECTIVE_SOURCE_PATH="$TMP_CLONE_PATH/$EXTENSION_SOURCE_SUBDIR"
            echo "Using specified subdirectory as extension source: '$EFFECTIVE_SOURCE_PATH'"
            if [ ! -d "$EFFECTIVE_SOURCE_PATH" ]; then
                echo "Error: Specified extension_source_subdir '$EXTENSION_SOURCE_SUBDIR' does not exist in cloned repo."
                exit 1
            fi
        fi

        # Before moving, ensure metadata.json exists in the source path (basic sanity check)
        if [ ! -f "$EFFECTIVE_SOURCE_PATH/metadata.json" ]; then
            echo "Error: 'metadata.json' not found in '$EFFECTIVE_SOURCE_PATH'. This does not appear to be a valid GNOME Shell extension directory."
            echo "Please check the 'extension_source_subdir' configuration or the extension's build process."
            exit 1
        fi
        
        # Remove existing destination directory if it exists, to ensure a clean move/replace
        if [ -d "$FINAL_DESTINATION_PATH" ]; then
            echo "Removing existing extension directory at '$FINAL_DESTINATION_PATH'..."
            rm -rf "$FINAL_DESTINATION_PATH"
        fi
        
        echo "Moving '$EFFECTIVE_SOURCE_PATH' to '$FINAL_DESTINATION_PATH'..."
        # The `mv` command effectively renames the source to the UUID at the destination.
        mkdir -p "$(dirname "$FINAL_DESTINATION_PATH")" # Ensure parent of FINAL_DESTINATION_PATH exists
        mv "$EFFECTIVE_SOURCE_PATH" "$FINAL_DESTINATION_PATH"
        
        echo "Extension '$PRETTY_NAME' installed to '$FINAL_DESTINATION_PATH'."
        # Trap will clean up $TMP_CLONE_PARENT_DIR which contains the original $TMP_CLONE_PATH (if not moved)
        # or its parent if $EFFECTIVE_SOURCE_PATH was $TMP_CLONE_PATH.
    """
    
    try:
        system_utils.run_command(
            install_script_for_user, run_as_user=target_user, shell=True, 
            capture_output=True, check=True, 
            print_fn_info=con.print_info, print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step, logger=app_logger
        )
        con.print_success(f"Extension '{name}' (UUID: {uuid}) installed successfully by direct move.")
        app_logger.info(f"Git extension '{name}' (UUID: {uuid}) installed via clone, build (if any), and move for {target_user}.")
        # No enabling step here, as per new requirement.
        return True
    except subprocess.CalledProcessError as e:
        # run_command's _p_error will print "Command failed: ..."
        # Add more context here
        con.print_error(f"Failed to install Git-based extension '{name}' (UUID: {uuid}). Script execution failed.")
        app_logger.error(f"Install script for Git-based extension '{name}' (UUID: {uuid}) failed for user '{target_user}'.\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}", exc_info=False)
        return False
    except Exception as e_unexp: # Catch other unexpected Python errors
        app_logger.error(f"Unexpected Python error during installation of Git-based extension '{name}' (UUID: {uuid}) for user '{target_user}': {e_unexp}", exc_info=True)
        con.print_error(f"Unexpected error installing Git-based extension '{name}'.")
        return False

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
    return color_scheme_success

# --- Main Phase Function ---
def run_phase4(app_config: dict) -> bool:
    app_logger.info("Starting Phase 4: GNOME Configuration & Direct Git Extensions Install.")
    con.print_step("PHASE 4: GNOME Configuration & Direct Git Extensions Install")
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
    con.print_info("\nStep 1: Installing support tools (git, build tools, optional utilities)...")
    
    dnf_packages = phase4_config.get("dnf_packages", [])
    # Ensure git (git-core) is included if Git extensions are planned
    # Also ensure build tools like 'make' and 'gcc' might be needed. The user should add these to config.
    if phase4_config.get("gnome_extensions_from_git") and "git-core" not in dnf_packages and "git" not in dnf_packages:
        app_logger.info("Adding 'git-core' to DNF packages as Git extensions are configured.")
        dnf_packages.append("git-core")
            
    if dnf_packages:
        if not system_utils.install_dnf_packages(dnf_packages, allow_erasing=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger): 
            overall_success = False; con.print_warning("DNF package installation encountered issues. Extension builds may fail if dependencies like 'make' or 'gcc' are missing.")
    else: 
        app_logger.info("No DNF packages specified for Phase 4 tools.")
        con.print_info("No DNF packages specified (ensure git, build tools like 'make', 'gcc' are present if needed for extensions).")

    # Pip packages are no longer strictly needed by this phase's core logic unless other tools are desired
    pip_user_packages = phase4_config.get("pip_packages_user", []) 
    if pip_user_packages:
        if not system_utils.install_pip_packages(pip_user_packages, user_only=True, target_user=target_user, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger):
            overall_success = False; con.print_warning("User pip package installation encountered issues.")
    else: app_logger.info("No user pip packages for Phase 4 tools."); con.print_info("No user pip packages for Phase 4 tools.")
    
    flatpak_apps = phase4_config.get("flatpak_apps", {}) # e.g., Extension Manager for user's convenience
    if flatpak_apps: 
        if not system_utils.install_flatpak_apps(apps_to_install=flatpak_apps, system_wide=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger): 
            overall_success = False; con.print_warning("Flatpak app installation encountered issues.")
    else: app_logger.info("No Flatpak apps for Phase 4."); con.print_info("No Flatpak apps for Phase 4.")

    # --- Step 2: Ensure base extensions directory exists ---
    con.print_info(f"\nStep 2: Ensuring GNOME Shell user extensions base directory exists (~/{USER_EXTENSIONS_BASE_DIR_REL_PATH})...")
    if not _ensure_user_extensions_base_dir_exists(target_user, target_user_home):
        con.print_error("CRITICAL: Could not create or verify the user's GNOME Shell extensions base directory. Cannot install extensions.")
        app_logger.error(f"CRITICAL: Failed to ensure extensions base directory for {target_user}.")
        return False # This is critical for placing extensions

    # --- Step 3: Install GNOME Shell Extensions directly from Git ---
    # Assumes a config key like "gnome_extensions_from_git"
    git_extensions_cfg = phase4_config.get("gnome_extensions_from_git", {})
    if git_extensions_cfg:
        con.print_info("\nStep 3: Installing GNOME Shell Extensions from Git by direct move...")
        all_ext_ok = True
        for ext_key, ext_val_cfg in git_extensions_cfg.items():
            if not isinstance(ext_val_cfg, dict): 
                app_logger.warning(f"Invalid config for Git ext '{ext_key}'. Skip."); con.print_warning(f"Invalid config Git ext '{ext_key}'."); all_ext_ok = False; continue
            if not _install_git_extension_direct_move(ext_key, ext_val_cfg, target_user, target_user_home): 
                all_ext_ok = False # Individual extension installation failed
        if not all_ext_ok: overall_success = False; con.print_warning("One or more Git-based GNOME extensions had install issues.")
        else: con.print_success("All configured Git-based GNOME extensions processed.")
    else: 
        app_logger.info("No Git-based GNOME extensions listed for direct installation in Phase 4."); 
        con.print_info("No Git-based GNOME extensions to install via direct move.")
        
    # --- Step 4: Set Dark Mode ---
    con.print_info("\nStep 4: Setting Dark Mode...")
    if phase4_config.get("set_dark_mode", True):
        if not _apply_dark_mode(target_user): app_logger.warning(f"Dark mode setting for '{target_user}' had issues.")
    else: app_logger.info("Dark mode setting disabled in Ph4 config."); con.print_info("Dark mode setting skipped.")

    # --- Final Summary ---
    if overall_success:
        app_logger.info("Phase 4 (Direct Git Extensions Install) completed successfully."); 
        con.print_success("Phase 4: GNOME Configuration & Direct Git Extensions Install completed successfully.")
        con.print_warning("IMPORTANT: A logout/login or GNOME Shell restart (Alt+F2, type 'r', press Enter) "
                          "is likely required for all changes to take full effect, especially for newly installed/moved extensions.")
    else:
        app_logger.error("Phase 4 (Direct Git Extensions Install) completed with errors."); 
        con.print_error("Phase 4: GNOME Configuration & Direct Git Extensions Install completed with errors. Review logs.")
    return overall_success