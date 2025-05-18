# Fedora-AutoEnv-Setup/scripts/phase3_terminal_enhancement.py

import subprocess 
import sys
import os
import shutil
import shlex 
from pathlib import Path
from typing import Optional, Dict 
import time # For time.sleep and unique backup naming

# Adjust import path to reach parent directory for shared modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils # Import the module
from scripts.logger_utils import app_logger # Import app_logger

# --- Helper Functions ---

# _get_target_user is now in system_utils.py


def _get_user_shell(username: str) -> Optional[str]:
    """Gets the current login shell for a specified user using getent."""
    app_logger.debug(f"Getting shell for user '{username}'.")
    try:
        process = system_utils.run_command(
            ["getent", "passwd", username], 
            capture_output=True, 
            check=True, # Ensure the command succeeds and user exists
            print_fn_info=None, # Suppress "Executing..." for this utility call
            logger=app_logger
        )
        # passwd entry format: name:password:UID:GID:GECOS:home_directory:shell
        shell_path = process.stdout.strip().split(":")[-1]
        if not shell_path: # Should not happen if getent succeeds for a valid user
            con.print_warning(f"Could not determine shell for user '{username}' from getent output.")
            app_logger.warning(f"Empty shell path from getent for user '{username}'.")
            return None
        return shell_path
    except subprocess.CalledProcessError:
        # User not found by getent or other error
        con.print_warning(f"Could not find user '{username}' via getent to determine shell.")
        app_logger.warning(f"User '{username}' not found via getent (CalledProcessError).")
        return None
    except Exception as e: 
        con.print_warning(f"Could not determine the current shell for user '{username}': {e}")
        app_logger.error(f"Exception getting shell for user '{username}': {e}", exc_info=True)
        return None

def _check_zsh_installed() -> Optional[str]:
    """
    Checks if Zsh is installed and returns its path. 
    Prefers common paths like /usr/bin/zsh or /bin/zsh.
    """
    app_logger.debug("Checking if Zsh is installed.")
    common_paths = ["/usr/bin/zsh", "/bin/zsh"] # Most typical locations
    for zsh_path_str in common_paths:
        zsh_path_obj = Path(zsh_path_str)
        if zsh_path_obj.is_file() and os.access(zsh_path_obj, os.X_OK):
            con.print_info(f"Zsh found at standard location: {zsh_path_str}")
            app_logger.info(f"Zsh found at {zsh_path_str}.")
            return zsh_path_str
            
    # Fallback to shutil.which if not in common paths
    zsh_path_which = shutil.which("zsh")
    if zsh_path_which:
        con.print_warning(f"Zsh found via 'which' at non-standard location: {zsh_path_which}.")
        con.print_info("Standard paths like /usr/bin/zsh or /bin/zsh are generally preferred for /etc/shells compatibility.")
        app_logger.warning(f"Zsh found via 'which' at {zsh_path_which}.")
        return zsh_path_which
        
    con.print_error("Zsh is not installed or not found in PATH. Please ensure Zsh is installed (e.g., via Phase 2).")
    app_logger.error("Zsh not found.")
    return None


def _ensure_shell_in_etc_shells(shell_path: str) -> bool:
    """
    Ensures the given shell_path is listed in /etc/shells. 
    Requires root privileges to modify /etc/shells.
    """
    if not shell_path: # Should not happen if _check_zsh_installed found something
        con.print_error("Cannot ensure empty shell path in /etc/shells.")
        app_logger.error("Empty shell_path passed to _ensure_shell_in_etc_shells.")
        return False

    # This function must run with effective root privileges to modify /etc/shells
    if os.geteuid() != 0:
        con.print_warning("Cannot modify /etc/shells without root privileges. Shell validity check for /etc/shells skipped.")
        # We'll let chsh attempt it; it will warn if the shell isn't listed.
        return True # Assume it's fine, or let chsh handle the warning/error.

    app_logger.info(f"Ensuring '{shell_path}' is in /etc/shells.")
    etc_shells_path = Path("/etc/shells")
    try:
        if not etc_shells_path.is_file():
            con.print_warning(f"File {etc_shells_path} not found. Cannot verify or add shell path.")
            # This is unusual. chsh will likely fail if /etc/shells is missing.
            app_logger.warning(f"{etc_shells_path} not found.")
            return False 

        # Read existing shells, ignoring comments and empty lines
        current_shells = []
        with open(etc_shells_path, 'r', encoding='utf-8') as f:
            current_shells = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        if shell_path in current_shells:
            con.print_info(f"Shell '{shell_path}' is already listed in {etc_shells_path}.")
            app_logger.info(f"'{shell_path}' already in {etc_shells_path}.")
            return True
        
        con.print_info(f"Shell '{shell_path}' not found in {etc_shells_path}. Attempting to add it...")
        
        # Make a backup of /etc/shells before modifying
        backup_etc_shells_path = f"{str(etc_shells_path)}.bak_{int(time.time())}"
        system_utils.run_command(
            ["cp", "-pf", str(etc_shells_path), backup_etc_shells_path],
            print_fn_info=con.print_info, print_fn_error=con.print_error,
            logger=app_logger
        )

        # Append the shell path. Using tee -a is robust.
        append_cmd_str = f"echo {shlex.quote(shell_path)} | tee -a {shlex.quote(str(etc_shells_path))} > /dev/null"
        system_utils.run_command(
            append_cmd_str,
            shell=True, # Necessary for the pipe and redirection
            check=True, # Fail if tee or echo fails
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            logger=app_logger
        )
        con.print_success(f"Successfully added '{shell_path}' to {etc_shells_path}.")
        app_logger.info(f"Added '{shell_path}' to {etc_shells_path}.")
        return True
    except Exception as e:
        con.print_error(f"Failed to process /etc/shells for '{shell_path}': {e}")
        app_logger.error(f"Error processing /etc/shells for '{shell_path}': {e}", exc_info=True)
        return False


def _set_default_shell(username: str, shell_path: str) -> bool:
    """Sets the default login shell for the user. Requires root privileges."""
    current_shell = _get_user_shell(username)
    if current_shell == shell_path:
        con.print_info(f"Shell '{shell_path}' is already the default shell for user '{username}'.")
        app_logger.info(f"'{shell_path}' is already default for '{username}'.")
        return True

    con.print_sub_step(f"Setting Zsh ('{shell_path}') as default shell for user '{username}'...")
    app_logger.info(f"Setting '{shell_path}' as default for '{username}'.")
    
    if os.geteuid() != 0:
        con.print_error(f"Cannot change shell for user '{username}'. This script part must be run as root (e.g., with sudo).")
        app_logger.error(f"Cannot change shell for '{username}': not root.")
        return False

    if not _ensure_shell_in_etc_shells(shell_path):
        con.print_warning(f"Could not ensure '{shell_path}' is in /etc/shells. `chsh` might warn or fail.")
        if not Path("/etc/shells").is_file():
             app_logger.error(f"Cannot set default shell: /etc/shells file not found, and could not ensure '{shell_path}' in it.")
             return False

    if not con.confirm_action(f"Change default shell for user '{username}' to '{shell_path}'?", default=True):
        con.print_warning("Shell change skipped by user.")
        app_logger.info(f"Shell change for '{username}' skipped by user.")
        return True 

    try:
        system_utils.run_command(
            ["chsh", "-s", shell_path, username],
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error,
            logger=app_logger
        )
        
        time.sleep(0.5) 
        new_shell_check = _get_user_shell(username)
        
        if new_shell_check == shell_path:
            con.print_success(f"Successfully set Zsh as the default shell for '{username}'.")
            app_logger.info(f"Successfully set Zsh for '{username}'.")
            con.print_info("Note: The shell change will take effect upon the user's next login.")
        else:
            con.print_warning(f"chsh command executed to set shell to '{shell_path}' for '{username}'.")
            con.print_warning(f"Verification via getent currently shows shell as: '{new_shell_check or 'unknown'}'.")
            app_logger.warning(f"chsh for '{username}' to '{shell_path}' ran, but getent shows '{new_shell_check}'.")
            con.print_info("Please verify the shell after the user's next login. The change likely succeeded if chsh reported no fatal errors.")
        
        return True
    except subprocess.CalledProcessError as e:
        con.print_error(f"The 'chsh' command failed to set shell for '{username}'. Exit code: {e.returncode}")
        app_logger.error(f"chsh command failed for '{username}' (CalledProcessError): {e}", exc_info=False)
        return False
    except Exception as e: 
        con.print_error(f"An unexpected error occurred while trying to set default shell for '{username}': {e}")
        app_logger.error(f"Unexpected error setting default shell for '{username}': {e}", exc_info=True)
        return False


def _get_user_home(username: str) -> Optional[Path]:
    """Gets the home directory of a specified user."""
    app_logger.debug(f"Getting home directory for user '{username}'.")
    try:
        proc = system_utils.run_command(
            ["getent", "passwd", username], capture_output=True, check=True,
            print_fn_info=None, # Suppress "Executing..." for this utility call
            logger=app_logger
        )
        home_dir_str = proc.stdout.strip().split(":")[5]
        if not home_dir_str:
            con.print_error(f"Could not determine home directory for user '{username}'.")
            app_logger.error(f"Empty home directory from getent for '{username}'.")
            return None
        return Path(home_dir_str)
    except Exception as e:
        con.print_error(f"Error getting home directory for user '{username}': {e}")
        app_logger.error(f"Exception getting home dir for '{username}': {e}", exc_info=True)
        return None

def _copy_config_file_to_user_home(
    source_filename: str,
    source_subdir: str, 
    target_user: str,
    target_user_home: Path,
    project_root_dir: Path
) -> bool:
    """
    Copies a configuration file from the project's subdirectory to the target user's home.
    Backs up the existing file in the user's home.
    """
    source_file_path = project_root_dir / source_subdir / source_filename
    target_file_path = target_user_home / source_filename
    app_logger.info(f"Copying '{source_filename}' from '{source_file_path}' to '{target_file_path}' for user '{target_user}'.")

    if not source_file_path.is_file():
        con.print_warning(f"Source configuration file '{source_file_path}' not found. Skipping copy.")
        app_logger.warning(f"Source file '{source_file_path}' not found. Skipping copy.")
        return False 

    con.print_sub_step(f"Copying '{source_filename}' to {target_user}'s home directory ({target_file_path})...")

    backup_command_str = ""
    try:
        target_exists_as_user = False
        if os.geteuid() == 0 : 
             test_exists_proc = system_utils.run_command(
                f"test -f {shlex.quote(str(target_file_path))}",
                run_as_user=target_user, shell=True, check=False, capture_output=True,
                print_fn_info=None, 
                logger=app_logger
            )
             if test_exists_proc.returncode == 0:
                 target_exists_as_user = True
        elif target_file_path.exists(): 
            target_exists_as_user = True


        if target_exists_as_user:
            timestamp_str = f"backup_{int(time.time())}_{Path.cwd().name.replace(' ','_')}"
            backup_target_path = target_user_home / f"{source_filename}.{timestamp_str}"
            
            backup_command_str = f"cp -pf {shlex.quote(str(target_file_path))} {shlex.quote(str(backup_target_path))}"
            con.print_info(f"Existing '{target_file_path.name}' found. Will attempt to back it up to '{backup_target_path.name}'.")
            app_logger.info(f"Target file '{target_file_path}' exists. Backup command: {backup_command_str}")
        else:
            con.print_info(f"No existing '{target_file_path.name}' found in {target_user}'s home. No backup needed.")
            app_logger.info(f"Target file '{target_file_path}' does not exist. No backup needed.")
    except Exception as e_check:
        con.print_warning(f"Could not check for existing '{target_file_path.name}' for backup: {e_check}. Proceeding with copy.")
        app_logger.warning(f"Error checking target file for backup: {e_check}", exc_info=True)

    try:
        copy_command_str = f"cp -f {shlex.quote(str(source_file_path))} {shlex.quote(str(target_file_path))}"
        
        full_command_for_user = copy_command_str
        if backup_command_str:
            full_command_for_user = f"{backup_command_str} && {copy_command_str}"
            
        system_utils.run_command(
            full_command_for_user,
            run_as_user=target_user,
            shell=True, 
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            logger=app_logger
        )
        con.print_success(f"Successfully copied '{source_filename}' to {target_user_home}.")
        app_logger.info(f"Successfully copied '{source_filename}' to '{target_user_home}'.")
        return True
    except Exception as e_copy: 
        con.print_error(f"Failed to copy '{source_filename}' to {target_user_home}.")
        app_logger.error(f"Failed to copy '{source_filename}' to '{target_user_home}': {e_copy}", exc_info=True)
        return False

# --- Main Phase Function ---

def run_phase3(app_config: dict) -> bool:
    """Executes Phase 3: Terminal Enhancement."""
    con.print_step("PHASE 3: Terminal Enhancement")
    app_logger.info("Starting Phase 3: Terminal Enhancement.")
    overall_success = True

    target_user = system_utils.get_target_user(
        logger=app_logger,
        print_fn_info=con.print_info,
        print_fn_error=con.print_error,
        print_fn_warning=con.print_warning
    )
    if not target_user:
        app_logger.error("Cannot determine target user for Phase 3. Aborting phase.")
        return False 


    target_user_home = _get_user_home(target_user)
    if not target_user_home:
        con.print_warning(f"Cannot determine home directory for target user '{target_user}'. Config file copy will be skipped.")
        app_logger.warning(f"Cannot determine home directory for '{target_user}'. Config file copy will be skipped.")

    con.print_info(f"Running terminal enhancements for user: [bold cyan]{target_user}[/bold cyan]")
    app_logger.info(f"Running Phase 3 for user: {target_user}")
    
    zsh_path = _check_zsh_installed()
    if not zsh_path:
        con.print_error("Zsh is not found. Cannot proceed with Zsh-specific enhancements.")
        return False 
    
    if not _set_default_shell(target_user, zsh_path):
        overall_success = False 
        con.print_error("Failed to set Zsh as the default shell. Terminal experience might not be as intended.")

    phase3_config: Optional[Dict[str,str]] = config_loader.get_phase_data(app_config, "phase3_terminal_enhancement")
    if not phase3_config:
        con.print_info("No terminal enhancement commands found in configuration. Skipping plugin/tool installations.")
        app_logger.info("No 'phase3_terminal_enhancement' config found. Skipping plugin/tool installations.")
    else:
        con.print_info(f"\nApplying terminal enhancement commands for user '{target_user}'...")
        app_logger.info(f"Applying terminal enhancement commands for user '{target_user}'.")
        
        omz_custom_plugins_dir_cmd = "mkdir -p ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
        try:
            system_utils.run_command(
                omz_custom_plugins_dir_cmd, run_as_user=target_user, shell=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error,
                logger=app_logger)
        except Exception as e_mkdir: 
            con.print_warning(f"Could not ensure Oh My Zsh custom plugins directory for '{target_user}'. Plugin installs relying on it might fail.")
            app_logger.warning(f"Failed to create OMZ custom plugins dir for '{target_user}': {e_mkdir}", exc_info=True)

        for item_name, command_str in phase3_config.items():
            app_logger.debug(f"Processing enhancement item: {item_name}, command: {command_str}")
            if not isinstance(command_str, str) or not command_str.strip():
                con.print_warning(f"Skipping invalid command for item '{item_name}': Command is not a valid string or is empty.")
                app_logger.warning(f"Invalid command for '{item_name}': not a string or empty.")
                continue
            
            con.print_sub_step(f"Processing enhancement: {item_name}")
            
            if "ZSH_CUSTOM:~" in command_str: 
                con.print_warning(f"Warning for '{item_name}': Command uses 'ZSH_CUSTOM:~'. Standard is 'ZSH_CUSTOM:-'. Please verify config (e.g., use '$HOME' in default path for robustness).")
            if item_name == "zsh-eza" and "plugins/you-should-use" in command_str: # Specific typo check from original
                 con.print_warning(f"Warning for 'zsh-eza': Command might have an incorrect target directory '.../plugins/you-should-use'. Expected '.../plugins/zsh-eza'. Please verify config.")


            is_git_clone_cmd = "git clone" in command_str.lower() 
            should_skip_command_due_to_existence = False

            if is_git_clone_cmd:
                cmd_parts = shlex.split(command_str) 
                target_dir_in_cmd = ""
                if len(cmd_parts) > 0:
                    try:
                        git_idx = cmd_parts.index("git")
                        clone_idx = cmd_parts.index("clone", git_idx)
                        if len(cmd_parts) > clone_idx + 2: 
                             target_dir_in_cmd = cmd_parts[clone_idx + 2]
                    except ValueError: 
                        pass 

                if target_dir_in_cmd:
                    check_dir_exists_cmd = f"test -d {target_dir_in_cmd}" 
                    
                    try:
                        proc = system_utils.run_command(
                            check_dir_exists_cmd,
                            run_as_user=target_user,
                            shell=True, 
                            capture_output=True,
                            check=False, 
                            print_fn_info=None, 
                            logger=app_logger
                        )
                        if proc.returncode == 0: 
                            con.print_info(f"Destination for '{item_name}' ('{target_dir_in_cmd}') seems to exist. Skipping git clone.")
                            should_skip_command_due_to_existence = True
                        elif proc.returncode == 1: 
                            pass 
                        else: 
                             con.print_warning(f"Command '{check_dir_exists_cmd}' for '{item_name}' failed with unexpected exit code {proc.returncode}. Will attempt clone anyway.")
                             app_logger.warning(f"'test -d' for '{item_name}' failed. Exit: {proc.returncode}, Stderr: {proc.stderr.strip() if proc.stderr else 'N/A'}")
                             if proc.stderr: con.print_warning(f"Stderr from 'test -d' command: {proc.stderr.strip()}")

                    except Exception as e_check: 
                        con.print_warning(f"Could not verify existence for '{item_name}' due to an exception: {e_check}. Will attempt command.")
                        app_logger.warning(f"Exception checking existence for '{item_name}': {e_check}", exc_info=True)
                else:
                    con.print_warning(f"Could not reliably determine target directory for '{item_name}' from command '{command_str}'. Will attempt command without existence check.")
                    app_logger.warning(f"Cannot determine target dir for '{item_name}' from '{command_str}'. No existence check.")
            
            if should_skip_command_due_to_existence:
                con.print_info(f"Skipped applying '{item_name}' as target seems to exist.")
                continue

            try:
                system_utils.run_command(
                    command_str, 
                    run_as_user=target_user,
                    shell=True, 
                    capture_output=True,
                    check=True, 
                    print_fn_info=con.print_info,
                    print_fn_error=con.print_error,
                    print_fn_sub_step=con.print_sub_step,
                    logger=app_logger
                )
                con.print_success(f"Enhancement '{item_name}' applied successfully.")
                app_logger.info(f"Enhancement '{item_name}' applied successfully.")
            except subprocess.CalledProcessError as e: 
                if is_git_clone_cmd and e.returncode == 128 and e.stderr and "already exists and is not an empty directory" in e.stderr.lower():
                    con.print_info(f"Clone for '{item_name}' failed because destination likely already exists and is not empty (git reported). Considered skipped/existing.")
                    app_logger.info(f"Git clone for '{item_name}' failed as dir exists and not empty. Skipped.")
                else:
                    con.print_error(f"Failed to apply enhancement '{item_name}'. Review errors logged above.")
                    app_logger.error(f"Failed to apply enhancement '{item_name}' (CalledProcessError): {e.stderr if e.stderr else e.output}", exc_info=False)
                    overall_success = False
            except Exception as e_cmd: 
                con.print_error(f"An unexpected error occurred while applying enhancement '{item_name}': {e_cmd}")
                app_logger.error(f"Unexpected error applying enhancement '{item_name}': {e_cmd}", exc_info=True)
                overall_success = False

    if target_user_home:
        app_logger.info(f"Copying custom config files for user '{target_user}'.")
        con.print_info(f"\nCopying custom configuration files for user '{target_user}'...")
        project_root = Path(__file__).resolve().parent.parent 
        
        if not _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root):
            con.print_warning("Failed to copy .zshrc. User's Zsh experience might not be as intended.")

        if not _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root):
            con.print_warning("Failed to copy .nanorc.")
    else:
        con.print_warning("Skipping copy of .zshrc and .nanorc because target user's home directory could not be determined.")
        app_logger.warning("Skipping .zshrc and .nanorc copy: target_user_home not determined.")
                
    if overall_success:
        con.print_success("Phase 3: Terminal Enhancement completed successfully.")
        app_logger.info("Phase 3 completed successfully.")
    else:
        con.print_error("Phase 3: Terminal Enhancement completed with errors. Please review the output.")
        app_logger.error("Phase 3 completed with errors.")
    
    return overall_success