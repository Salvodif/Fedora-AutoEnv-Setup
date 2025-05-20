# Fedora-AutoEnv-Setup/scripts/phase4_gnome_configuration.py

import subprocess
import sys
import os
import shlex 
from pathlib import Path
import tempfile 
from typing import Optional, Dict, List
import logging 
import time # <<< IMPORT MISSING TIME MODULE

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils 
from scripts.logger_utils import app_logger 

# --- Constants ---
USER_EXTENSIONS_BASE_DIR_REL_PATH = Path(".local/share/gnome-shell/extensions") 

# --- Helper Functions ---

def _ensure_user_extensions_base_dir_exists(target_user: str, target_user_home: Path) -> bool:
    """Ensures the base directory for user GNOME Shell extensions exists."""
    user_extensions_path = target_user_home / USER_EXTENSIONS_BASE_DIR_REL_PATH
    app_logger.info(f"Ensuring base GNOME Shell extension directory exists for user '{target_user}': {user_extensions_path}")
    
    check_cmd = f"test -d {shlex.quote(str(user_extensions_path))}"
    try:
        proc = system_utils.run_command(
            check_cmd, run_as_user=target_user, shell=True,
            capture_output=True, check=False, print_fn_info=None, logger=app_logger
        )
        if proc.returncode == 0:
            app_logger.info(f"User extensions base directory already exists: {user_extensions_path}")
            return True
        
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
    Clones a GNOME Shell extension from Git into a temporary directory,
    optionally runs a build command within the clone,
    then moves the relevant (sub)directory to the user's local extensions folder,
    renaming it to the extension's UUID.
    Enabling is NOT handled by this function.
    """
    name = ext_cfg.get("name", ext_key)
    git_url = ext_cfg.get("url")
    build_command = ext_cfg.get("build_command", "") 
    extension_source_subdir_name = ext_cfg.get("extension_source_subdir", "") 
    uuid = ext_cfg.get("uuid") or ext_cfg.get("uuid_to_enable") 

    if not git_url:
        con.print_error(f"Missing 'url' for Git-based extension '{name}'."); return False
    if not uuid:
        con.print_error(f"Missing 'uuid' (or 'uuid_to_enable') for Git-based extension '{name}'. Cannot determine destination directory name."); return False

    app_logger.info(f"Processing Git-based extension '{name}' (UUID: {uuid}) from URL '{git_url}' for user '{target_user}'.")
    con.print_sub_step(f"Installing Git-based extension: {name} (UUID: {uuid})")

    repo_name_default = Path(git_url).name.removesuffix(".git") 
    user_extensions_dir = target_user_home / USER_EXTENSIONS_BASE_DIR_REL_PATH
    final_extension_path = user_extensions_dir / uuid 
    temp_clone_parent_dir_obj = None 

    try:
        # Using time.time() here, ensure 'import time' is at the top of the file.
        temp_parent_dir_name = f"gnome_ext_clone_{ext_key}_{os.getpid()}_{int(time.time())}"
        user_cache_dir = target_user_home / ".cache"
        
        mkdir_cache_cmd = f"mkdir -p {shlex.quote(str(user_cache_dir))}"
        system_utils.run_command(mkdir_cache_cmd, run_as_user=target_user, shell=True, check=False, logger=app_logger, print_fn_info=None)

        mktemp_cmd_user_cache = f"mktemp -d -p {shlex.quote(str(user_cache_dir))} {temp_parent_dir_name}_XXXXXX"
        mktemp_cmd_tmp = f"mktemp -d -t {temp_parent_dir_name}_XXXXXX" 

        temp_clone_parent_dir_str = ""
        try:
            proc = system_utils.run_command(mktemp_cmd_user_cache, run_as_user=target_user, shell=True, capture_output=True, check=True, logger=app_logger, print_fn_info=None)
            temp_clone_parent_dir_str = proc.stdout.strip()
        except Exception:
            app_logger.warning(f"Failed to create temp dir in user's .cache for {name}, trying system /tmp.")
            proc = system_utils.run_command(mktemp_cmd_tmp, run_as_user=target_user, shell=True, capture_output=True, check=True, logger=app_logger, print_fn_info=None)
            temp_clone_parent_dir_str = proc.stdout.strip()
        
        if not temp_clone_parent_dir_str: raise Exception("Failed to create any temporary directory.")
        temp_clone_parent_dir_obj = Path(temp_clone_parent_dir_str)
        app_logger.info(f"Created temporary parent directory for clone: {temp_clone_parent_dir_obj}")

        cloned_repo_path_in_temp = temp_clone_parent_dir_obj / repo_name_default

        con.print_info(f"Cloning '{git_url}' into '{cloned_repo_path_in_temp}'...")
        git_clone_cmd = ["git", "clone", "--depth=1", git_url, str(cloned_repo_path_in_temp)]
        system_utils.run_command(git_clone_cmd, run_as_user=target_user, capture_output=True, check=True, print_fn_info=con.print_info, logger=app_logger)
        app_logger.info(f"Successfully cloned {name} to {cloned_repo_path_in_temp}")

        if build_command:
            con.print_info(f"Running build command '{build_command}' for {name} in {cloned_repo_path_in_temp}...")
            system_utils.run_command(
                build_command, cwd=str(cloned_repo_path_in_temp), run_as_user=target_user, shell=True, 
                capture_output=True, check=True, print_fn_info=con.print_info, print_fn_sub_step=con.print_sub_step, logger=app_logger
            )
            app_logger.info(f"Build command '{build_command}' completed for {name}.")
        else: app_logger.info(f"No build command specified for {name}.")

        effective_source_path = cloned_repo_path_in_temp
        if extension_source_subdir_name:
            effective_source_path = cloned_repo_path_in_temp / extension_source_subdir_name
            app_logger.info(f"Using subdirectory '{extension_source_subdir_name}' as effective source: {effective_source_path}")
        
        check_dir_as_user_cmd = f"test -d {shlex.quote(str(effective_source_path))}"
        dir_exists_as_user_proc = system_utils.run_command(check_dir_as_user_cmd, run_as_user=target_user, shell=True, check=False, capture_output=True, logger=app_logger, print_fn_info=None)
        if dir_exists_as_user_proc.returncode != 0:
            con.print_error(f"Effective source path '{effective_source_path}' does not exist or is not a directory after clone/build for extension '{name}'."); return False
        
        metadata_check_cmd = f"test -f {shlex.quote(str(effective_source_path / 'metadata.json'))}"
        metadata_exists_proc = system_utils.run_command(metadata_check_cmd, run_as_user=target_user, shell=True, check=False, capture_output=True, logger=app_logger, print_fn_info=None)
        if metadata_exists_proc.returncode != 0:
            con.print_error(f"'metadata.json' not found in '{effective_source_path}'. Not a valid GNOME Shell extension directory. Check 'extension_source_subdir' or build process."); return False

        check_old_dest_cmd = f"test -d {shlex.quote(str(final_extension_path))}"
        old_dest_exists_proc = system_utils.run_command(check_old_dest_cmd, run_as_user=target_user, shell=True, check=False, capture_output=True, logger=app_logger, print_fn_info=None)
        if old_dest_exists_proc.returncode == 0:
            con.print_info(f"Removing existing extension directory at '{final_extension_path}'...")
            rm_old_dest_cmd = f"rm -rf {shlex.quote(str(final_extension_path))}"
            system_utils.run_command(rm_old_dest_cmd, run_as_user=target_user, shell=True, check=True, print_fn_info=con.print_info, logger=app_logger)

        mkdir_parent_dest_cmd = f"mkdir -p {shlex.quote(str(final_extension_path.parent))}"
        system_utils.run_command(mkdir_parent_dest_cmd, run_as_user=target_user, shell=True, check=True, print_fn_info=None, logger=app_logger) 

        mv_cmd = f"mv {shlex.quote(str(effective_source_path))} {shlex.quote(str(final_extension_path))}"
        con.print_info(f"Moving '{effective_source_path}' to '{final_extension_path}'...")
        system_utils.run_command(mv_cmd, run_as_user=target_user, shell=True, check=True, print_fn_info=con.print_info, logger=app_logger)

        con.print_success(f"Extension '{name}' (UUID: {uuid}) installed successfully to '{final_extension_path}'.")
        app_logger.info(f"Git extension '{name}' (UUID: {uuid}) installed via direct move for {target_user}.")
        return True
    except Exception as e:
        con.print_error(f"Failed to install Git-based extension '{name}' (UUID: {uuid}). Error: {e}")
        app_logger.error(f"Installation of Git-based extension '{name}' (UUID: {uuid}) failed for user '{target_user}'. Error: {e}", exc_info=True)
        return False
    finally:
        if temp_clone_parent_dir_obj and temp_clone_parent_dir_obj.exists():
            app_logger.info(f"Cleaning up temporary clone parent directory: {temp_clone_parent_dir_obj}")
            cleanup_cmd = f"rm -rf {shlex.quote(str(temp_clone_parent_dir_obj))}"
            try:
                system_utils.run_command(cleanup_cmd, run_as_user=target_user, shell=True, check=False, print_fn_info=None, logger=app_logger) 
            except Exception as e_cleanup:
                app_logger.warning(f"Failed to clean up temporary directory {temp_clone_parent_dir_obj}: {e_cleanup}")

def _apply_gnome_setting( target_user: str, schema: str, key: str, value: str, setting_description: str ) -> bool:
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
    if phase4_config.get("gnome_extensions") and "git-core" not in dnf_packages and "git" not in dnf_packages:
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
    if flatpak_apps: 
        if not system_utils.install_flatpak_apps(apps_to_install=flatpak_apps, system_wide=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger): 
            overall_success = False; con.print_warning("Flatpak app installation encountered issues.")
    else: app_logger.info("No Flatpak apps for Phase 4."); con.print_info("No Flatpak apps for Phase 4.")

    # --- Step 2: Ensure base extensions directory exists ---
    con.print_info(f"\nStep 2: Ensuring GNOME Shell user extensions base directory exists (~/{USER_EXTENSIONS_BASE_DIR_REL_PATH})...")
    if not _ensure_user_extensions_base_dir_exists(target_user, target_user_home):
        con.print_error("CRITICAL: Could not create or verify the user's GNOME Shell extensions base directory. Cannot install extensions.")
        app_logger.error(f"CRITICAL: Failed to ensure extensions base directory for {target_user}.")
        return False 

    # --- Step 3: Install GNOME Shell Extensions directly from Git ---
    git_extensions_cfg = phase4_config.get("gnome_extensions", {}) 
    if git_extensions_cfg:
        con.print_info("\nStep 3: Installing GNOME Shell Extensions from Git by direct move...")
        all_ext_ok = True
        for ext_key, ext_val_cfg in git_extensions_cfg.items():
            if not isinstance(ext_val_cfg, dict): 
                app_logger.warning(f"Invalid config for Git ext '{ext_key}'. Skip."); con.print_warning(f"Invalid config Git ext '{ext_key}'."); all_ext_ok = False; continue
            if ext_val_cfg.get("type") != "git": # Process only "git" type extensions with this logic
                app_logger.info(f"Skipping extension '{ext_key}' as its type is not 'git' (type: {ext_val_cfg.get('type')}). This method only handles 'git' type extensions.")
                con.print_info(f"Skipping non-Git type extension: {ext_val_cfg.get('name', ext_key)}")
                continue
            if not _install_git_extension_direct_move(ext_key, ext_val_cfg, target_user, target_user_home): 
                all_ext_ok = False
        if not all_ext_ok: overall_success = False; con.print_warning("One or more Git-based GNOME extensions had install issues.")
        else: con.print_success("All configured Git-based GNOME extensions processed.")
    else: 
        app_logger.info("No extensions listed under 'gnome_extensions' key in Phase 4 configuration."); 
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