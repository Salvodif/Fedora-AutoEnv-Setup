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
            check=True, 
            print_fn_info=None, 
            logger=app_logger
        )
        shell_path = process.stdout.strip().split(":")[-1]
        if not shell_path: 
            con.print_warning(f"Could not determine shell for user '{username}' from getent output.")
            app_logger.warning(f"Empty shell path from getent for user '{username}'.")
            return None
        return shell_path
    except subprocess.CalledProcessError:
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
    common_paths = ["/usr/bin/zsh", "/bin/zsh"] 
    for zsh_path_str in common_paths:
        zsh_path_obj = Path(zsh_path_str)
        if zsh_path_obj.is_file() and os.access(zsh_path_obj, os.X_OK):
            app_logger.info(f"Zsh found at {zsh_path_str}.")
            return zsh_path_str
            
    zsh_path_which = shutil.which("zsh")
    if zsh_path_which:
        app_logger.warning(f"Zsh found via 'which' at {zsh_path_which}.")
        return zsh_path_which
        
    app_logger.info("Zsh not found by _check_zsh_installed.")
    return None


def _ensure_shell_in_etc_shells(shell_path: str) -> bool:
    if not shell_path: 
        con.print_error("Cannot ensure empty shell path in /etc/shells.")
        app_logger.error("Empty shell_path passed to _ensure_shell_in_etc_shells.")
        return False

    if os.geteuid() != 0:
        con.print_warning("Cannot modify /etc/shells without root privileges. Shell validity check for /etc/shells skipped.")
        return True 

    app_logger.info(f"Ensuring '{shell_path}' is in /etc/shells.")
    etc_shells_path = Path("/etc/shells")
    try:
        if not etc_shells_path.is_file():
            con.print_warning(f"File {etc_shells_path} not found. Cannot verify or add shell path.")
            app_logger.warning(f"{etc_shells_path} not found.")
            return False 

        current_shells = []
        with open(etc_shells_path, 'r', encoding='utf-8') as f:
            current_shells = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        if shell_path in current_shells:
            app_logger.info(f"'{shell_path}' already in {etc_shells_path}.")
            return True
        
        con.print_info(f"Shell '{shell_path}' not found in {etc_shells_path}. Attempting to add it...")
        
        backup_etc_shells_path = f"{str(etc_shells_path)}.bak_{int(time.time())}"
        system_utils.run_command(
            ["cp", "-pf", str(etc_shells_path), backup_etc_shells_path],
            print_fn_info=con.print_info, print_fn_error=con.print_error,
            logger=app_logger
        )

        append_cmd_str = f"echo {shlex.quote(shell_path)} | tee -a {shlex.quote(str(etc_shells_path))} > /dev/null"
        system_utils.run_command(
            append_cmd_str,
            shell=True, check=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error,
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
    current_shell = _get_user_shell(username)
    if current_shell == shell_path:
        con.print_info(f"Shell '{shell_path}' is already the default shell for user '{username}'.")
        app_logger.info(f"'{shell_path}' is already default for '{username}'.")
        return True

    con.print_sub_step(f"Setting Zsh ('{shell_path}') as default shell for user '{username}'...")
    app_logger.info(f"Setting '{shell_path}' as default for '{username}'.")
    
    if os.geteuid() != 0:
        con.print_error(f"Cannot change shell for user '{username}'. This script part must be run as root.")
        app_logger.error(f"Cannot change shell for '{username}': not root.")
        return False

    if not _ensure_shell_in_etc_shells(shell_path):
        con.print_warning(f"Could not ensure '{shell_path}' is in /etc/shells. `chsh` might warn or fail.")
        if not Path("/etc/shells").is_file():
             app_logger.error(f"Cannot set default shell: /etc/shells file not found.")
             return False
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
            con.print_info("Please verify the shell after the user's next login.")
        
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
    app_logger.debug(f"Getting home directory for user '{username}'.")
    try:
        proc = system_utils.run_command(
            ["getent", "passwd", username], capture_output=True, check=True,
            print_fn_info=None, 
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
    con.print_step("PHASE 3: Terminal Enhancement")
    app_logger.info("Starting Phase 3: Terminal Enhancement.")
    overall_success = True

    target_user = system_utils.get_target_user(
        logger=app_logger, print_fn_info=con.print_info,
        print_fn_error=con.print_error, print_fn_warning=con.print_warning
    )
    if not target_user:
        app_logger.error("Cannot determine target user for Phase 3. Aborting phase.")
        return False 

    target_user_home = _get_user_home(target_user)

    con.print_info(f"Running terminal enhancements for user: [bold cyan]{target_user}[/bold cyan]")
    app_logger.info(f"Running Phase 3 for user: {target_user}")

    zsh_path = _check_zsh_installed()
    current_shell = _get_user_shell(target_user)
    is_zsh_default = current_shell and "zsh" in Path(current_shell).name
    
    phase2_config = config_loader.get_phase_data(app_config, "phase2_basic_configuration")
    zsh_should_be_dnf_installed = "zsh" in [pkg.lower() for pkg in phase2_config.get("dnf_packages", [])]

    user_wants_to_proceed_with_enhancements = True 

    if not zsh_path:
        if zsh_should_be_dnf_installed:
            con.print_warning("Zsh was expected from Phase 2 DNF packages but is not currently found by this script.")
            con.print_info("This might mean Phase 2 failed, or Zsh isn't in PATH for this script's execution context.")
            if not con.confirm_action("Proceed with terminal enhancements (Oh My Zsh, plugins etc.)? (These may fail if Zsh is truly unavailable).", default=False):
                user_wants_to_proceed_with_enhancements = False
        else: 
            con.print_warning("Zsh is not installed. It's highly recommended to add 'zsh' to Phase 2 DNF packages.")
            con.print_info("The Oh My Zsh installer (if configured) might attempt to install Zsh system-wide or prompt you.")
            # No confirmation here about OMZ specifically, as per request. We assume if 'omz' is in config, user wants it.
            # But if Zsh itself is missing, we still need to confirm if user wants to proceed with *any* enhancements.
            if not con.confirm_action("Zsh is not found. Do you want to attempt terminal enhancements now? (Oh My Zsh might try to install Zsh or fail).", default=True):
                user_wants_to_proceed_with_enhancements = False
    elif not is_zsh_default:
        con.print_info(f"Zsh is installed ('{zsh_path}') but is not the default shell for '{target_user}'.")
        if not con.confirm_action(f"Set Zsh as default and proceed with further terminal enhancements for '{target_user}'?", default=True):
            user_wants_to_proceed_with_enhancements = False
            con.print_info("Zsh will not be set as default. Some enhancements might not apply as expected.")
            app_logger.info(f"User declined setting Zsh as default for '{target_user}'.")
    # If Zsh is installed and default, we assume user wants to proceed unless they say no to a general "enhancements" question (covered by `install.py` menu)
    # No specific OMZ prompt here, it will be installed if in config.

    if not user_wants_to_proceed_with_enhancements:
        con.print_info("Skipping Zsh-specific terminal enhancements based on user choice.")
        app_logger.info("User opted out of Zsh-specific terminal enhancements.")
        if target_user_home: 
            project_root_nano = Path(__file__).resolve().parent.parent
            _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root_nano)
        return True 

    app_logger.info("Proceeding with Zsh terminal enhancements.")

    if zsh_path and not is_zsh_default:
        if not _set_default_shell(target_user, zsh_path):
            overall_success = False
            con.print_error("Failed to set Zsh as default. This may impact Oh My Zsh functionality.")
    
    if not target_user_home: 
        con.print_error(f"Cannot determine home directory for '{target_user}'. Cannot proceed with Oh My Zsh, plugins, or dotfile copy.")
        app_logger.error(f"Target user home for '{target_user}' not found. Aborting user-specific part of Phase 3.")
        return False 

    phase3_config_commands = config_loader.get_phase_data(app_config, "phase3_terminal_enhancement").copy()
    
    omz_custom_plugins_dir_cmd = "mkdir -p ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
    try:
        system_utils.run_command(
            omz_custom_plugins_dir_cmd, run_as_user=target_user, shell=True,
            logger=app_logger, print_fn_info=con.print_info, print_fn_error=con.print_error
        )
    except Exception:
        con.print_warning("Could not ensure Oh My Zsh custom plugins directory exists. Plugin installations might fail.")
        app_logger.warning("Failed to create OMZ custom plugins directory.", exc_info=True)
        overall_success = False

    omz_install_key = "omz" 
    omz_install_command = phase3_config_commands.pop(omz_install_key, None)

    if omz_install_command:
        con.print_sub_step("Processing Oh My Zsh installation...")
        app_logger.info("Checking for existing Oh My Zsh installation.")
        omz_dir_check_cmd = "test -d $HOME/.oh-my-zsh"
        try:
            omz_exists_proc = system_utils.run_command(
                omz_dir_check_cmd, run_as_user=target_user, shell=True,
                check=False, capture_output=True, logger=app_logger, print_fn_info=None
            )
            if omz_exists_proc.returncode == 0:
                con.print_info("Oh My Zsh directory ($HOME/.oh-my-zsh) already exists. Skipping OMZ interactive installation script.")
                app_logger.info("OMZ directory exists, skipping its installer script execution.")
            else:
                con.print_info("Oh My Zsh directory not found. Running Oh My Zsh installation script...")
                con.print_panel(
                    "The Oh My Zsh installer is an [bold]interactive script[/].\n"
                    "Its output will be displayed directly below.\n"
                    "Please follow any prompts from the OMZ installer itself.\n"
                    "It may ask to change your default shell if this script hasn't already done so.",
                    title="Oh My Zsh Installation", style="yellow"
                )
                # Run OMZ installer with output visible to user for interaction
                # Pass print_fn_info=None so our run_command doesn't prefix OMZ's output with "Executing..."
                system_utils.run_command(
                    omz_install_command, run_as_user=target_user, shell=True,
                    capture_output=False, # CRITICAL: Let user see OMZ output directly
                    check=True, 
                    print_fn_info=None, # Let OMZ handle its own primary output
                    print_fn_error=con.print_error, # Still use our error for general failures
                    logger=app_logger
                )
                con.print_success("Oh My Zsh installation script finished.")
                app_logger.info("OMZ installation script finished.")
                con.print_warning("A new Zsh shell session may be required for all OMZ changes to take effect.")
        except Exception as e:
            con.print_error(f"Oh My Zsh installation process failed: {e}")
            app_logger.error(f"OMZ installation process failed: {e}", exc_info=True)
            overall_success = False
    
    if overall_success:
        for item_name, command_str in phase3_config_commands.items():
            app_logger.debug(f"Processing enhancement item: {item_name}, command: {command_str}")
            if not isinstance(command_str, str) or not command_str.strip():
                con.print_warning(f"Skipping invalid command for item '{item_name}'.")
                app_logger.warning(f"Invalid command for '{item_name}'.")
                continue
            
            con.print_sub_step(f"Processing: {item_name}")
            
            if "ZSH_CUSTOM:~" in command_str: 
                con.print_warning(f"Warning for '{item_name}': Command uses 'ZSH_CUSTOM:~'. Standard is 'ZSH_CUSTOM:-'. Ensure your command structure is correct for variable expansion in the user's shell.")
            if item_name == "zsh-eza" and "plugins/you-should-use" in command_str: 
                 con.print_warning(f"Warning for 'zsh-eza': Command might have an incorrect target directory '.../plugins/you-should-use'. Expected '.../plugins/zsh-eza'. Please verify config.")

            is_git_clone_cmd = "git clone" in command_str.lower()
            should_skip_due_to_existence = False
            if is_git_clone_cmd:
                cmd_parts = shlex.split(command_str) 
                target_dir_in_cmd = ""
                if len(cmd_parts) > 0:
                    try:
                        git_idx = cmd_parts.index("git")
                        clone_idx = cmd_parts.index("clone", git_idx)
                        if len(cmd_parts) > clone_idx + 2:
                             potential_path = cmd_parts[clone_idx + 2]
                             if not potential_path.startswith("-"): 
                                target_dir_in_cmd = potential_path
                    except ValueError: pass 

                if target_dir_in_cmd:
                    check_dir_exists_cmd = f"test -d {shlex.quote(target_dir_in_cmd)}"
                    try:
                        proc = system_utils.run_command(
                            check_dir_exists_cmd, run_as_user=target_user, shell=True, 
                            capture_output=True, check=False, print_fn_info=None, logger=app_logger
                        )
                        if proc.returncode == 0:
                            con.print_info(f"Destination for '{item_name}' ('{target_dir_in_cmd}') seems to exist. Skipping.")
                            should_skip_due_to_existence = True
                        elif proc.returncode != 1: 
                            con.print_warning(f"Could not check existence for '{item_name}' due to test command error (code {proc.returncode}). Will attempt command.")
                            app_logger.warning(f"test -d for '{item_name}' errored: {proc.stderr if proc.stderr else 'N/A'}")
                    except Exception as e_check_exist:
                        con.print_warning(f"Could not check existence for '{item_name}': {e_check_exist}. Will attempt command.")
                        app_logger.warning(f"Exception checking plugin existence for '{item_name}': {e_check_exist}", exc_info=True)
            
            if should_skip_due_to_existence:
                continue

            try:
                system_utils.run_command(
                    command_str, run_as_user=target_user, shell=True,
                    capture_output=True, check=True,
                    print_fn_info=con.print_info, print_fn_error=con.print_error,
                    print_fn_sub_step=con.print_sub_step, logger=app_logger
                )
                con.print_success(f"Applied: {item_name}")
                app_logger.info(f"Applied enhancement: {item_name}")
            except subprocess.CalledProcessError as e:
                if is_git_clone_cmd and e.returncode == 128 and e.stderr and "already exists" in e.stderr.lower():
                     con.print_info(f"Git clone for '{item_name}' reported destination exists. Skipped.")
                     app_logger.info(f"Git clone for '{item_name}' skipped, dir likely exists.")
                else:
                    con.print_error(f"Failed to apply: {item_name}. Check logs.")
                    app_logger.error(f"Failed applying enhancement '{item_name}'.", exc_info=False)
                    overall_success = False
            except Exception as e_cmd:
                con.print_error(f"Unexpected error applying '{item_name}': {e_cmd}")
                app_logger.error(f"Unexpected error for '{item_name}': {e_cmd}", exc_info=True)
                overall_success = False

    # Copy Dotfiles
    if target_user_home: 
        project_root = Path(__file__).resolve().parent.parent
        if user_wants_to_proceed_with_enhancements: 
            if not _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root):
                con.print_warning("Failed to copy .zshrc.")
                if omz_install_command or (omz_exists_proc and omz_exists_proc.returncode == 0): 
                    overall_success = False 
        
        if not _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root):
            con.print_warning("Failed to copy .nanorc.")
    else:
        app_logger.warning("Skipping dotfile copy: target_user_home not determined.")
                
    if overall_success:
        con.print_success("Phase 3: Terminal Enhancement completed.")
        app_logger.info("Phase 3 completed successfully.")
    else:
        con.print_error("Phase 3: Terminal Enhancement completed with errors. Please review the output.")
        app_logger.error("Phase 3 completed with errors.")
    
    return overall_success