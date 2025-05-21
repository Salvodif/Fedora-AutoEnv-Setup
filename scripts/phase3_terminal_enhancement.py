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
        # con.print_error already called by get_user_home_dir
        app_logger.error(f"Target user home for '{target_user}' not found. Aborting user-specific part of Phase 3.")
        return False 

    con.print_info(f"Running terminal enhancements for user: [bold cyan]{target_user}[/bold cyan] (Home: {target_user_home})")
    app_logger.info(f"Running Phase 3 for user: {target_user}, Home: {target_user_home}")

    zsh_path = _check_zsh_installed()
    current_shell = system_utils.get_user_shell(target_user, logger=app_logger, print_fn_warning=con.print_warning)
    is_zsh_default = current_shell is not None and "zsh" in Path(current_shell).name.lower()
    
    phase2_config = config_loader.get_phase_data(app_config, "phase2_basic_configuration")
    zsh_should_be_dnf_installed_in_phase2 = False
    if isinstance(phase2_config, dict): # Check if phase2_config is valid
        dnf_pkgs_ph2 = phase2_config.get("dnf_packages", [])
        if isinstance(dnf_pkgs_ph2, list): # Ensure dnf_packages is a list
            zsh_should_be_dnf_installed_in_phase2 = "zsh" in [str(pkg).lower() for pkg in dnf_pkgs_ph2]

    user_wants_to_proceed_with_zsh_enhancements = True 

    if not zsh_path:
        if zsh_should_be_dnf_installed_in_phase2:
            con.print_warning("Zsh was expected from Phase 2 DNF packages but is not currently found by this script.")
            con.print_info("This might mean Phase 2 failed, Zsh isn't in PATH, or it wasn't installed correctly.")
            app_logger.warning("Zsh expected from Phase 2 DNF packages but not found by _check_zsh_installed().")
            if not con.confirm_action("Proceed with Zsh-specific terminal enhancements (Oh My Zsh, etc.)? (These may fail if Zsh is truly unavailable).", default=False):
                user_wants_to_proceed_with_zsh_enhancements = False
        else: 
            con.print_warning("Zsh is not installed. It's highly recommended to add 'zsh' to Phase 2 DNF packages for Oh My Zsh.")
            app_logger.warning("Zsh not found and not listed in Phase 2 DNF packages. Oh My Zsh installation will likely fail or try to install Zsh.")
            if not con.confirm_action("Zsh is not found. Do you want to attempt Oh My Zsh installation and other terminal enhancements? (OMZ might try to install Zsh or fail).", default=False):
                user_wants_to_proceed_with_zsh_enhancements = False
    elif not is_zsh_default: # Zsh is installed, but not default
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
                # system_utils.set_default_shell already prints errors.
                con.print_error("CRITICAL: Failed to set Zsh as default. Oh My Zsh relies on Zsh being the login shell.")
                app_logger.error(f"CRITICAL: Failed to set Zsh as default for {target_user}. Aborting Zsh-specific enhancements in Phase 3.")
                # Still attempt to copy .nanorc as it's independent of Zsh
                project_root_nano = Path(__file__).resolve().parent.parent
                _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root_nano)
                return False # Treat failure to set Zsh as default (when user wants it) as critical for OMZ part.
            else:
                is_zsh_default = True # Assume success for the rest of this script run
                app_logger.info(f"Zsh successfully set as default for {target_user} (pending next login for full effect).")
        else: # User chose not to set Zsh as default
            user_wants_to_proceed_with_zsh_enhancements = False
            con.print_info("Zsh will not be set as default. Oh My Zsh and related enhancements will be skipped.")
            app_logger.info(f"User declined setting Zsh as default for '{target_user}'. OMZ enhancements skipped.")


    if not user_wants_to_proceed_with_zsh_enhancements:
        con.print_info("Skipping Zsh-specific terminal enhancements (including Oh My Zsh and plugins).")
        app_logger.info("User opted out of Zsh-specific terminal enhancements or a prerequisite (like setting Zsh default) failed/was declined.")
        project_root_nano = Path(__file__).resolve().parent.parent
        _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root_nano)
        # If overall_success was already False due to _set_default_shell issue but user chose to skip,
        # this phase might still be considered "completed with errors" if we return overall_success.
        # For now, if they skip, we consider this path "successful" in terms of not attempting OMZ.
        return True 

    app_logger.info("Proceeding with Zsh terminal enhancements (Oh My Zsh, plugins, dotfiles).")
    
    phase3_config_data = config_loader.get_phase_data(app_config, "phase3_terminal_enhancement")
    if not isinstance(phase3_config_data, dict): 
        con.print_warning("No valid configuration data (expected a dictionary) found for Phase 3. Skipping specific Oh My Zsh/plugin enhancements.")
        app_logger.warning("No Phase 3 configuration data (not a dict) found in config. Will only attempt dotfile copy if applicable.")
        # If Zsh is default (or was made default), still try to copy .zshrc
        if zsh_path and is_zsh_default:
            project_root_zsh = Path(__file__).resolve().parent.parent
            _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root_zsh)
        project_root_nano = Path(__file__).resolve().parent.parent
        _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root_nano)
        return True # No specific OMZ config, but basic dotfiles might be copied.

    # Make a mutable copy for pop
    phase3_enhancement_commands = phase3_config_data.copy() 
    
    omz_install_key = "omz" 
    omz_install_command_template = phase3_enhancement_commands.pop(omz_install_key, None)
    omz_installed_successfully_this_run = False 
    omz_base_dir_exists = False
    omz_custom_dir_exists = False 

    if omz_install_command_template:
        con.print_sub_step("Processing Oh My Zsh installation...")
        app_logger.info("Checking for existing Oh My Zsh installation before running installer.")
        # Check for $HOME/.oh-my-zsh existence AS THE TARGET USER
        omz_base_path_check_cmd = f"test -d {shlex.quote(str(target_user_home / '.oh-my-zsh'))}"
        try:
            omz_exists_proc = system_utils.run_command(
                omz_base_path_check_cmd, run_as_user=target_user, shell=True, # shell=True for test -d
                check=False, capture_output=True, logger=app_logger, print_fn_info=None 
            )
            if omz_exists_proc.returncode == 0:
                con.print_info("Oh My Zsh directory ($HOME/.oh-my-zsh) already exists. Skipping OMZ installation script.")
                app_logger.info("OMZ directory $HOME/.oh-my-zsh exists, skipping installer.")
                omz_base_dir_exists = True 
            else: # OMZ base directory does not exist, proceed with installation
                con.print_info("Oh My Zsh directory ($HOME/.oh-my-zsh) not found. Running Oh My Zsh installation script...")
                con.print_panel(
                    "The Oh My Zsh installer may be [bold]interactive[/].\n"
                    "Its output will be displayed directly below.\n"
                    "Please follow any prompts from the OMZ installer itself.\n"
                    "[yellow]IMPORTANT:[/] This script attempts to run OMZ non-interactively regarding shell changes "
                    "by setting `RUNZSH=no` and `CHSH=no` environment variables for the installer.",
                    title="Oh My Zsh Installation", style="yellow"
                )
                
                omz_env_vars_for_installer = {"RUNZSH": "no", "CHSH": "no"} 
                
                # Ensure curl is available (as target_user context)
                curl_check_cmd = "command -v curl"
                curl_check_proc = system_utils.run_command(curl_check_cmd, run_as_user=target_user, shell=True, check=False, capture_output=True, logger=app_logger, print_fn_info=None)
                if curl_check_proc.returncode != 0:
                    con.print_error("`curl` command not found in user's environment. Cannot download Oh My Zsh installer.")
                    app_logger.error(f"`curl` not found for Oh My Zsh installation (user: {target_user}). Add `curl` to DNF packages.")
                    return False # Critical failure for OMZ install

                # The command from config is usually "curl ... | bash" or "sh -c \"$(curl ...)\""
                final_omz_command_from_config = str(omz_install_command_template)
                                
                # Run the OMZ installer command as the target user
                system_utils.run_command(
                    final_omz_command_from_config,
                    run_as_user=target_user,
                    shell=True, # The OMZ command from config often requires a shell (e.g., for pipelines or subshells)
                    capture_output=False, # Stream OMZ installer output directly
                    check=True, # Fail if OMZ installer script returns non-zero
                    env_vars=omz_env_vars_for_installer, 
                    print_fn_info=None, # Installer will print its own info
                    print_fn_error=con.print_error, # Let run_command use Rich for errors
                    logger=app_logger
                )
                con.print_success("Oh My Zsh installation script finished successfully.")
                app_logger.info("OMZ installation script finished successfully.")
                omz_installed_successfully_this_run = True
                omz_base_dir_exists = True # Installer should have created it
                con.print_warning("A new Zsh shell session (new terminal or re-login) is required for all OMZ changes to take full effect.")
        
        except subprocess.CalledProcessError as e_omz_script:
            # run_command already logs and prints error message
            app_logger.error(f"OMZ installation script execution failed for user '{target_user}'. Command: {e_omz_script.cmd}, Exit: {e_omz_script.returncode}", exc_info=False)
            app_logger.error(f"Failed OMZ command (as {target_user}, with RUNZSH/CHSH=no): {final_omz_command_from_config if 'final_omz_command_from_config' in locals() else omz_install_command_template}")
            con.print_error("Oh My Zsh installation is CRITICAL for subsequent terminal enhancements. Aborting Phase 3.")
            return False 

        except Exception as e_unexpected_omz: 
            con.print_error(f"Oh My Zsh installation process encountered an unexpected error: {e_unexpected_omz}")
            app_logger.error(f"OMZ installation - unexpected error for user '{target_user}': {e_unexpected_omz}", exc_info=True)
            con.print_error("Oh My Zsh installation is CRITICAL. Aborting Phase 3.")
            return False 
    
    else: # No OMZ install command in config, just check if $HOME/.oh-my-zsh exists
        omz_base_path_check_cmd = f"test -d {shlex.quote(str(target_user_home / '.oh-my-zsh'))}"
        omz_exists_proc = system_utils.run_command(
            omz_base_path_check_cmd, run_as_user=target_user, shell=True,
            check=False, capture_output=True, logger=app_logger, print_fn_info=None
        )
        if omz_exists_proc.returncode == 0:
            omz_base_dir_exists = True
            app_logger.info("OMZ install command not in config, but $HOME/.oh-my-zsh exists.")
        else:
            app_logger.info("OMZ install command not in config and $HOME/.oh-my-zsh does not exist. Skipping OMZ-dependent steps.")
            # No OMZ, so no plugins. Copy dotfiles and exit successfully for this path.
            if zsh_path and is_zsh_default:
                 _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, Path(__file__).resolve().parent.parent)
            _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, Path(__file__).resolve().parent.parent)
            return True # Successfully completed what could be done without OMZ config.


    # Check for $ZSH_CUSTOM (e.g., $HOME/.oh-my-zsh/custom) IFF OMZ base dir exists
    if omz_base_dir_exists:
        # Define ZSH_CUSTOM path explicitly based on user's home for the check
        zsh_custom_path_abs = target_user_home / ".oh-my-zsh" / "custom"
        zsh_custom_check_cmd = f"test -d {shlex.quote(str(zsh_custom_path_abs))}"
        
        custom_exists_proc = system_utils.run_command(
            zsh_custom_check_cmd, run_as_user=target_user, shell=True, # shell=True for test -d
            check=False, capture_output=True, logger=app_logger, print_fn_info=None
        )
        if custom_exists_proc.returncode == 0:
            omz_custom_dir_exists = True
            app_logger.info(f"OMZ custom directory ({zsh_custom_path_abs}) found for user '{target_user}'.")
        else:
            app_logger.warning(f"OMZ custom directory ({zsh_custom_path_abs}) NOT found for user '{target_user}'.")
            if omz_installed_successfully_this_run: 
                con.print_error(f"CRITICAL: Oh My Zsh installer seemed to finish, but its 'custom' directory ({zsh_custom_path_abs}) is missing. This indicates a problem with OMZ setup. Aborting further OMZ enhancements.")
                app_logger.error(f"CRITICAL: OMZ 'custom' directory missing for {target_user} after presumed successful install. Aborting OMZ enhancements.")
                overall_success = False 
    else: 
        app_logger.info("OMZ base directory $HOME/.oh-my-zsh not found for user. Skipping plugin setup.")

    # Proceed with plugins ONLY IF OMZ base AND its custom directory exist AND overall_success is still true
    if omz_base_dir_exists and omz_custom_dir_exists and overall_success:
        for item_name, command_str_template in phase3_enhancement_commands.items():
            app_logger.debug(f"Processing enhancement item: {item_name}, command template: {command_str_template}")
            if not isinstance(command_str_template, str) or not command_str_template.strip():
                con.print_warning(f"Skipping invalid command for item '{item_name}' (not a string or empty).")
                app_logger.warning(f"Invalid command template for '{item_name}'.")
                continue
            
            con.print_sub_step(f"Processing: {item_name}")
            
            # Substitute $HOME and ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}
            # Note: ZSH_CUSTOM default is $HOME/.oh-my-zsh/custom. We use the absolute path.
            # OMZ itself sets $ZSH_CUSTOM. If it's not set, this default is used by OMZ.
            # For robustness, we can define what $ZSH_CUSTOM should be for our script's context.
            # If we are here, omz_custom_dir_exists is true, meaning $HOME/.oh-my-zsh/custom exists.
            # So, use target_user_home / ".oh-my-zsh" / "custom" for ZSH_CUSTOM.
            
            # Correctly define paths for substitution
            home_dir_str_for_sub = str(target_user_home)
            zsh_custom_dir_str_for_sub = str(target_user_home / ".oh-my-zsh" / "custom")

            # Perform substitutions
            command_str_processed = command_str_template.replace("$HOME", home_dir_str_for_sub)
            command_str_processed = command_str_processed.replace("${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}", zsh_custom_dir_str_for_sub)
            command_str_processed = command_str_processed.replace("$ZSH_CUSTOM", zsh_custom_dir_str_for_sub) # Also handle direct $ZSH_CUSTOM

            if "ZSH_CUSTOM:~" in command_str_template: # Original template check
                con.print_warning(f"Warning for '{item_name}': Original command template uses 'ZSH_CUSTOM:~'. This script substitutes with absolute custom path. Ensure command logic is compatible.")

            # Git clone target checking
            is_git_clone_cmd = "git clone" in command_str_processed.lower()
            should_skip_due_to_existence = False
            if is_git_clone_cmd:
                try:
                    cmd_parts = shlex.split(command_str_processed)
                    target_dir_in_cmd_unexpanded = "" # This was for unexpanded, now we use expanded_target_dir_str directly
                    
                    # Find the target directory of the git clone command
                    # Assuming format: git clone <repo_url> <target_directory>
                    clone_idx = -1
                    try: clone_idx = cmd_parts.index("clone")
                    except ValueError: pass 

                    if clone_idx != -1 and len(cmd_parts) > clone_idx + 2: 
                        # The part after <repo_url> is the potential target directory
                        potential_target_path_str = cmd_parts[clone_idx + 2]
                        if not potential_target_path_str.startswith("-"): # Not an option like --depth
                             # The path is already expanded because command_str_processed has $HOME and $ZSH_CUSTOM substituted
                            expanded_target_dir_str = potential_target_path_str

                            if expanded_target_dir_str:
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
                                elif proc.returncode != 1: # 1 means test evaluated to false (dir doesn't exist), other codes are errors
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
                    command_str_processed, # Use the processed command string
                    run_as_user=target_user, 
                    shell=True, # Many of these commands (curl | sh, cargo install, git clone) benefit from or require shell
                    capture_output=True, # Capture for logging, run_command can show summaries
                    check=True, 
                    print_fn_info=con.print_info, # For "Executing..."
                    print_fn_error=con.print_error,
                    print_fn_sub_step=con.print_sub_step, # For STDOUT/STDERR summaries
                    logger=app_logger
                )
                con.print_success(f"Applied: {item_name}")
                app_logger.info(f"Applied enhancement '{item_name}' for user '{target_user}'.")
            except subprocess.CalledProcessError as e_cmd:
                # run_command already logs and prints a generic error.
                # Add specific context here if needed.
                if is_git_clone_cmd and e_cmd.returncode == 128 and e_cmd.stderr and \
                   ("already exists and is not an empty directory" in e_cmd.stderr.lower() or \
                    ("destination path" in e_cmd.stderr.lower() and "already exists" in e_cmd.stderr.lower())):
                    con.print_info(f"Git clone for '{item_name}' reported destination exists (via stderr after attempt). Considered skipped.")
                    app_logger.info(f"Git clone for '{item_name}' skipped (error 128, dir exists based on stderr) for user '{target_user}'.")
                else: 
                    app_logger.error(f"Failed applying enhancement '{item_name}' for user '{target_user}'. Command: '{e_cmd.cmd}', Exit: {e_cmd.returncode}, Stderr: {e_cmd.stderr.strip() if e_cmd.stderr else 'N/A'}", exc_info=False)
                    overall_success = False 
            except Exception as e_cmd_unexpected: 
                con.print_error(f"Unexpected error applying '{item_name}': {e_cmd_unexpected}")
                app_logger.error(f"Unexpected error for '{item_name}' for user '{target_user}': {e_cmd_unexpected}", exc_info=True)
                overall_success = False 
    elif not (omz_base_dir_exists and omz_custom_dir_exists) : 
        con.print_warning("Oh My Zsh base or custom directory not found/verified. Skipping OMZ plugin configuration.")
        app_logger.warning(f"OMZ base or custom directory not found/verified for user '{target_user}'. Skipping plugin config.")


    # --- Dotfile Copying (always attempted if user wanted Zsh enhancements initially, or if Zsh is default) ---
    project_root = Path(__file__).resolve().parent.parent
    
    # Copy .zshrc if Zsh is installed AND (it's the default OR the user explicitly wanted Zsh enhancements)
    if zsh_path and (is_zsh_default or user_wants_to_proceed_with_zsh_enhancements): 
        if not _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root):
            con.print_warning("Failed to copy .zshrc. Your Zsh terminal might not use the custom configuration.")
            app_logger.warning(f"Failed to copy .zshrc for user '{target_user}'")
            overall_success = False # Custom .zshrc is important for the Zsh experience
    elif zsh_path and not is_zsh_default and not user_wants_to_proceed_with_zsh_enhancements:
        app_logger.info(f"Zsh is installed but not default, and user skipped Zsh enhancements. Not copying .zshrc for {target_user}.")
    elif not zsh_path:
        app_logger.info(f"Zsh is not installed. Not copying .zshrc for {target_user}.")

    
    # Always attempt to copy .nanorc if home directory is valid
    if not _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root):
        con.print_warning("Failed to copy .nanorc.")
        app_logger.warning(f"Failed to copy .nanorc for user '{target_user}'")
        # overall_success = False # Nanorc is less critical than .zshrc for terminal *enhancements* phase success

    # --- Phase Completion Summary ---
    if overall_success:
        con.print_success("Phase 3: Terminal Enhancement completed.")
        app_logger.info(f"Phase 3 completed successfully for user '{target_user}'.")
    else:
        con.print_error("Phase 3: Terminal Enhancement completed with errors. Please review the output and logs.")
        app_logger.error(f"Phase 3 completed with errors for user '{target_user}'.")
    
    return overall_success