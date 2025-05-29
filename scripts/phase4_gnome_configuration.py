import subprocess
import sys
import os
import shlex 
from pathlib import Path
from typing import Optional, Dict, List
import logging
import time 

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils 
from scripts.logger_utils import app_logger 

# --- Constants ---
USER_EXTENSIONS_BASE_DIR_REL_PATH = Path(".local/share/gnome-shell/extensions") # Relative to user's home
USER_THEMES_BASE_DIR_REL_PATH = Path(".themes") # Relative to user's home for GTK/WM themes

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
    build_handles_install = ext_cfg.get("build_handles_install", False)

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
        sanitized_ext_key = ext_key.replace(" ", "_")
        temp_parent_dir_name_prefix = f"gnome_ext_clone_{sanitized_ext_key}_{os.getpid()}_{int(time.time())}"
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

            if build_handles_install: # Check the new flag
                app_logger.info(f"Extension '{name}' build command is expected to handle installation. Verifying final destination.")
                final_metadata_path = final_extension_dest_path_abs / 'metadata.json'
                check_final_metadata_cmd = f"test -f {shlex.quote(str(final_metadata_path))}"
                
                # Use a try-except block for this check to ensure cleanup if something goes wrong
                try:
                    metadata_exists_at_dest_proc = system_utils.run_command(
                        check_final_metadata_cmd, run_as_user=target_user, shell=True,
                        check=False, capture_output=True, logger=app_logger, print_fn_info=None
                    )
                    if metadata_exists_at_dest_proc.returncode == 0:
                        con.print_success(f"Extension '{name}' (UUID: {uuid}) successfully installed by its build command to '{final_extension_dest_path_abs}'.")
                        app_logger.info(f"Extension '{name}' (UUID: {uuid}) verified at final destination after build_handles_install.")
                        # temp_clone_parent_dir_obj will be cleaned up in the 'finally' block of the main try-except
                        return True # Installation successful
                    else:
                        con.print_error(f"'metadata.json' not found in final destination '{final_metadata_path}' after build_handles_install for extension '{name}'. Build command may have failed to install correctly.")
                        app_logger.error(f"metadata.json missing in final destination for '{name}' after build_handles_install: {final_metadata_path}")
                        return False # Installation failed
                except Exception as e_verify:
                    con.print_error(f"Error verifying installation for '{name}' at final destination: {e_verify}")
                    app_logger.error(f"Error verifying final installation for '{name}': {e_verify}", exc_info=True)
                    return False
        else:
            app_logger.info(f"No build command specified for '{name}'.")

        # If build_handles_install is False, or no build command was run, proceed with original logic:
        # Determine the actual source path of extension files within the clone
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

def _install_git_theme(
    theme_key: str,
    theme_cfg: Dict[str, any],
    target_user: str,
    target_user_home: Path # Already resolved absolute path to user's home
) -> bool:
    """
    Clones a GTK/WM theme from Git into a temporary directory,
    optionally runs a build command, then moves the relevant (sub)directory
    to the user's local themes folder (~/.themes/RepoName).
    Applying the theme is NOT handled by this function.
    """
    friendly_name = theme_cfg.get("name", theme_key) # For display
    git_url = theme_cfg.get("url")
    build_command_template = theme_cfg.get("build_command", "")
    theme_source_subdir_in_clone = theme_cfg.get("theme_source_subdir", "")

    if not git_url:
        con.print_error(f"Missing 'url' for Git-based theme '{friendly_name}'. Skipping installation.")
        app_logger.error(f"Missing 'url' for Git-based theme '{friendly_name}' (key: {theme_key}).")
        return False

    app_logger.info(f"Processing Git-based theme '{friendly_name}' from URL '{git_url}' for user '{target_user}'.")
    con.print_sub_step(f"Installing Git-based theme: {friendly_name}")

    repo_name_from_url = Path(git_url).name.removesuffix(".git")
    if not repo_name_from_url:
        con.print_error(f"Could not determine repository name from URL '{git_url}' for theme '{friendly_name}'.")
        app_logger.error(f"Could not determine repo name for theme '{friendly_name}' from URL '{git_url}'.")
        return False

    user_themes_dir_abs = target_user_home / USER_THEMES_BASE_DIR_REL_PATH
    final_theme_dest_path_abs = user_themes_dir_abs / repo_name_from_url
    temp_clone_parent_dir_obj: Optional[Path] = None

    try:
        if not system_utils.ensure_dir_exists(
            user_themes_dir_abs, target_user=target_user, logger=app_logger,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_success=None
        ):
            con.print_error(f"Failed to create or verify user themes directory: {user_themes_dir_abs}. Cannot install theme '{friendly_name}'.")
            app_logger.error(f"Failed to ensure themes directory '{user_themes_dir_abs}' for user '{target_user}'.")
            return False

        temp_parent_dir_name_prefix = f"gnome_theme_clone_{theme_key}_{os.getpid()}_{int(time.time())}"
        user_cache_dir_abs = target_user_home / ".cache"
        system_utils.ensure_dir_exists(user_cache_dir_abs, target_user=target_user, logger=app_logger, print_fn_info=None)

        temp_clone_parent_dir_str = ""
        try:
            proc_mktemp_cache = system_utils.run_command(
                f"mktemp -d -p {shlex.quote(str(user_cache_dir_abs))} {temp_parent_dir_name_prefix}_XXXXXX",
                run_as_user=target_user, shell=True, capture_output=True, check=True, logger=app_logger, print_fn_info=None
            )
            temp_clone_parent_dir_str = proc_mktemp_cache.stdout.strip()
        except Exception:
            app_logger.warning(f"Failed to create temp dir in user's .cache for '{friendly_name}', trying system /tmp.")
            proc_mktemp_tmp = system_utils.run_command(
                f"mktemp -d -t {temp_parent_dir_name_prefix}_XXXXXX",
                run_as_user=target_user, shell=True, capture_output=True, check=True, logger=app_logger, print_fn_info=None
            )
            temp_clone_parent_dir_str = proc_mktemp_tmp.stdout.strip()

        if not temp_clone_parent_dir_str:
            raise Exception("Failed to create any temporary directory for cloning theme.")
        
        temp_clone_parent_dir_obj = Path(temp_clone_parent_dir_str)
        app_logger.info(f"Created temporary parent directory for theme clone: {temp_clone_parent_dir_obj} (as user '{target_user}')")
        
        cloned_repo_path_in_temp_abs = temp_clone_parent_dir_obj / repo_name_from_url

        con.print_info(f"Cloning theme '{git_url}' into '{cloned_repo_path_in_temp_abs}' as user '{target_user}'...")
        git_clone_cmd = ["git", "clone", "--depth=1", git_url, str(cloned_repo_path_in_temp_abs)]
        system_utils.run_command(
            git_clone_cmd, run_as_user=target_user,
            capture_output=True, check=True, print_fn_info=con.print_info, logger=app_logger
        )
        app_logger.info(f"Successfully cloned theme '{friendly_name}' to '{cloned_repo_path_in_temp_abs}' as user '{target_user}'.")

        if build_command_template:
            processed_build_command = build_command_template.replace("$HOME", str(target_user_home))
            con.print_info(f"Running build command '{processed_build_command}' for theme '{friendly_name}' in '{cloned_repo_path_in_temp_abs}' as user '{target_user}'...")
            system_utils.run_command(
                processed_build_command, cwd=str(cloned_repo_path_in_temp_abs),
                run_as_user=target_user, shell=True, capture_output=True, check=True,
                print_fn_info=con.print_info, logger=app_logger
            )
            app_logger.info(f"Build command '{processed_build_command}' completed for theme '{friendly_name}' as user '{target_user}'.")
        else:
            app_logger.info(f"No build command specified for theme '{friendly_name}'.")

        effective_theme_source_path_abs = cloned_repo_path_in_temp_abs
        if theme_source_subdir_in_clone:
            effective_theme_source_path_abs = cloned_repo_path_in_temp_abs / theme_source_subdir_in_clone
            app_logger.info(f"Using subdirectory '{theme_source_subdir_in_clone}' as effective theme source: {effective_theme_source_path_abs}")

        theme_check_script = (
            f"dir={shlex.quote(str(effective_theme_source_path_abs))}; "
            f"test -d \"$dir\" && ("
            f"  test -f \"$dir/index.theme\" || "
            f"  test -d \"$dir/gtk-3.0\" || "
            f"  test -d \"$dir/gtk-4.0\" "
            f")"
        )
        theme_valid_proc = system_utils.run_command(
            theme_check_script, run_as_user=target_user, shell=True,
            check=False, capture_output=True, logger=app_logger, print_fn_info=None
        )
        if theme_valid_proc.returncode != 0:
            con.print_error(f"Directory '{effective_theme_source_path_abs}' does not appear to be a valid theme directory for '{friendly_name}'. Check 'theme_source_subdir' or build output.")
            app_logger.error(f"Validation failed for theme source path '{effective_theme_source_path_abs}' for theme '{friendly_name}'.")
            return False

        check_old_dest_cmd = f"test -d {shlex.quote(str(final_theme_dest_path_abs))}"
        old_dest_exists_proc = system_utils.run_command(
            check_old_dest_cmd, run_as_user=target_user, shell=True,
            check=False, capture_output=True, logger=app_logger, print_fn_info=None
        )
        if old_dest_exists_proc.returncode == 0:
            con.print_info(f"Removing existing theme directory at '{final_theme_dest_path_abs}' as user '{target_user}'...")
            rm_old_dest_cmd = f"rm -rf {shlex.quote(str(final_theme_dest_path_abs))}"
            system_utils.run_command(
                rm_old_dest_cmd, run_as_user=target_user, shell=True,
                check=True, print_fn_info=con.print_info, logger=app_logger
            )

        mv_cmd = f"mv {shlex.quote(str(effective_theme_source_path_abs))} {shlex.quote(str(final_theme_dest_path_abs))}"
        con.print_info(f"Moving '{effective_theme_source_path_abs}' to '{final_theme_dest_path_abs}' as user '{target_user}'...")
        system_utils.run_command(
            mv_cmd, run_as_user=target_user, shell=True,
            check=True, print_fn_info=con.print_info, logger=app_logger
        )

        con.print_success(f"Theme '{friendly_name}' installed successfully to '{final_theme_dest_path_abs}'.")
        app_logger.info(f"Git theme '{friendly_name}' installed to '{final_theme_dest_path_abs}' for user '{target_user}'.")
        return True

    except Exception as e:
        con.print_error(f"Failed to install Git-based theme '{friendly_name}'. Error: {e}")
        app_logger.error(f"Installation of Git-based theme '{friendly_name}' failed for user '{target_user}'. Error: {e}", exc_info=True)
        return False
    finally:
        if temp_clone_parent_dir_obj and temp_clone_parent_dir_obj.is_dir():
            app_logger.info(f"Cleaning up temporary theme clone parent directory: {temp_clone_parent_dir_obj} (as user '{target_user}')")
            cleanup_cmd = f"rm -rf {shlex.quote(str(temp_clone_parent_dir_obj))}"
            try:
                system_utils.run_command(cleanup_cmd, run_as_user=target_user, shell=True, check=False, print_fn_info=None, logger=app_logger)
            except Exception as e_cleanup:
                app_logger.warning(f"Failed to clean up temporary theme directory {temp_clone_parent_dir_obj} (user: {target_user}): {e_cleanup}")

def _apply_gnome_setting( target_user: str, schema: str, key: str, value_str: str, setting_description: str ) -> bool:
    """Applies a GSetting for the target user. value_str is the string representation of the value."""
    app_logger.info(f"Applying GSetting for user '{target_user}': Schema='{schema}', Key='{key}', Value='{value_str}' ({setting_description})")
    con.print_sub_step(f"Applying GSetting: {setting_description}...")
    
    cmd_for_gsettings = f"gsettings set {shlex.quote(schema)} {shlex.quote(key)} {value_str}"
    full_cmd_with_dbus = f"dbus-run-session -- {cmd_for_gsettings}"
    
    try:
        system_utils.run_command(
            full_cmd_with_dbus, 
            run_as_user=target_user, 
            shell=True, 
            capture_output=True, 
            check=True, 
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error, 
            logger=app_logger
        )
        con.print_success(f"GSetting '{setting_description}' applied successfully for user '{target_user}'.")
        app_logger.info(f"GSetting '{setting_description}' applied for '{target_user}'.")
        return True
    except subprocess.CalledProcessError as e:
        app_logger.error(f"Failed to apply GSetting '{setting_description}' for user '{target_user}'. Exit: {e.returncode}, Stderr: {e.stderr or e.stdout}", exc_info=False)
        return False
    except Exception as e_unexp: 
        con.print_error(f"Unexpected error applying GSetting '{setting_description}' for user '{target_user}': {e_unexp}")
        app_logger.error(f"Unexpected error applying GSetting '{setting_description}' for '{target_user}': {e_unexp}", exc_info=True)
        return False

def _apply_gnome_theme_settings(target_user: str, gsettings_theme_name: str, theme_friendly_name: str) -> bool:
    """Applies GTK and Window Manager (WM) theme settings using GSettings."""
    con.print_sub_step(f"Applying theme '{theme_friendly_name}' (GSettings name: '{gsettings_theme_name}')...")
    app_logger.info(f"Applying GTK and WM theme '{gsettings_theme_name}' for user '{target_user}'.")

    gsettings_value_str = f"'{gsettings_theme_name}'"

    gtk_theme_success = _apply_gnome_setting(
        target_user,
        "org.gnome.desktop.interface",
        "gtk-theme",
        gsettings_value_str,
        f"GTK Theme to {theme_friendly_name}"
    )

    wm_theme_success = _apply_gnome_setting(
        target_user,
        "org.gnome.desktop.wm.preferences",
        "theme",
        gsettings_value_str,
        f"Window Manager (Titlebar) Theme to {theme_friendly_name}"
    )

    if gtk_theme_success and wm_theme_success:
        con.print_success(f"Theme '{theme_friendly_name}' applied successfully for GTK and Window Manager.")
        app_logger.info(f"Successfully applied theme '{gsettings_theme_name}' for GTK and WM for user '{target_user}'.")
        return True
    else:
        con.print_warning(f"One or more GSettings failed while applying theme '{theme_friendly_name}'. Check details above.")
        app_logger.warning(f"Failed to fully apply theme '{gsettings_theme_name}' for user '{target_user}'. GTK success: {gtk_theme_success}, WM success: {wm_theme_success}")
        return False

def _apply_dark_mode(target_user: str) -> bool:
    """Applies dark mode settings for the target user."""
    app_logger.info(f"Setting dark mode for user '{target_user}'.")
    con.print_sub_step("Applying Dark Mode settings...")
    
    color_scheme_success = _apply_gnome_setting(
        target_user, 
        "org.gnome.desktop.interface", 
        "color-scheme", 
        "'prefer-dark'", 
        "Color Scheme to Prefer Dark"
    )
    
    gtk_theme_success = _apply_gnome_setting(
        target_user, 
        "org.gnome.desktop.interface", 
        "gtk-theme", 
        "'Adwaita-dark'", 
        "GTK Theme to Adwaita-dark"
    )
    
    if not color_scheme_success: 
        app_logger.warning(f"Failed to set 'color-scheme' to 'prefer-dark' for user '{target_user}'.")
    if not gtk_theme_success: 
        app_logger.warning(f"Failed to set 'gtk-theme' to 'Adwaita-dark' for user '{target_user}'.")
        
    return color_scheme_success

# --- Main Phase Function ---
def run_phase4(app_config: dict) -> bool:
    app_logger.info("Starting Phase 4: GNOME Configuration, Extensions & Themes.")
    con.print_step("PHASE 4: GNOME Configuration, Extensions & Themes")
    overall_success = True
    
    phase4_config = config_loader.get_phase_data(app_config, "phase4_gnome_configuration")
    if not isinstance(phase4_config, dict):
        app_logger.warning("No valid Phase 4 configuration data found. Skipping GNOME configuration.")
        con.print_warning("No Phase 4 configuration data found. Skipping GNOME configuration.")
        return True 

    target_user = system_utils.get_target_user(
        logger=app_logger, print_fn_info=con.print_info, 
        print_fn_error=con.print_error, print_fn_warning=con.print_warning
    )
    if not target_user: 
        return False 
    
    target_user_home = system_utils.get_user_home_dir(target_user, logger=app_logger, print_fn_error=con.print_error)
    if not target_user_home: 
        app_logger.error(f"CRITICAL: Could not determine home directory for '{target_user}'. Aborting GNOME configuration phase.")
        return False

    app_logger.info(f"Running GNOME configurations for user: {target_user} (Home: {target_user_home})")
    con.print_info(f"Running GNOME configurations for: [bold cyan]{target_user}[/bold cyan]")

    # --- Step 1: Install support tools (DNF, Pip, Flatpak) ---
    con.print_info("\nStep 1: Installing support tools (git, build tools, optional utilities)...")
    app_logger.info("Phase 4, Step 1: Installing support tools.")
    
    dnf_packages_ph4 = phase4_config.get("dnf_packages", [])
    if phase4_config.get("gnome_extensions") or phase4_config.get("gnome_themes"):
        git_found = any(pkg == "git-core" or pkg == "git" for pkg in dnf_packages_ph4 if isinstance(pkg, str))
        if not git_found:
            app_logger.info("Adding 'git-core' to DNF packages as Git extensions or themes are configured and git was not explicitly listed.")
            dnf_packages_ph4.append("git-core")

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
    user_extensions_dir_abs = target_user_home / USER_EXTENSIONS_BASE_DIR_REL_PATH
    con.print_info(f"\nStep 2: Ensuring GNOME Shell user extensions base directory exists ({user_extensions_dir_abs})...")
    app_logger.info(f"Phase 4, Step 2: Ensuring extensions base directory: {user_extensions_dir_abs}")
    if not system_utils.ensure_dir_exists(
        user_extensions_dir_abs, 
        target_user=target_user, 
        logger=app_logger,
        print_fn_info=con.print_info,
        print_fn_error=con.print_error,
        print_fn_success=con.print_success 
    ):
        con.print_error(f"CRITICAL: Could not create or verify the user's GNOME Shell extensions base directory ({user_extensions_dir_abs}). Extensions might not install.")
        app_logger.error(f"CRITICAL: Failed to ensure extensions base directory '{user_extensions_dir_abs}' for user '{target_user}'.")
        # Not returning False here to allow theme installation to proceed if desired.
        # overall_success will reflect failure if extension installs subsequently fail.
        overall_success = False # Mark that there was an issue.

    # --- Step 3: Install GNOME Shell Extensions directly from Git ---
    git_extensions_config_map: Dict[str, Dict] = phase4_config.get("gnome_extensions", {}) 
    if git_extensions_config_map:
        con.print_info("\nStep 3: Installing GNOME Shell Extensions from Git...")
        app_logger.info("Phase 4, Step 3: Installing Git-based GNOME extensions.")
        any_ext_failed = False
        for ext_key, ext_config_dict in git_extensions_config_map.items():
            if not isinstance(ext_config_dict, dict): 
                app_logger.warning(f"Invalid configuration for Git extension '{ext_key}' (not a dictionary). Skipping.")
                con.print_warning(f"Invalid configuration for Git extension '{ext_key}'. Skipping.")
                any_ext_failed = True
                continue
            
            if ext_config_dict.get("type") != "git": 
                app_logger.info(f"Skipping extension '{ext_config_dict.get('name', ext_key)}' as its type is not 'git' (type: {ext_config_dict.get('type')}). This installation method only handles 'git' type extensions.")
                con.print_info(f"Skipping non-Git type extension: {ext_config_dict.get('name', ext_key)}")
                continue 
                
            if not _install_git_extension_direct_move(ext_key, ext_config_dict, target_user, target_user_home): 
                any_ext_failed = True 
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
        
    # --- Step 4: Install and Apply GNOME Themes ---
    con.print_info("\nStep 4: Installing and Applying GNOME Themes...")
    app_logger.info("Phase 4, Step 4: Installing and Applying GNOME Themes.")
    gnome_themes_config: Dict[str, Dict] = phase4_config.get("gnome_themes", {})
    any_theme_failed_install = False
    any_theme_failed_apply = False

    if gnome_themes_config:
        for theme_key, theme_cfg_dict in gnome_themes_config.items():
            if not isinstance(theme_cfg_dict, dict):
                app_logger.warning(f"Invalid configuration for theme '{theme_key}' (not a dictionary). Skipping.")
                con.print_warning(f"Invalid configuration for theme '{theme_key}'. Skipping.")
                any_theme_failed_install = True
                continue
            
            if theme_cfg_dict.get("type") != "git":
                app_logger.info(f"Skipping theme '{theme_cfg_dict.get('name', theme_key)}' as its type is not 'git'.")
                con.print_info(f"Skipping non-Git type theme: {theme_cfg_dict.get('name', theme_key)}")
                continue

            theme_installed = _install_git_theme(theme_key, theme_cfg_dict, target_user, target_user_home)
            if not theme_installed:
                any_theme_failed_install = True
                app_logger.warning(f"Installation failed for theme: {theme_cfg_dict.get('name', theme_key)}")
                continue 

            if theme_cfg_dict.get("apply", False):
                gsettings_name = theme_cfg_dict.get("gsettings_name")
                friendly_name_for_apply = theme_cfg_dict.get("name", theme_key) # Use friendly name for messages
                if not gsettings_name:
                    con.print_error(f"Theme '{friendly_name_for_apply}' is set to apply, but 'gsettings_name' is missing in config. Cannot apply.")
                    app_logger.error(f"Cannot apply theme '{friendly_name_for_apply}': 'gsettings_name' missing from config for key '{theme_key}'.")
                    any_theme_failed_apply = True
                    continue
                
                if not _apply_gnome_theme_settings(target_user, gsettings_name, friendly_name_for_apply):
                    any_theme_failed_apply = True
                    app_logger.warning(f"Failed to apply theme settings for: {friendly_name_for_apply} (GSettings name: {gsettings_name})")
        
        if any_theme_failed_install or any_theme_failed_apply:
            overall_success = False
            con.print_warning("One or more GNOME themes encountered installation or application issues.")
        else:
            con.print_success("All configured GNOME themes processed successfully.")
            app_logger.info("All configured GNOME themes processed.")
    else:
        app_logger.info("No GNOME themes configured for installation in Phase 4.")
        con.print_info("No GNOME themes configured for installation.")

    # --- Step 5: Set Dark Mode ---
    con.print_info("\nStep 5: Setting Dark Mode...")
    app_logger.info("Phase 4, Step 5: Setting Dark Mode.")
    if phase4_config.get("set_dark_mode", True):
        if not _apply_dark_mode(target_user): 
            app_logger.warning(f"Dark mode setting for user '{target_user}' encountered issues.")
            # Not changing overall_success as this is less critical.
    else: 
        app_logger.info("Dark mode setting explicitly disabled in Phase 4 configuration.")
        con.print_info("Dark mode setting skipped as per configuration.")

    # --- Final Summary ---
    if overall_success:
        app_logger.info("Phase 4 (GNOME Configuration, Extensions & Themes) completed successfully.")
        con.print_success("Phase 4: GNOME Configuration, Extensions & Themes completed successfully.")
        con.print_warning("IMPORTANT: A logout/login or GNOME Shell restart (Alt+F2, type 'r', press Enter) "
                          "is likely required for all GNOME changes (themes, extensions) to take full effect.")
    else:
        app_logger.error("Phase 4 (GNOME Configuration, Extensions & Themes) completed with errors.")
        con.print_error("Phase 4: GNOME Configuration, Extensions & Themes completed with errors. Please review the logs.")
    return overall_success