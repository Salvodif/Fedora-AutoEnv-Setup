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


def _handle_zsh_default_shell_setup(
    target_user: str, 
    zsh_path: str, 
    current_shell: Optional[str]
) -> bool:
    """
    Handles setting Zsh as the default shell for the target user.
    Returns True if Zsh is successfully set as default OR if the user declines 
    but Zsh is present (no failure), False if set_default_shell fails critically.
    """
    app_logger.debug(f"Entering _handle_zsh_default_shell_setup for user '{target_user}'. Zsh path: '{zsh_path}', Current shell: '{current_shell}'")
    is_zsh_default = current_shell is not None and "zsh" in Path(current_shell).name.lower()

    if is_zsh_default:
        app_logger.info(f"Zsh ('{current_shell}') is already the default shell for '{target_user}'. No action needed in _handle_zsh_default_shell_setup.")
        return True # Already default, so successful state for this function's purpose

    # Zsh is installed but not default
    con.print_info(f"Zsh is installed ('{zsh_path}') but is not the default shell for '{target_user}'. Current shell: '{current_shell or 'Not set/Unknown'}'.")
    if con.confirm_action(f"Set Zsh as default shell for '{target_user}' and proceed with Zsh enhancements?", default=True):
        if not system_utils.set_default_shell(
            target_user, 
            zsh_path, 
            logger=app_logger, 
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step,
            print_fn_warning=con.print_warning,
            print_fn_success=con.print_success
        ): 
            con.print_error("CRITICAL: Failed to set Zsh as default in _handle_zsh_default_shell_setup. This affects Oh My Zsh functionality.")
            app_logger.error(f"CRITICAL: _handle_zsh_default_shell_setup failed to set Zsh as default for {target_user}.")
            return False # Critical failure
        else:
            app_logger.info(f"Zsh successfully set as default for {target_user} by _handle_zsh_default_shell_setup (pending next login for full effect).")
            # is_zsh_default will be updated in the caller (run_phase3) if needed
            return True # Successfully set
    else: # User chose not to set Zsh as default
        con.print_info("Zsh will not be set as default by user choice in _handle_zsh_default_shell_setup.")
        app_logger.info(f"User declined setting Zsh as default for '{target_user}' in _handle_zsh_default_shell_setup.")
        return True # User declined, not a failure of the function itself. Caller decides if this is a blocking event.

def _check_zsh_installed() -> Optional[str]:
    """
    Checks if Zsh is installed and returns its path. 
    Prefers common paths like /usr/bin/zsh or /bin/zsh, then `which`.
    """
    app_logger.debug("Checking if Zsh is installed.")
    common_paths_to_check = ["/usr/bin/zsh", "/bin/zsh"] 
    for zsh_path_str in common_paths_to_check:
        zsh_path_obj = Path(zsh_path_str)
        if zsh_path_obj.is_file() and os.access(zsh_path_obj, os.X_OK):
            app_logger.info(f"Zsh found at pre-defined common path: {zsh_path_str}.")
            return zsh_path_str
            
    # Fallback to shutil.which if not found in common paths
    zsh_path_which = shutil.which("zsh")
    if zsh_path_which:
        app_logger.info(f"Zsh found via 'which' at {zsh_path_which}.") 
        return zsh_path_which
        
    app_logger.info("Zsh not found by _check_zsh_installed (common paths or 'which' failed).")
    return None

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

# --- Helper Function for Oh My Zsh Installation ---
def _handle_oh_my_zsh_installation(
    target_user: str, 
    target_user_home: Path, 
    omz_install_command_template: Optional[str]
) -> bool:
    """
    Manages Oh My Zsh installation.
    Returns True if OMZ is successfully installed/already existed and custom dir verified, False otherwise.
    """
    app_logger.debug(f"Entering _handle_oh_my_zsh_installation for user '{target_user}'.")
    omz_base_dir_path = target_user_home / ".oh-my-zsh"
    omz_custom_dir_path = omz_base_dir_path / "custom"

    # Check if OMZ base directory exists
    omz_base_path_check_cmd = f"test -d {shlex.quote(str(omz_base_dir_path))}"
    try:
        omz_exists_proc = system_utils.run_command(
            omz_base_path_check_cmd, run_as_user=target_user, shell=True,
            check=False, capture_output=True, logger=app_logger, print_fn_info=None
        )
        omz_base_dir_exists = (omz_exists_proc.returncode == 0)
    except Exception as e_check_omz_base:
        con.print_warning(f"Error checking for OMZ base directory '{omz_base_dir_path}': {e_check_omz_base}. Assuming not present.")
        app_logger.warning(f"Error checking OMZ base dir for '{target_user}': {e_check_omz_base}", exc_info=True)
        omz_base_dir_exists = False
        
    omz_installed_successfully_this_run = False

    if omz_base_dir_exists:
        con.print_info(f"Oh My Zsh directory ('{omz_base_dir_path}') already exists. Skipping OMZ installation script.")
        app_logger.info(f"OMZ directory '{omz_base_dir_path}' exists, skipping installer.")
    elif omz_install_command_template:
        con.print_info(f"Oh My Zsh directory ('{omz_base_dir_path}') not found. Running Oh My Zsh installation script...")
        con.print_panel(
            "The Oh My Zsh installer may be [bold]interactive[/].\n"
            "Its output will be displayed directly below.\n"
            "Please follow any prompts from the OMZ installer itself.\n"
            "[yellow]IMPORTANT:[/] This script attempts to run OMZ non-interactively regarding shell changes "
            "by setting `RUNZSH=no` and `CHSH=no` environment variables for the installer.",
            title="Oh My Zsh Installation", style="yellow"
        )
        
        omz_env_vars_for_installer = {"RUNZSH": "no", "CHSH": "no"}
        
        curl_check_cmd = "command -v curl"
        curl_check_proc = system_utils.run_command(
            curl_check_cmd, run_as_user=target_user, shell=True, check=False, 
            capture_output=True, logger=app_logger, print_fn_info=None
        )
        if curl_check_proc.returncode != 0:
            con.print_error("`curl` command not found in user's environment. Cannot download Oh My Zsh installer.")
            app_logger.error(f"`curl` not found for Oh My Zsh installation (user: {target_user}). Add `curl` to DNF packages.")
            return False

        try:
            system_utils.run_command(
                str(omz_install_command_template), run_as_user=target_user, shell=True,
                capture_output=False, check=True, env_vars=omz_env_vars_for_installer,
                print_fn_info=None, print_fn_error=con.print_error, logger=app_logger
            )
            con.print_success("Oh My Zsh installation script finished successfully.")
            app_logger.info(f"OMZ installation script finished successfully for '{target_user}'.")
            omz_installed_successfully_this_run = True
            omz_base_dir_exists = True # Installer should have created it
            con.print_warning("A new Zsh shell session (new terminal or re-login) is required for all OMZ changes to take full effect.")
        except subprocess.CalledProcessError as e_omz_script:
            app_logger.error(f"OMZ installation script execution failed for user '{target_user}'. Command: {e_omz_script.cmd}, Exit: {e_omz_script.returncode}", exc_info=False)
            con.print_error("Oh My Zsh installation is CRITICAL for subsequent terminal enhancements. Installation failed.")
            return False
        except Exception as e_unexpected_omz:
            con.print_error(f"Oh My Zsh installation process encountered an unexpected error: {e_unexpected_omz}")
            app_logger.error(f"OMZ installation - unexpected error for user '{target_user}': {e_unexpected_omz}", exc_info=True)
            return False
    else: # No OMZ install command and OMZ not found
        app_logger.info("OMZ install command not in config and $HOME/.oh-my-zsh does not exist. Cannot install OMZ.")
        # Not necessarily an error for this function if OMZ was optional. Caller (run_phase3) decides.
        # But if OMZ is expected, this function returning False signals it's not available.
        return False # Cannot proceed if OMZ isn't there and no way to install it.

    # Verify OMZ custom directory if OMZ base exists (either pre-existing or just installed)
    if omz_base_dir_exists:
        zsh_custom_check_cmd = f"test -d {shlex.quote(str(omz_custom_dir_path))}"
        try:
            custom_exists_proc = system_utils.run_command(
                zsh_custom_check_cmd, run_as_user=target_user, shell=True,
                check=False, capture_output=True, logger=app_logger, print_fn_info=None
            )
            if custom_exists_proc.returncode == 0:
                app_logger.info(f"OMZ custom directory ('{omz_custom_dir_path}') found for user '{target_user}'.")
                return True # OMZ exists and custom dir is verified
            else:
                app_logger.error(f"OMZ custom directory ('{omz_custom_dir_path}') NOT found for user '{target_user}'.")
                if omz_installed_successfully_this_run:
                    con.print_error(f"CRITICAL: Oh My Zsh installer seemed to finish, but its 'custom' directory ('{omz_custom_dir_path}') is missing. This indicates a problem with OMZ setup.")
                else: # OMZ pre-existed but custom dir is missing
                    con.print_warning(f"Warning: Oh My Zsh seems to be installed, but its 'custom' directory ('{omz_custom_dir_path}') is missing. Some plugins might fail.")
                return False # Custom dir missing is a failure for OMZ setup integrity
        except Exception as e_check_custom:
            con.print_warning(f"Error checking for OMZ custom directory '{omz_custom_dir_path}': {e_check_custom}. Assuming not present or inaccessible.")
            app_logger.warning(f"Error checking OMZ custom dir for '{target_user}': {e_check_custom}", exc_info=True)
            return False
            
    return False # Should not be reached if logic is correct, but default to false if omz_base_dir_exists was false initially.


# --- Helper Function for OMZ Plugins and Themes ---
def _install_omz_plugins_and_themes(
    target_user: str, 
    target_user_home: Path, 
    enhancement_commands: Dict[str, str]
) -> bool:
    """
    Installs Oh My Zsh plugins and themes.
    Returns True if all enhancements applied/skipped successfully, False if any command fails.
    """
    app_logger.debug(f"Entering _install_omz_plugins_and_themes for user '{target_user}'.")
    overall_success = True
    
    # $ZSH_CUSTOM is typically $HOME/.oh-my-zsh/custom
    # This path should exist if _handle_oh_my_zsh_installation returned True.
    zsh_custom_dir_abs = target_user_home / ".oh-my-zsh" / "custom"
    
    # Verify ZSH_CUSTOM path again, just in case (though _handle_oh_my_zsh_installation should ensure it)
    zsh_custom_check_cmd = f"test -d {shlex.quote(str(zsh_custom_dir_abs))}"
    try:
        custom_exists_proc = system_utils.run_command(
            zsh_custom_check_cmd, run_as_user=target_user, shell=True,
            check=False, capture_output=True, logger=app_logger, print_fn_info=None
        )
        if custom_exists_proc.returncode != 0:
            con.print_error(f"OMZ custom directory '{zsh_custom_dir_abs}' not found before plugin installation. Cannot proceed with plugins.")
            app_logger.error(f"OMZ custom directory '{zsh_custom_dir_abs}' missing for user '{target_user}' before plugin install.")
            return False
    except Exception as e_pre_check_custom:
        con.print_warning(f"Error pre-checking OMZ custom directory '{zsh_custom_dir_abs}' before plugin install: {e_pre_check_custom}. Plugins may fail.")
        app_logger.warning(f"Error pre-checking OMZ custom dir for '{target_user}' before plugins: {e_pre_check_custom}", exc_info=True)
        return False


    for item_name, command_str_template in enhancement_commands.items():
        app_logger.debug(f"Processing OMZ enhancement item: {item_name}, command template: {command_str_template}")
        if not isinstance(command_str_template, str) or not command_str_template.strip():
            con.print_warning(f"Skipping invalid command for OMZ item '{item_name}' (not a string or empty).")
            app_logger.warning(f"Invalid command template for OMZ item '{item_name}'.")
            continue
        
        con.print_sub_step(f"Processing OMZ enhancement: {item_name}")
        
        home_dir_str_for_sub = str(target_user_home)
        zsh_custom_dir_str_for_sub = str(zsh_custom_dir_abs)

        command_str_processed = command_str_template.replace("$HOME", home_dir_str_for_sub)
        command_str_processed = command_str_processed.replace("${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}", zsh_custom_dir_str_for_sub)
        command_str_processed = command_str_processed.replace("$ZSH_CUSTOM", zsh_custom_dir_str_for_sub)

        if "ZSH_CUSTOM:~" in command_str_template:
            con.print_warning(f"Warning for '{item_name}': Original command template uses 'ZSH_CUSTOM:~'. This script substitutes with absolute custom path. Ensure command logic is compatible.")

        is_git_clone_cmd = "git clone" in command_str_processed.lower()
        should_skip_due_to_existence = False
        if is_git_clone_cmd:
            try:
                cmd_parts = shlex.split(command_str_processed)
                clone_idx = -1
                try: clone_idx = cmd_parts.index("clone") 
                except ValueError: pass

                if clone_idx != -1 and len(cmd_parts) > clone_idx + 2:
                    potential_target_path_str = cmd_parts[clone_idx + 2]
                    if not potential_target_path_str.startswith("-"):
                        expanded_target_dir_str = potential_target_path_str # Already expanded

                        check_dir_exists_cmd = f"test -d {shlex.quote(expanded_target_dir_str)}"
                        app_logger.debug(f"Checking plugin existence for '{item_name}' with command (as {target_user}): {check_dir_exists_cmd}")
                        proc = system_utils.run_command(
                            check_dir_exists_cmd, run_as_user=target_user, shell=True,
                            capture_output=True, check=False, print_fn_info=None, logger=app_logger
                        )
                        if proc.returncode == 0:
                            con.print_info(f"Destination for '{item_name}' ('{expanded_target_dir_str}') seems to exist. Skipping git clone.")
                            app_logger.info(f"Git clone for '{item_name}' skipped, dir '{expanded_target_dir_str}' likely exists for user '{target_user}'.")
                            should_skip_due_to_existence = True
                        elif proc.returncode != 1:
                            con.print_warning(f"Could not reliably check existence for '{item_name}' (target: '{expanded_target_dir_str}', test cmd error {proc.returncode}). Will attempt command.")
                            app_logger.warning(f"test -d for '{item_name}' (target: {expanded_target_dir_str}) errored as user '{target_user}': {proc.stderr.strip() if proc.stderr else 'N/A'}")
                else:
                    app_logger.warning(f"Could not determine target directory for git clone of '{item_name}' from command '{command_str_processed}'. Will attempt command.")
            except Exception as e_parse_clone:
                con.print_warning(f"Could not parse/check git clone target for '{item_name}': {e_parse_clone}. Will attempt command.")
                app_logger.warning(f"Exception parsing/checking git clone for '{item_name}': {e_parse_clone}", exc_info=True)
        
        if should_skip_due_to_existence:
            continue

        try:
            system_utils.run_command(
                command_str_processed, run_as_user=target_user, shell=True,
                capture_output=True, check=True, print_fn_info=con.print_info,
                print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step,
                logger=app_logger
            )
            con.print_success(f"Applied OMZ enhancement: {item_name}")
            app_logger.info(f"Applied OMZ enhancement '{item_name}' for user '{target_user}'.")
        except subprocess.CalledProcessError as e_cmd:
            if is_git_clone_cmd and e_cmd.returncode == 128 and e_cmd.stderr and \
               ("already exists and is not an empty directory" in e_cmd.stderr.lower() or \
                ("destination path" in e_cmd.stderr.lower() and "already exists" in e_cmd.stderr.lower())):
                con.print_info(f"Git clone for '{item_name}' reported destination exists (via stderr after attempt). Considered skipped.")
                app_logger.info(f"Git clone for '{item_name}' skipped (error 128, dir exists based on stderr) for user '{target_user}'.")
            else:
                app_logger.error(f"Failed applying OMZ enhancement '{item_name}' for user '{target_user}'. Command: '{e_cmd.cmd}', Exit: {e_cmd.returncode}, Stderr: {e_cmd.stderr.strip() if e_cmd.stderr else 'N/A'}", exc_info=False)
                overall_success = False
        except Exception as e_cmd_unexpected:
            con.print_error(f"Unexpected error applying OMZ enhancement '{item_name}': {e_cmd_unexpected}")
            app_logger.error(f"Unexpected error for OMZ enhancement '{item_name}' for user '{target_user}': {e_cmd_unexpected}", exc_info=True)
            overall_success = False
            
    return overall_success


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

    zsh_path = _check_zsh_installed()
    current_shell = system_utils.get_user_shell(target_user, logger=app_logger, print_fn_warning=con.print_warning)
    # is_zsh_default will be determined and updated after potential call to _handle_zsh_default_shell_setup
    
    phase2_config = config_loader.get_phase_data(app_config, "phase2_basic_configuration")
    zsh_should_be_dnf_installed_in_phase2 = False
    if isinstance(phase2_config, dict):
        dnf_pkgs_ph2 = phase2_config.get("dnf_packages", [])
        if isinstance(dnf_pkgs_ph2, list):
            zsh_should_be_dnf_installed_in_phase2 = "zsh" in [str(pkg).lower() for pkg in dnf_pkgs_ph2]

    user_wants_to_proceed_with_zsh_enhancements = True
    proceed_with_omz_and_plugins = True # This flag will control OMZ/plugin steps

    if not zsh_path:
        if zsh_should_be_dnf_installed_in_phase2:
            con.print_warning("Zsh was expected from Phase 2 DNF packages but is not currently found.")
            app_logger.warning("Zsh expected from Phase 2 DNF but not found by _check_zsh_installed().")
            if not con.confirm_action("Proceed with Zsh-specific enhancements (Oh My Zsh, etc.)? (These may fail).", default=False):
                user_wants_to_proceed_with_zsh_enhancements = False
        else:
            con.print_warning("Zsh is not installed. Consider adding 'zsh' to Phase 2 DNF packages for Oh My Zsh.")
            app_logger.warning("Zsh not found and not in Phase 2 DNF. OMZ installation might try to install Zsh or fail.")
            if not con.confirm_action("Zsh not found. Attempt Oh My Zsh and other terminal enhancements?", default=False):
                user_wants_to_proceed_with_zsh_enhancements = False
    else: # Zsh is installed
        is_zsh_default_initially = current_shell is not None and "zsh" in Path(current_shell).name.lower()
        if not is_zsh_default_initially:
            # Call helper to handle setting Zsh as default.
            # The helper returns False only on critical failure to set default.
            # If user declines, it returns True, and we skip OMZ based on user_wants_to_proceed_with_zsh_enhancements.
            shell_setup_ok = _handle_zsh_default_shell_setup(target_user, zsh_path, current_shell)
            if not shell_setup_ok: # Critical failure in set_default_shell
                overall_success = False
                proceed_with_omz_and_plugins = False # Cannot proceed with OMZ if shell setup failed critically
                user_wants_to_proceed_with_zsh_enhancements = False # To prevent .zshrc copy later if default failed
            elif not (system_utils.get_user_shell(target_user, logger=app_logger) == zsh_path) : # User declined or some other non-critical issue
                 # Re-check if Zsh is default AFTER the call (if user confirmed, it should be set)
                 # If user declined in helper, they don't want Zsh enhancements.
                is_zsh_now_default = system_utils.get_user_shell(target_user, logger=app_logger, print_fn_warning=con.print_warning) == zsh_path
                if not is_zsh_now_default: # User declined setting Zsh as default
                    user_wants_to_proceed_with_zsh_enhancements = False
                    proceed_with_omz_and_plugins = False 
                    con.print_info("Zsh will not be set as default. Oh My Zsh and related enhancements will be skipped.")
                    app_logger.info(f"User declined setting Zsh as default for '{target_user}'. OMZ enhancements skipped.")
        # If Zsh was already default, user_wants_to_proceed_with_zsh_enhancements remains True by default.

    if not user_wants_to_proceed_with_zsh_enhancements:
        con.print_info("Skipping Zsh-specific terminal enhancements (including Oh My Zsh and plugins) based on earlier choices.")
        app_logger.info("User opted out of Zsh-specific terminal enhancements or a prerequisite failed/was declined.")
        # proceed_with_omz_and_plugins is already False or will be effectively skipped
    
    # Update is_zsh_default status after potential changes
    current_shell = system_utils.get_user_shell(target_user, logger=app_logger, print_fn_warning=con.print_warning)
    is_zsh_default = current_shell is not None and "zsh" in Path(current_shell).name.lower()

    if proceed_with_omz_and_plugins and user_wants_to_proceed_with_zsh_enhancements:
        app_logger.info("Proceeding with Oh My Zsh installation and plugin setup.")
        phase3_config_data = config_loader.get_phase_data(app_config, "phase3_terminal_enhancement")
        
        if not isinstance(phase3_config_data, dict):
            con.print_warning("No valid Phase 3 config data found. Skipping OMZ/plugin specific enhancements.")
            app_logger.warning("No Phase 3 config (not a dict). Only dotfiles might be copied if Zsh is default.")
            proceed_with_omz_and_plugins = False # Cannot do OMZ without config
        else:
            omz_install_key = "omz"
            omz_install_command_template = phase3_config_data.get(omz_install_key) # Use .get for safety
            
            # Make a mutable copy for plugin installation, excluding OMZ installer itself
            enhancement_commands_for_plugins = phase3_config_data.copy()
            if omz_install_key in enhancement_commands_for_plugins:
                del enhancement_commands_for_plugins[omz_install_key]

            omz_setup_successful = _handle_oh_my_zsh_installation(
                target_user, target_user_home, omz_install_command_template
            )

            if not omz_setup_successful:
                con.print_error("Oh My Zsh setup failed or was skipped. Subsequent plugin installations will be skipped.")
                app_logger.error(f"OMZ setup failed for '{target_user}' or OMZ not found and no install command. Skipping plugins.")
                overall_success = False
                proceed_with_omz_and_plugins = False # Stop further OMZ steps
            else: # OMZ setup was successful (or already existed and verified)
                app_logger.info(f"OMZ setup successful for '{target_user}'. Proceeding to plugins/themes.")
                if not enhancement_commands_for_plugins:
                    con.print_info("No Oh My Zsh plugin/theme commands found in configuration.")
                    app_logger.info("No OMZ plugin/theme commands in config to execute.")
                elif not _install_omz_plugins_and_themes(
                    target_user, target_user_home, enhancement_commands_for_plugins
                ):
                    con.print_warning("Some Oh My Zsh plugins/themes failed to install.")
                    app_logger.warning(f"Failures encountered during OMZ plugin/theme installation for '{target_user}'.")
                    overall_success = False
    
    # --- Dotfile Copying ---
    project_root = Path(__file__).resolve().parent.parent
    
    # Copy .zshrc if Zsh is installed AND (it's now the default OR the user initially wanted Zsh enhancements and didn't hit a blocking error)
    # The user_wants_to_proceed_with_zsh_enhancements flag covers cases where Zsh isn't made default by choice,
    # or if Zsh wasn't found but they wanted to try OMZ anyway.
    if zsh_path and user_wants_to_proceed_with_zsh_enhancements and is_zsh_default :
        if not _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root):
            con.print_warning("Failed to copy .zshrc. Your Zsh terminal might not use the custom configuration.")
            app_logger.warning(f"Failed to copy .zshrc for user '{target_user}'")
            overall_success = False
    elif zsh_path and not is_zsh_default:
         app_logger.info(f"Zsh is installed but not default, and user opted out or setup failed. Not copying .zshrc for {target_user}.")
    elif not zsh_path:
        app_logger.info(f"Zsh is not installed. Not copying .zshrc for {target_user}.")

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