# Fedora-AutoEnv-Setup/scripts/phase4_gnome_configuration.py

import subprocess
import sys
import os
import shlex 
from pathlib import Path
# import tempfile # Not directly used, mktemp is via run_command
from typing import Optional, Dict, List
import logging # Retained for type hints
import time 

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils 
from scripts.logger_utils import app_logger 

# --- Constants ---
USER_EXTENSIONS_BASE_DIR_REL_PATH = Path(".local/share/gnome-shell/extensions") # Relative to user's home

# --- Helper Functions ---

# _ensure_user_extensions_base_dir_exists was moved to system_utils.ensure_dir_exists

def _install_git_extension_direct_move(
    ext_key: str, 
    ext_cfg: Dict[str, any], 
    target_user: str,
    target_user_home: Path # Already resolved absolute path to user's home
) -> bool:
    """
    Clones a GNOME Shell extension from Git into a temporary directory,
    optionally runs a build command within the clone,
    then moves the relevant (sub)directory to the user's local extensions folder,
    renaming it to the extension's UUID.
    Enabling is NOT handled by this function.
    """
    name = ext_cfg.get("name", ext_key) # Friendly name for display
    git_url = ext_cfg.get("url")
    build_command_template = ext_cfg.get("build_command", "") 
    # Subdirectory within the cloned repo that actually contains the extension files (e.g., "extension_files/")
    extension_source_subdir_in_clone = ext_cfg.get("extension_source_subdir", "") 
    uuid = ext_cfg.get("uuid") or ext_cfg.get("uuid_to_enable") # UUID is the destination directory name

    if not git_url:
        con.print_error(f"Missing 'url' for Git-based extension '{name}'. Skipping installation.")
        app_logger.error(f"Missing 'url' for Git-based extension '{name}' (key: {ext_key}).")
        return False
    if not uuid:
        con.print_error(f"Missing 'uuid' (or 'uuid_to_enable') for Git-based extension '{name}'. Cannot determine destination directory name. Skipping installation.")
        app_logger.error(f"Missing 'uuid' for Git-based extension '{name}' (key: {ext_key}).")
        return False

    app_logger.info(f"Processing Git-based extension '{name}' (UUID: {uuid}) from URL '{git_url}' for user '{target_user}'.")
    con.print_sub_step(f"Installing Git-based extension: {name} (UUID: {uuid})")

    # Determine names and paths
    repo_name_from_url = Path(git_url).name.removesuffix(".git") # e.g., "quick-settings-tweaks"
    
    # Absolute path to the user's extensions directory (e.g., /home/user/.local/share/gnome-shell/extensions)
    user_extensions_dir_abs = target_user_home / USER_EXTENSIONS_BASE_DIR_REL_PATH
    # Final absolute path for this specific extension (e.g., /home/user/.../extensions/quick-settings-tweaks@qwreey)
    final_extension_dest_path_abs = user_extensions_dir_abs / uuid 
    
    temp_clone_parent_dir_obj: Optional[Path] = None # To store the path of the temp directory used for cloning

    try:
        # Create a unique temporary directory for cloning.
        # Prefer user's .cache, fallback to system /tmp. Run mktemp as the user.
        temp_parent_dir_name_prefix = f"gnome_ext_clone_{ext_key}_{os.getpid()}_{int(time.time())}"
        user_cache_dir_abs = target_user_home / ".cache"
        
        # Ensure user's .cache directory exists (quietly)
        system_utils.ensure_dir_exists(
            user_cache_dir_abs, 
            target_user=target_user, 
            logger=app_logger, 
            print_fn_info=None 
        )

        # Try creating temp dir in user's .cache
        mktemp_cmd_user_cache = f"mktemp -d -p {shlex.quote(str(user_cache_dir_abs))} {temp_parent_dir_name_prefix}_XXXXXX"
        mktemp_cmd_system_tmp = f"mktemp -d -t {temp_parent_dir_name_prefix}_XXXXXX" # Fallback

        temp_clone_parent_dir_str = ""
        try:
            proc_mktemp_cache = system_utils.run_command(
                mktemp_cmd_user_cache, run_as_user=target_user, shell=True, 
                capture_output=True, check=True, logger=app_logger, print_fn_info=None
            )
            temp_clone_parent_dir_str = proc_mktemp_cache.stdout.strip()
        except Exception: # If mktemp in user's cache fails
            app_logger.warning(f"Failed to create temp dir in user's .cache for '{name}', trying system /tmp.")
            proc_mktemp_tmp = system_utils.run_command(
                mktemp_cmd_system_tmp, run_as_user=target_user, shell=True, # Still run as user for consistency, though /tmp is usually world-writable
                capture_output=True, check=True, logger=app_logger, print_fn_info=None
            )
            temp_clone_parent_dir_str = proc_mktemp_tmp.stdout.strip()
        
        if not temp_clone_parent_dir_str: # Should not happen if mktemp commands succeed
            raise Exception("Failed to create any temporary directory for cloning.")
        
        temp_clone_parent_dir_obj = Path(temp_clone_parent_dir_str)
        app_logger.info(f"Created temporary parent directory for clone: {temp_clone_parent_dir_obj} (as user '{target_user}')")

        # Path where the repo will be cloned inside the temporary parent
        cloned_repo_path_in_temp_abs = temp_clone_parent_dir_obj / repo_name_from_url

        con.print_info(f"Cloning '{git_url}' into '{cloned_repo_path_in_temp_abs}' as user '{target_user}'...")
        git_clone_cmd = ["git", "clone", "--depth=1", git_url, str(cloned_repo_path_in_temp_abs)]
        system_utils.run_command(
            git_clone_cmd, run_as_user=target_user, # Run git clone as the target user
            capture_output=True, check=True, print_fn_info=con.print_info, logger=app_logger
        )
        app_logger.info(f"Successfully cloned '{name}' to '{cloned_repo_path_in_temp_abs}' as user '{target_user}'.")

        # Run build command if specified, within the cloned repo directory, as the target user
        if build_command_template:
            # Substitute $HOME in build command if present (relative to target_user's home)
            # This simple substitution might not cover all shell expansions.
            processed_build_command = build_command_template.replace("$HOME", str(target_user_home))
            
            con.print_info(f"Running build command '{processed_build_command}' for '{name}' in '{cloned_repo_path_in_temp_abs}' as user '{target_user}'...")
            system_utils.run_command(
                processed_build_command, 
                cwd=str(cloned_repo_path_in_temp_abs), # Execute in the cloned repo's directory
                run_as_user=target_user, 
                shell=True, # Build commands often need a shell
                capture_output=True, check=True, 
                print_fn_info=con.print_info, print_fn_sub_step=con.print_sub_step, logger=app_logger
            )
            app_logger.info(f"Build command '{processed_build_command}' completed for '{name}' as user '{target_user}'.")
        else:
            app_logger.info(f"No build command specified for '{name}'.")

        # Determine the actual source path of extension files within the clone
        # (could be the root of the clone, or a subdirectory)
        effective_extension_source_path_abs = cloned_repo_path_in_temp_abs
        if extension_source_subdir_in_clone:
            effective_extension_source_path_abs = cloned_repo_path_in_temp_abs / extension_source_subdir_in_clone
            app_logger.info(f"Using subdirectory '{extension_source_subdir_in_clone}' as effective source: {effective_extension_source_path_abs}")
        
        # Verify the effective source path exists and contains metadata.json (as the target user)
        check_effective_source_dir_cmd = f"test -d {shlex.quote(str(effective_extension_source_path_abs))}"
        dir_exists_proc = system_utils.run_command(
            check_effective_source_dir_cmd, run_as_user=target_user, shell=True, 
            check=False, capture_output=True, logger=app_logger, print_fn_info=None
        )
        if dir_exists_proc.returncode != 0:
            con.print_error(f"Effective source path '{effective_extension_source_path_abs}' does not exist or is not a directory after clone/build for extension '{name}'. Check 'extension_source_subdir' or build process output.")
            app_logger.error(f"Effective source path missing for '{name}': {effective_extension_source_path_abs}")
            return False
        
        metadata_json_path_abs = effective_extension_source_path_abs / 'metadata.json'
        check_metadata_cmd = f"test -f {shlex.quote(str(metadata_json_path_abs))}"
        metadata_exists_proc = system_utils.run_command(
            check_metadata_cmd, run_as_user=target_user, shell=True, 
            check=False, capture_output=True, logger=app_logger, print_fn_info=None
        )
        if metadata_exists_proc.returncode != 0:
            con.print_error(f"'metadata.json' not found in '{effective_extension_source_path_abs}'. Not a valid GNOME Shell extension directory. Check 'extension_source_subdir' or build process output.")
            app_logger.error(f"metadata.json missing in effective source for '{name}': {metadata_json_path_abs}")
            return False

        # Remove existing extension directory at the final destination if it exists (as target user)
        check_old_dest_cmd = f"test -d {shlex.quote(str(final_extension_dest_path_abs))}"
        old_dest_exists_proc = system_utils.run_command(
            check_old_dest_cmd, run_as_user=target_user, shell=True, 
            check=False, capture_output=True, logger=app_logger, print_fn_info=None
        )
        if old_dest_exists_proc.returncode == 0:
            con.print_info(f"Removing existing extension directory at '{final_extension_dest_path_abs}' as user '{target_user}'...")
            rm_old_dest_cmd = f"rm -rf {shlex.quote(str(final_extension_dest_path_abs))}"
            system_utils.run_command(
                rm_old_dest_cmd, run_as_user=target_user, shell=True, 
                check=True, print_fn_info=con.print_info, logger=app_logger
            )

        # Ensure parent of final destination exists (e.g., .../extensions/); user_extensions_dir_abs should already exist from earlier step.
        # This is a safeguard if UUID contains slashes, though unlikely for GNOME extensions.
        system_utils.ensure_dir_exists(
            final_extension_dest_path_abs.parent, 
            target_user=target_user, 
            logger=app_logger, 
            print_fn_info=None # Quiet for parent dir
        )

        # Move the effective source to the final destination, as the target user
        mv_cmd = f"mv {shlex.quote(str(effective_extension_source_path_abs))} {shlex.quote(str(final_extension_dest_path_abs))}"
        con.print_info(f"Moving '{effective_extension_source_path_abs}' to '{final_extension_dest_path_abs}' as user '{target_user}'...")
        system_utils.run_command(
            mv_cmd, run_as_user=target_user, shell=True, 
            check=True, print_fn_info=con.print_info, logger=app_logger
        )

        con.print_success(f"Extension '{name}' (UUID: {uuid}) installed successfully to '{final_extension_dest_path_abs}'.")
        app_logger.info(f"Git extension '{name}' (UUID: {uuid}) installed via direct move for user '{target_user}'.")
        return True
    except Exception as e: # Catch CalledProcessError from run_command or other Python errors
        con.print_error(f"Failed to install Git-based extension '{name}' (UUID: {uuid}). Error: {e}")
        app_logger.error(f"Installation of Git-based extension '{name}' (UUID: {uuid}) failed for user '{target_user}'. Error: {e}", exc_info=True)
        return False
    finally:
        # Cleanup the temporary clone parent directory (as target user)
        if temp_clone_parent_dir_obj and temp_clone_parent_dir_obj.is_dir(): # Check is_dir for safety
            app_logger.info(f"Cleaning up temporary clone parent directory: {temp_clone_parent_dir_obj} (as user '{target_user}')")
            cleanup_cmd = f"rm -rf {shlex.quote(str(temp_clone_parent_dir_obj))}"
            try:
                # Run cleanup as the user who created the temp dir
                system_utils.run_command(cleanup_cmd, run_as_user=target_user, shell=True, check=False, print_fn_info=None, logger=app_logger) 
            except Exception as e_cleanup:
                app_logger.warning(f"Failed to clean up temporary directory {temp_clone_parent_dir_obj} (user: {target_user}): {e_cleanup}")

def _apply_gnome_setting( target_user: str, schema: str, key: str, value_str: str, setting_description: str ) -> bool:
    """Applies a GSetting for the target user. value_str is the string representation of the value."""
    app_logger.info(f"Applying GSetting for user '{target_user}': Schema='{schema}', Key='{key}', Value='{value_str}' ({setting_description})")
    con.print_sub_step(f"Applying GSetting: {setting_description}...")
    
    # Construct the command. gsettings expects the value part correctly quoted if it's a string.
    # Example: gsettings set org.gnome.desktop.interface gtk-theme 'Adwaita-dark'
    # Example: gsettings set org.gnome.desktop.wm.preferences button-layout 'appmenu:minimize,maximize,close'
    # The value_str should already be prepared with necessary quotes if it's a string literal for gsettings.
    # e.g. if value is "Adwaita-dark", value_str should be "'Adwaita-dark'"
    cmd_for_gsettings = f"gsettings set {shlex.quote(schema)} {shlex.quote(key)} {value_str}"
    
    # gsettings needs a D-Bus session. dbus-run-session helps run a command within a new session.
    # This is crucial when running gsettings commands from scripts, especially as another user or root.
    full_cmd_with_dbus = f"dbus-run-session -- {cmd_for_gsettings}"
    
    try:
        system_utils.run_command(
            full_cmd_with_dbus, 
            run_as_user=target_user, 
            shell=True, # dbus-run-session and the gsettings command benefit from shell
            capture_output=True, # Capture output for logging
            check=True, # Fail on non-zero exit code
            print_fn_info=con.print_info, # For "Executing..."
            print_fn_error=con.print_error, # For errors from run_command
            logger=app_logger
        )
        con.print_success(f"GSetting '{setting_description}' applied successfully for user '{target_user}'.")
        app_logger.info(f"GSetting '{setting_description}' applied for '{target_user}'.")
        return True
    except subprocess.CalledProcessError as e:
        # run_command already logs and prints error
        app_logger.error(f"Failed to apply GSetting '{setting_description}' for user '{target_user}'. Exit: {e.returncode}, Stderr: {e.stderr or e.stdout}", exc_info=False)
        return False
    except Exception as e_unexp: 
        con.print_error(f"Unexpected error applying GSetting '{setting_description}' for user '{target_user}': {e_unexp}")
        app_logger.error(f"Unexpected error applying GSetting '{setting_description}' for '{target_user}': {e_unexp}", exc_info=True)
        return False

def _apply_dark_mode(target_user: str) -> bool:
    """Applies dark mode settings for the target user."""
    app_logger.info(f"Setting dark mode for user '{target_user}'.")
    con.print_sub_step("Applying Dark Mode settings...")
    
    # For modern GNOME (Fedora 36+ typically)
    color_scheme_success = _apply_gnome_setting(
        target_user, 
        "org.gnome.desktop.interface", 
        "color-scheme", 
        "'prefer-dark'", # Value for gsettings (string literal 'prefer-dark')
        "Color Scheme to Prefer Dark"
    )
    
    # Fallback/Traditional GTK theme setting (still often respected or useful)
    gtk_theme_success = _apply_gnome_setting(
        target_user, 
        "org.gnome.desktop.interface", 
        "gtk-theme", 
        "'Adwaita-dark'", # Value for gsettings (string literal 'Adwaita-dark')
        "GTK Theme to Adwaita-dark"
    )
    
    if not color_scheme_success: 
        app_logger.warning(f"Failed to set 'color-scheme' to 'prefer-dark' for user '{target_user}'.")
    if not gtk_theme_success: 
        app_logger.warning(f"Failed to set 'gtk-theme' to 'Adwaita-dark' for user '{target_user}'.")
        
    # Consider success if at least one, or preferably color-scheme, succeeded.
    # For this script, we'll say it's generally successful if color-scheme works,
    # as that's the more modern approach.
    return color_scheme_success

# --- Main Phase Function ---
def run_phase4(app_config: dict) -> bool:
    app_logger.info("Starting Phase 4: GNOME Configuration & Direct Git Extensions Install.")
    con.print_step("PHASE 4: GNOME Configuration & Direct Git Extensions Install")
    overall_success = True
    
    phase4_config = config_loader.get_phase_data(app_config, "phase4_gnome_configuration")
    if not isinstance(phase4_config, dict):
        app_logger.warning("No valid Phase 4 configuration data found (expected a dictionary). Skipping GNOME configuration.")
        con.print_warning("No Phase 4 configuration data found. Skipping GNOME configuration.")
        return True # Successfully skipped

    target_user = system_utils.get_target_user(
        logger=app_logger, print_fn_info=con.print_info, 
        print_fn_error=con.print_error, print_fn_warning=con.print_warning
    )
    if not target_user: 
        # Error already printed by get_target_user
        return False 
    
    target_user_home = system_utils.get_user_home_dir(target_user, logger=app_logger, print_fn_error=con.print_error)
    if not target_user_home: 
        # Error already printed by get_user_home_dir
        app_logger.error(f"CRITICAL: Could not determine home directory for '{target_user}'. Aborting GNOME configuration phase.")
        return False

    app_logger.info(f"Running GNOME configurations for user: {target_user} (Home: {target_user_home})")
    con.print_info(f"Running GNOME configurations for: [bold cyan]{target_user}[/bold cyan]")

    # --- Step 1: Install support tools (DNF, Pip, Flatpak) ---
    con.print_info("\nStep 1: Installing support tools (git, build tools, optional utilities)...")
    app_logger.info("Phase 4, Step 1: Installing support tools.")
    
    dnf_packages_ph4 = phase4_config.get("dnf_packages", [])
    # Ensure git is available if Git-based extensions are to be installed
    if phase4_config.get("gnome_extensions"):
        git_found = False
        for pkg in dnf_packages_ph4: # Check if git or git-core is already listed
            if isinstance(pkg, str) and ("git-core" == pkg or "git" == pkg):
                git_found = True
                break
        if not git_found:
            app_logger.info("Adding 'git-core' to DNF packages as Git extensions are configured and git was not explicitly listed.")
            dnf_packages_ph4.append("git-core") # Add git if not already there

    if dnf_packages_ph4:
        if not system_utils.install_dnf_packages(
            dnf_packages_ph4, allow_erasing=True, 
            print_fn_info=con.print_info, print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step, logger=app_logger
        ): 
            overall_success = False
            app_logger.warning("DNF package installation for Phase 4 tools encountered issues.")
    else: 
        app_logger.info("No DNF packages specified for Phase 4 tools.")
        con.print_info("No DNF packages to install for Phase 4 tools.")

    pip_user_packages_ph4 = phase4_config.get("pip_packages_user", []) 
    if pip_user_packages_ph4:
        if not system_utils.install_pip_packages(
            pip_user_packages_ph4, user_only=True, target_user=target_user, 
            print_fn_info=con.print_info, print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step, logger=app_logger
        ):
            overall_success = False
            app_logger.warning("User pip package installation for Phase 4 tools encountered issues.")
    else: 
        app_logger.info("No user pip packages specified for Phase 4 tools.")
        con.print_info("No user pip packages to install for Phase 4 tools.")
    
    flatpak_apps_ph4: Dict[str, str] = phase4_config.get("flatpak_apps", {})
    if flatpak_apps_ph4: 
        if not system_utils.install_flatpak_apps(
            apps_to_install=flatpak_apps_ph4, system_wide=True, 
            print_fn_info=con.print_info, print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step, logger=app_logger
        ): 
            overall_success = False
            app_logger.warning("Flatpak app installation for Phase 4 tools encountered issues.")
    else: 
        app_logger.info("No Flatpak apps specified for Phase 4 tools.")
        con.print_info("No Flatpak apps to install for Phase 4 tools.")

    # --- Step 2: Ensure base extensions directory exists ---
    # This directory is $HOME/.local/share/gnome-shell/extensions
    user_extensions_dir_abs = target_user_home / USER_EXTENSIONS_BASE_DIR_REL_PATH
    con.print_info(f"\nStep 2: Ensuring GNOME Shell user extensions base directory exists ({user_extensions_dir_abs})...")
    app_logger.info(f"Phase 4, Step 2: Ensuring extensions base directory: {user_extensions_dir_abs}")
    if not system_utils.ensure_dir_exists(
        user_extensions_dir_abs, 
        target_user=target_user, # Ensure it's owned by the user
        logger=app_logger,
        print_fn_info=con.print_info,
        print_fn_error=con.print_error,
        print_fn_success=con.print_success 
    ):
        con.print_error(f"CRITICAL: Could not create or verify the user's GNOME Shell extensions base directory ({user_extensions_dir_abs}). Cannot install extensions.")
        app_logger.error(f"CRITICAL: Failed to ensure extensions base directory '{user_extensions_dir_abs}' for user '{target_user}'.")
        return False # This is critical for installing extensions

    # --- Step 3: Install GNOME Shell Extensions directly from Git ---
    git_extensions_config_map: Dict[str, Dict] = phase4_config.get("gnome_extensions", {}) 
    if git_extensions_config_map:
        con.print_info("\nStep 3: Installing GNOME Shell Extensions from Git by direct move...")
        app_logger.info("Phase 4, Step 3: Installing Git-based GNOME extensions.")
        any_ext_failed = False
        for ext_key, ext_config_dict in git_extensions_config_map.items():
            if not isinstance(ext_config_dict, dict): 
                app_logger.warning(f"Invalid configuration for Git extension '{ext_key}' (not a dictionary). Skipping.")
                con.print_warning(f"Invalid configuration for Git extension '{ext_key}'. Skipping.")
                any_ext_failed = True
                continue
            
            # This phase specifically handles "git" type extensions by cloning and moving
            if ext_config_dict.get("type") != "git": 
                app_logger.info(f"Skipping extension '{ext_config_dict.get('name', ext_key)}' as its type is not 'git' (type: {ext_config_dict.get('type')}). This installation method only handles 'git' type extensions.")
                con.print_info(f"Skipping non-Git type extension: {ext_config_dict.get('name', ext_key)}")
                continue # Skip non-git types in this specific logic block
                
            if not _install_git_extension_direct_move(ext_key, ext_config_dict, target_user, target_user_home): 
                any_ext_failed = True # _install_git_extension_direct_move prints its own errors
                app_logger.warning(f"Installation failed for Git-based extension: {ext_config_dict.get('name', ext_key)}")
        
        if any_ext_failed: 
            overall_success = False
            con.print_warning("One or more Git-based GNOME extensions encountered installation issues.")
        else: 
            con.print_success("All configured Git-based GNOME extensions processed successfully.")
            app_logger.info("All Git-based GNOME extensions processed.")
    else: 
        app_logger.info("No extensions listed under 'gnome_extensions' key in Phase 4 configuration, or key is empty.")
        con.print_info("No Git-based GNOME extensions configured for installation via direct move.")
        
    # --- Step 4: Set Dark Mode ---
    con.print_info("\nStep 4: Setting Dark Mode...")
    app_logger.info("Phase 4, Step 4: Setting Dark Mode.")
    if phase4_config.get("set_dark_mode", True): # Default to True if key is missing
        if not _apply_dark_mode(target_user): 
            # _apply_dark_mode prints its own sub-step messages
            app_logger.warning(f"Dark mode setting for user '{target_user}' encountered issues.")
            # Not critical enough to fail the whole phase, but good to note.
    else: 
        app_logger.info("Dark mode setting explicitly disabled in Phase 4 configuration.")
        con.print_info("Dark mode setting skipped as per configuration.")

    # --- Final Summary ---
    if overall_success:
        app_logger.info("Phase 4 (GNOME Configuration & Direct Git Extensions Install) completed successfully.")
        con.print_success("Phase 4: GNOME Configuration & Direct Git Extensions Install completed successfully.")
        con.print_warning("IMPORTANT: A logout/login or GNOME Shell restart (Alt+F2, type 'r', press Enter) "
                          "is likely required for all GNOME changes (especially new extensions) to take full effect.")
    else:
        app_logger.error("Phase 4 (GNOME Configuration & Direct Git Extensions Install) completed with errors.")
        con.print_error("Phase 4: GNOME Configuration & Direct Git Extensions Install completed with errors. Please review the logs.")
    return overall_success