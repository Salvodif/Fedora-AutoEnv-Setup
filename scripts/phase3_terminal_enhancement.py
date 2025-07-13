# Fedora-AutoEnv-Setup/scripts/phase3_terminal_enhancement.py

import subprocess 
import sys
import os
import shutil # For shutil.which
import shlex 
from pathlib import Path
from typing import Optional, Dict 
import time # For time.sleep and unique backup naming
import logging # Retained for type hints if direct logger use was needed

# Adjust import path to reach parent directory for shared modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils 
from scripts.logger_utils import app_logger 

# --- Helper Functions ---
# _get_user_shell was moved to system_utils.get_user_shell
# _ensure_shell_in_etc_shells was moved to system_utils.ensure_shell_in_etc_shells
# _set_default_shell was moved to system_utils.set_default_shell
# _get_user_home was moved to system_utils.get_user_home_dir


def _copy_config_file_to_user_home(
    source_filename: str,
    source_subdir_in_project: str, # e.g., "zsh", "nano" relative to project root
    target_user: str,
    target_user_home: Path,
    project_root_dir: Path
) -> bool:
    """
    Copies a configuration file from the project's config directory (e.g., project_root/zsh/.zshrc)
    to the target user's home directory (e.g., /home/user/.zshrc).
    Manages backup of existing files. Uses `run_as_user` for file operations in user's home.
    """
    source_file_path = project_root_dir / source_subdir_in_project / source_filename
    # Target path is directly in user's home, e.g. /home/user/.zshrc, /home/user/.nanorc
    target_file_path_in_user_home = target_user_home / source_filename 
    
    app_logger.info(f"Preparing to copy '{source_filename}' from project dir '{source_file_path}' to user home '{target_file_path_in_user_home}' for user '{target_user}'.")

    if not source_file_path.is_file():
        con.print_warning(f"Source configuration file '{source_file_path}' not found. Skipping copy of '{source_filename}'.")
        app_logger.warning(f"Source file '{source_file_path}' for '{source_filename}' not found. Skipping copy.")
        return False 

    con.print_sub_step(f"Copying '{source_filename}' to {target_user}'s home directory ({target_file_path_in_user_home})...")

    backup_command_for_user_shell = ""
    try:
        test_exists_cmd = f"test -f {shlex.quote(str(target_file_path_in_user_home))}"
        test_exists_proc = system_utils.run_command(
            test_exists_cmd,
            run_as_user=target_user, shell=True, check=False, capture_output=True,
            print_fn_info=None, 
            logger=app_logger
        )
        target_exists_as_user = (test_exists_proc.returncode == 0)
        
        if target_exists_as_user:
            timestamp_str = f"backup_{Path.cwd().name.replace(' ','_')}_{int(time.time())}" # cwd().name provides project name context
            backup_target_path_in_user_home = target_user_home / f"{source_filename}.{timestamp_str}"
            
            backup_command_for_user_shell = f"cp -pf {shlex.quote(str(target_file_path_in_user_home))} {shlex.quote(str(backup_target_path_in_user_home))}"
            con.print_info(f"Existing '{target_file_path_in_user_home.name}' found. Will attempt to back it up to '{backup_target_path_in_user_home.name}' as user '{target_user}'.")
            app_logger.info(f"Target file '{target_file_path_in_user_home}' exists. Backup command (as user '{target_user}'): {backup_command_for_user_shell}")
        else:
            app_logger.info(f"Target file '{target_file_path_in_user_home}' does not exist for user '{target_user}'. No backup needed.")
    except Exception as e_check: 
        con.print_warning(f"Could not check for existing '{target_file_path_in_user_home.name}' for backup: {e_check}. Proceeding with copy attempt.")
        app_logger.warning(f"Error checking target file '{target_file_path_in_user_home}' for backup: {e_check}", exc_info=True)

    try:
        # This command assumes the target_user (when run_as_user is invoked) has read access to source_file_path.
        # If the script is run as root, sudo -u target_user cp <source_from_anywhere> <user_dest> works.
        # If script is run as user_A and target_user is user_A, cp works.
        # If script is user_A and target_user is user_B, this might fail if user_B cannot read source_file_path.
        # For this project's typical use (run script as self, or as root targeting SUDO_USER), this is usually fine.
        copy_command_for_user_shell = f"cp -f {shlex.quote(str(source_file_path))} {shlex.quote(str(target_file_path_in_user_home))}"
        
        full_command_for_user_shell = copy_command_for_user_shell
        if backup_command_for_user_shell: # If backup is needed, chain commands
            full_command_for_user_shell = f"{backup_command_for_user_shell} && {copy_command_for_user_shell}"
            
        system_utils.run_command(
            full_command_for_user_shell,
            run_as_user=target_user, 
            shell=True, # Commands are constructed for shell execution by the user
            check=True, 
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error,
            logger=app_logger
        )
        con.print_success(f"Successfully copied '{source_filename}' to {target_file_path_in_user_home}.")
        app_logger.info(f"Successfully copied '{source_filename}' to '{target_file_path_in_user_home}' as user '{target_user}'.")
        return True
    except Exception as e_copy: 
        # run_command will call con.print_error if check=True and command fails
        app_logger.error(f"Failed to copy '{source_filename}' to '{target_file_path_in_user_home}' (user: {target_user}): {e_copy}", exc_info=True)
        return False

# --- Main Phase Function ---

def run_phase3(app_config: dict) -> bool:
    con.print_step("PHASE 3: Terminal Enhancement")
    app_logger.info("Starting Phase 3: Terminal Enhancement.")
    overall_success = True 

    target_user = system_utils.get_target_user(
        logger=app_logger, print_fn_info=con.print_info,
        print_fn_error=con.print_error, print_fn_warning=con.print_warning
    )
    if not target_user:
        app_logger.error("Cannot determine target user for Phase 3. Aborting phase.")
        # con.print_error already called by get_target_user if it fails critically
        return False 

    target_user_home = system_utils.get_user_home_dir(target_user, logger=app_logger, print_fn_error=con.print_error)
    if not target_user_home:
        app_logger.error(f"Target user home for '{target_user}' not found. Aborting user-specific part of Phase 3.")
        return False

    con.print_info(f"Running terminal enhancements for user: [bold cyan]{target_user}[/bold cyan] (Home: {target_user_home})")
    app_logger.info(f"Running Phase 3 for user: {target_user}, Home: {target_user_home}")

    # --- Dotfile Copying ---
    project_root = Path(__file__).resolve().parent.parent
    
    if not _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root):
        con.print_warning("Failed to copy .nanorc.")
        app_logger.warning(f"Failed to copy .nanorc for user '{target_user}'")
        # Not critical enough to set overall_success = False by itself

    # --- Phase Completion Summary ---
    if overall_success: # This overall_success is from the top of run_phase3, modified by critical failures
        con.print_success("Phase 3: Terminal Enhancement process completed.")
        app_logger.info(f"Phase 3 process completed for user '{target_user}'. Status: {'Success' if overall_success else 'With Errors'}")
    else:
        con.print_error("Phase 3: Terminal Enhancement completed with errors. Please review the output and logs.")
        app_logger.error(f"Phase 3 process completed with errors for user '{target_user}'.")
    
    return overall_success