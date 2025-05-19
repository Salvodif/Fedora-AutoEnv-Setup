# Fedora-AutoEnv-Setup/scripts/phase3_terminal_enhancement.py

import subprocess 
import sys
import os
import shutil
import shlex 
from pathlib import Path
from typing import Optional, Dict 
import time # For time.sleep and unique backup naming
import logging # Added for Optional[logging.Logger] type hint

# Adjust import path to reach parent directory for shared modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils 
from scripts.logger_utils import app_logger 

# --- Helper Functions ---

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
        app_logger.info(f"Zsh found via 'which' at {zsh_path_which}, preferring this.") 
        return zsh_path_which
        
    app_logger.info("Zsh not found by _check_zsh_installed.")
    return None


def _ensure_shell_in_etc_shells(shell_path: str, logger: Optional[logging.Logger] = None) -> bool:
    _log = logger or app_logger
    if not shell_path: 
        con.print_error("Cannot ensure empty shell path in /etc/shells.")
        _log.error("Empty shell_path passed to _ensure_shell_in_etc_shells.")
        return False
    
    _log.info(f"Ensuring '{shell_path}' is in /etc/shells.")
    etc_shells_path = Path("/etc/shells")
    try:
        if not etc_shells_path.is_file():
            con.print_warning(f"File {etc_shells_path} not found. Cannot verify or add shell path.")
            _log.warning(f"{etc_shells_path} not found.")
            if os.geteuid() == 0:
                try:
                    con.print_info(f"Attempting to create {etc_shells_path} as root.")
                    # Create empty file with sudo
                    system_utils.run_command(f"sudo touch {shlex.quote(str(etc_shells_path))}", shell=True, logger=_log, print_fn_info=con.print_info)
                    system_utils.run_command(["sudo", "chown", "root:root", str(etc_shells_path)], logger=_log, print_fn_info=con.print_info)
                    system_utils.run_command(["sudo", "chmod", "644", str(etc_shells_path)], logger=_log, print_fn_info=con.print_info)
                    _log.info(f"Created {etc_shells_path}.")
                except Exception as e_create:
                    con.print_error(f"Failed to create {etc_shells_path}: {e_create}")
                    _log.error(f"Failed to create {etc_shells_path}: {e_create}")
                    return False
            else:
                return False

        current_shells_content = ""
        # Always try to read with sudo if script is root, as permissions might be strict
        if os.geteuid() == 0:
            try:
                 cat_proc = system_utils.run_command(
                    ["sudo", "cat", str(etc_shells_path)],
                    capture_output=True, check=True, logger=_log, print_fn_info=None
                 )
                 current_shells_content = cat_proc.stdout
            except Exception as e_cat: # Fallback to direct read if sudo cat fails (e.g. sudo not configured for cat)
                _log.warning(f"sudo cat {etc_shells_path} failed ({e_cat}), trying direct read (might fail due to perms).")
                if etc_shells_path.exists(): # Check again before direct read
                    current_shells_content = etc_shells_path.read_text(encoding='utf-8')
                else: # If it didn't exist and create failed, this will be an issue
                    _log.error(f"{etc_shells_path} still not found after creation attempt.")
                    return False

        else: # Not root, try direct read
            current_shells_content = etc_shells_path.read_text(encoding='utf-8')

        current_shells = [line.strip() for line in current_shells_content.splitlines() if line.strip() and not line.startswith('#')]

        if shell_path in current_shells:
            _log.info(f"'{shell_path}' already in {etc_shells_path}.")
            return True
        
        con.print_info(f"Shell '{shell_path}' not found in {etc_shells_path}. Attempting to add it (requires sudo)...")
        
        quoted_shell_path = shlex.quote(shell_path)
        append_cmd_str = f"echo {quoted_shell_path} | sudo tee -a {shlex.quote(str(etc_shells_path))} > /dev/null"

        system_utils.run_command(
            append_cmd_str,
            shell=True, check=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error,
            logger=_log
        )

        con.print_success(f"Successfully added '{shell_path}' to {etc_shells_path}.")
        _log.info(f"Added '{shell_path}' to {etc_shells_path}.")
        return True
    except Exception as e:
        con.print_error(f"Failed to process /etc/shells for '{shell_path}': {e}")
        _log.error(f"Error processing /etc/shells for '{shell_path}': {e}", exc_info=True)
        return False


def _set_default_shell(username: str, shell_path: str, logger: Optional[logging.Logger] = None) -> bool:
    _log = logger or app_logger
    current_shell = _get_user_shell(username)
    if current_shell == shell_path:
        con.print_info(f"Shell '{shell_path}' is already the default shell for user '{username}'.")
        _log.info(f"'{shell_path}' is already default for '{username}'.")
        return True

    con.print_sub_step(f"Setting Zsh ('{shell_path}') as default shell for user '{username}'...")
    _log.info(f"Setting '{shell_path}' as default for '{username}'.")
    
    if os.geteuid() != 0:
        con.print_error(f"Cannot change shell for user '{username}' without root privileges for `chsh` command itself.")
        _log.error(f"Cannot change shell for '{username}' using `chsh` without overall root privileges for the script.")
        return False

    if not _ensure_shell_in_etc_shells(shell_path, logger=_log):
        con.print_warning(f"Could not ensure '{shell_path}' is in /etc/shells. `chsh` might warn or fail.")
    try:
        system_utils.run_command(
            ["sudo", "chsh", "-s", shell_path, username],
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error,
            logger=_log
        )
        
        time.sleep(0.5) 
        new_shell_check = _get_user_shell(username)
        
        if new_shell_check == shell_path:
            con.print_success(f"Successfully set Zsh as the default shell for '{username}'.")
            _log.info(f"Successfully set Zsh for '{username}'.")
            con.print_info("Note: The shell change will take effect upon the user's next login.")
        else:
            con.print_warning(f"chsh command executed to set shell to '{shell_path}' for '{username}'.")
            con.print_warning(f"Verification via getent currently shows shell as: '{new_shell_check or 'unknown'}'. This is sometimes delayed.")
            _log.warning(f"chsh for '{username}' to '{shell_path}' ran, but getent shows '{new_shell_check}'. May take effect on next login.")
            con.print_info("Please verify the shell after the user's next login.")
        
        return True
    except subprocess.CalledProcessError as e:
        con.print_error(f"The 'chsh' command failed to set shell for '{username}'. Exit code: {e.returncode}")
        if e.stderr: con.print_error(f"chsh STDERR: {e.stderr}")
        _log.error(f"chsh command failed for '{username}' (CalledProcessError): {e}", exc_info=False)
        return False
    except Exception as e: 
        con.print_error(f"An unexpected error occurred while trying to set default shell for '{username}': {e}")
        _log.error(f"Unexpected error setting default shell for '{username}': {e}", exc_info=True)
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
        test_exists_proc = system_utils.run_command(
            f"test -f {shlex.quote(str(target_file_path))}",
            run_as_user=target_user, shell=True, check=False, capture_output=True,
            print_fn_info=None, 
            logger=app_logger
        )
        if test_exists_proc.returncode == 0:
            target_exists_as_user = True
        
        if target_exists_as_user:
            timestamp_str = f"backup_{int(time.time())}_{Path.cwd().name.replace(' ','_')}"
            backup_target_path = target_user_home / f"{source_filename}.{timestamp_str}"
            
            backup_command_str = f"cp -pf {shlex.quote(str(target_file_path))} {shlex.quote(str(backup_target_path))}"
            con.print_info(f"Existing '{target_file_path.name}' found. Will attempt to back it up to '{backup_target_path.name}'.")
            app_logger.info(f"Target file '{target_file_path}' exists. Backup command (as user): {backup_command_str}")
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
    if not target_user_home: 
        con.print_error(f"Cannot determine home directory for '{target_user}'. Aborting user-specific Phase 3 steps.")
        app_logger.error(f"Target user home for '{target_user}' not found. Aborting user-specific part of Phase 3.")
        return False 

    con.print_info(f"Running terminal enhancements for user: [bold cyan]{target_user}[/bold cyan]")
    app_logger.info(f"Running Phase 3 for user: {target_user}")

    zsh_path = _check_zsh_installed()
    current_shell = _get_user_shell(target_user)
    is_zsh_default = current_shell and "zsh" in Path(current_shell).name.lower()
    
    phase2_config = config_loader.get_phase_data(app_config, "phase2_basic_configuration")
    zsh_should_be_dnf_installed = "zsh" in [pkg.lower() for pkg in phase2_config.get("dnf_packages", [])]

    user_wants_to_proceed_with_enhancements = True 

    if not zsh_path:
        if zsh_should_be_dnf_installed:
            con.print_warning("Zsh was expected from Phase 2 DNF packages but is not currently found.")
            con.print_info("This might mean Phase 2 failed, Zsh isn't in PATH for this script, or it wasn't installed correctly.")
            if not con.confirm_action("Proceed with Zsh-specific terminal enhancements (Oh My Zsh, etc.)? (These may fail if Zsh is truly unavailable).", default=False):
                user_wants_to_proceed_with_enhancements = False
        else: 
            con.print_warning("Zsh is not installed. It's highly recommended to add 'zsh' to Phase 2 DNF packages.")
            con.print_info("The Oh My Zsh installer (if configured) might attempt to install Zsh or prompt you.")
            if not con.confirm_action("Zsh is not found. Do you want to attempt terminal enhancements now? (Oh My Zsh might try to install Zsh or fail).", default=False):
                user_wants_to_proceed_with_enhancements = False
    elif not is_zsh_default:
        con.print_info(f"Zsh is installed ('{zsh_path}') but is not the default shell for '{target_user}'. Current: '{current_shell}'")
        if con.confirm_action(f"Set Zsh as default shell for '{target_user}' and proceed with enhancements?", default=True):
            if not _set_default_shell(target_user, zsh_path, logger=app_logger):
                overall_success = False # Mark as partial failure
                con.print_error("Failed to set Zsh as default. Oh My Zsh might not function as expected.")
                app_logger.error(f"Failed to set Zsh as default for {target_user}.")
                if not con.confirm_action("Zsh could not be set as default. Continue with other terminal enhancements (plugins, .zshrc copy)?", default=False):
                    user_wants_to_proceed_with_enhancements = False
            else:
                is_zsh_default = True 
        else: 
            user_wants_to_proceed_with_enhancements = False
            con.print_info("Zsh will not be set as default. Some enhancements might not apply as expected.")
            app_logger.info(f"User declined setting Zsh as default for '{target_user}'.")


    if not user_wants_to_proceed_with_enhancements:
        con.print_info("Skipping Zsh-specific terminal enhancements based on user choice or Zsh setup issues.")
        app_logger.info("User opted out of Zsh-specific terminal enhancements or Zsh setup failed/declined.")
        project_root_nano = Path(__file__).resolve().parent.parent
        _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root_nano)
        return overall_success 

    app_logger.info("Proceeding with Zsh terminal enhancements.")
    
    phase3_config_data = config_loader.get_phase_data(app_config, "phase3_terminal_enhancement")
    if not phase3_config_data:
        con.print_warning("No configuration found for Phase 3 in config files. Skipping specific enhancements.")
        app_logger.warning("No Phase 3 configuration data found in config. Skipping specific enhancements.")
        if zsh_path and is_zsh_default:
            project_root = Path(__file__).resolve().parent.parent
            _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root)
        project_root_nano = Path(__file__).resolve().parent.parent
        _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root_nano)
        return overall_success

    phase3_config_commands = phase3_config_data.copy()
    
    omz_install_key = "omz" 
    omz_install_command_template = phase3_config_commands.pop(omz_install_key, None)
    omz_installed_or_existed_successfully = False # Flag to track OMZ status

    if omz_install_command_template:
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
                omz_installed_or_existed_successfully = True # It exists, so proceed as if successful
            else:
                con.print_info("Oh My Zsh directory not found. Running Oh My Zsh installation script...")
                con.print_panel(
                    "The Oh My Zsh installer is an [bold]interactive script[/].\n"
                    "Its output will be displayed directly below.\n"
                    "Please follow any prompts from the OMZ installer itself.\n"
                    "[yellow]IMPORTANT:[/] This script will attempt to run it non-interactively regarding shell change by setting `RUNZSH=no` and `CHSH=no`.",
                    title="Oh My Zsh Installation", style="yellow"
                )
                
                omz_env_vars = {"RUNZSH": "no", "CHSH": "no"}
                final_omz_command = omz_install_command_template # Assuming it's a string
                                
                system_utils.run_command(
                    final_omz_command,
                    run_as_user=target_user,
                    shell=True, 
                    capture_output=False, 
                    check=True, 
                    env_vars=omz_env_vars, 
                    print_fn_info=None, 
                    print_fn_error=con.print_error, 
                    logger=app_logger
                )
                con.print_success("Oh My Zsh installation script finished.")
                app_logger.info("OMZ installation script finished.")
                omz_installed_or_existed_successfully = True
                con.print_warning("A new Zsh shell session (new terminal or re-login) is required for all OMZ changes to take full effect.")
        except subprocess.CalledProcessError as e_omz_script:
            con.print_error(f"Oh My Zsh installation script failed with exit code {e_omz_script.returncode}.")
            if e_omz_script.stdout: con.print_info(f"OMZ STDOUT:\n{e_omz_script.stdout}")
            if e_omz_script.stderr: con.print_error(f"OMZ STDERR:\n{e_omz_script.stderr}")
            app_logger.error(f"OMZ installation script failed: {e_omz_script}", exc_info=False)
            overall_success = False # OMZ install is fairly critical for subsequent steps
            omz_installed_or_existed_successfully = False
        except Exception as e:
            con.print_error(f"Oh My Zsh installation process encountered an unexpected error: {e}")
            app_logger.error(f"OMZ installation process failed: {e}", exc_info=True)
            overall_success = False
            omz_installed_or_existed_successfully = False
    else: # No OMZ install command in config, check if it exists anyway
        omz_dir_check_cmd = "test -d $HOME/.oh-my-zsh"
        omz_exists_proc = system_utils.run_command(
            omz_dir_check_cmd, run_as_user=target_user, shell=True,
            check=False, capture_output=True, logger=app_logger, print_fn_info=None
        )
        if omz_exists_proc.returncode == 0:
            omz_installed_or_existed_successfully = True
            app_logger.info("OMZ install command not in config, but $HOME/.oh-my-zsh exists.")
        else:
            app_logger.info("OMZ install command not in config and $HOME/.oh-my-zsh does not exist.")
            # If no OMZ, plugins might not make sense, but user might have custom setup.
            # Let's proceed with caution for other commands.


    # Only create custom plugin dir and install plugins IF OMZ installed/existed successfully
    if omz_installed_or_existed_successfully:
        omz_custom_plugins_dir_cmd = "mkdir -p ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
        try:
            system_utils.run_command(
                omz_custom_plugins_dir_cmd, run_as_user=target_user, shell=True,
                logger=app_logger, print_fn_info=con.print_info, print_fn_error=con.print_error
            )
            app_logger.info(f"Ensured OMZ custom plugins directory exists: {omz_custom_plugins_dir_cmd}")
        except Exception:
            con.print_warning("Could not ensure Oh My Zsh custom plugins directory exists after OMZ setup. Plugin installations might fail.")
            app_logger.warning("Failed to create OMZ custom plugins directory after OMZ setup.", exc_info=True)
            overall_success = False # This is important for plugins if OMZ was intended

        # Proceed with other commands (plugins, etc.) only if OMZ setup was okay and custom dir creation attempt was made
        if overall_success: # Check overall_success which might have been affected by custom dir creation
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
                    try:
                        cmd_parts = shlex.split(command_str)
                        target_dir_in_cmd_unexpanded = ""
                        if len(cmd_parts) > 0:
                            clone_idx = -1
                            try:
                                clone_idx = cmd_parts.index("clone")
                            except ValueError: pass

                            if clone_idx != -1 and len(cmd_parts) > clone_idx + 2:
                                potential_path_unexpanded = cmd_parts[clone_idx + 2]
                                if not potential_path_unexpanded.startswith("-"):
                                    target_dir_in_cmd_unexpanded = potential_path_unexpanded
                        
                        if target_dir_in_cmd_unexpanded:
                            expanded_target_dir_cmd = f"echo {target_dir_in_cmd_unexpanded}"
                            path_expansion_proc = system_utils.run_command(
                                expanded_target_dir_cmd, run_as_user=target_user, shell=True,
                                capture_output=True, check=True, print_fn_info=None, logger=app_logger
                            )
                            expanded_target_dir_str = path_expansion_proc.stdout.strip()

                            if expanded_target_dir_str:
                                check_dir_exists_cmd = f"test -d {shlex.quote(expanded_target_dir_str)}"
                                app_logger.debug(f"Checking existence with command: {check_dir_exists_cmd}")
                                proc = system_utils.run_command(
                                    check_dir_exists_cmd, run_as_user=target_user, shell=True, 
                                    capture_output=True, check=False, print_fn_info=None, logger=app_logger
                                )
                                if proc.returncode == 0:
                                    con.print_info(f"Destination for '{item_name}' ('{expanded_target_dir_str}') seems to exist. Skipping git clone.")
                                    app_logger.info(f"Git clone for '{item_name}' skipped, dir '{expanded_target_dir_str}' likely exists.")
                                    should_skip_due_to_existence = True
                                elif proc.returncode != 1:
                                    con.print_warning(f"Could not reliably check existence for '{item_name}' due to test command error (code {proc.returncode}). Will attempt command.")
                                    app_logger.warning(f"test -d for '{item_name}' errored: {proc.stderr if proc.stderr else 'N/A'}")
                            else:
                                app_logger.warning(f"Could not expand target directory '{target_dir_in_cmd_unexpanded}' for '{item_name}'. Will attempt command.")
                    except Exception as e_parse_clone:
                        con.print_warning(f"Could not parse/check git clone target for '{item_name}': {e_parse_clone}. Will attempt command.")
                        app_logger.warning(f"Exception parsing/checking git clone for '{item_name}': {e_parse_clone}", exc_info=True)
                
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
                except subprocess.CalledProcessError as e_cmd:
                    if is_git_clone_cmd and e_cmd.returncode == 128 and e_cmd.stderr and \
                    ("already exists and is not an empty directory" in e_cmd.stderr.lower() or \
                        "destination path" in e_cmd.stderr.lower() and "already exists" in e_cmd.stderr.lower()):
                        con.print_info(f"Git clone for '{item_name}' reported destination exists. Considered skipped.")
                        app_logger.info(f"Git clone for '{item_name}' skipped (error 128, dir exists).")
                    else:
                        con.print_error(f"Failed to apply: {item_name}. Check logs.")
                        app_logger.error(f"Failed applying enhancement '{item_name}'. Exit: {e_cmd.returncode}", exc_info=False)
                        overall_success = False
                except Exception as e_cmd_unexpected:
                    con.print_error(f"Unexpected error applying '{item_name}': {e_cmd_unexpected}")
                    app_logger.error(f"Unexpected error for '{item_name}': {e_cmd_unexpected}", exc_info=True)
                    overall_success = False
    elif not omz_install_command_template: # No OMZ in config and it didn't exist
        con.print_info("Oh My Zsh is not configured for installation and was not found. Skipping plugin installations.")
        app_logger.info("OMZ not configured and not found. Skipping plugins.")
    else: # OMZ was in config but failed to install
        con.print_warning("Oh My Zsh installation failed or was problematic. Skipping related plugin installations.")
        app_logger.warning("OMZ installation failed. Skipping plugins.")


    project_root = Path(__file__).resolve().parent.parent
    if user_wants_to_proceed_with_enhancements:
        if zsh_path and is_zsh_default:
            if not _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root):
                con.print_warning("Failed to copy .zshrc. Your Zsh terminal might not use the custom configuration.")
                app_logger.warning("Failed to copy .zshrc")
        elif zsh_path: 
            con.print_info("Zsh is installed but might not be default. .zshrc will be copied as enhancements were requested.")
            _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root)

    if not _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root):
        con.print_warning("Failed to copy .nanorc.")
        app_logger.warning("Failed to copy .nanorc")
                
    if overall_success:
        con.print_success("Phase 3: Terminal Enhancement completed.")
        app_logger.info("Phase 3 completed successfully.")
    else:
        con.print_error("Phase 3: Terminal Enhancement completed with errors. Please review the output and logs.")
        app_logger.error("Phase 3 completed with errors.")
    
    return overall_success