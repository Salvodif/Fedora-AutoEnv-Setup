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
# ... (Helper functions _get_user_shell, _check_zsh_installed, _ensure_shell_in_etc_shells, _set_default_shell, _get_user_home, _copy_config_file_to_user_home remain unchanged from the previous correct version)
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
    Prefers common paths like /usr/bin/zsh or /bin/zsh, then `which`.
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
        app_logger.info(f"Zsh found via 'which' at {zsh_path_which}.") 
        return zsh_path_which
        
    app_logger.info("Zsh not found by _check_zsh_installed.")
    return None


def _ensure_shell_in_etc_shells(shell_path: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Ensures the given shell_path is listed in /etc/shells.
    Attempts to create /etc/shells if it doesn't exist and script is root.
    Requires sudo privileges to modify /etc/shells.
    """
    _log = logger or app_logger
    if not shell_path: 
        con.print_error("Cannot ensure empty shell path in /etc/shells.")
        _log.error("Empty shell_path passed to _ensure_shell_in_etc_shells.")
        return False
    
    _log.info(f"Ensuring '{shell_path}' is in /etc/shells.")
    etc_shells_path = Path("/etc/shells")
    try:
        if not etc_shells_path.is_file():
            con.print_warning(f"File {etc_shells_path} not found.")
            _log.warning(f"{etc_shells_path} not found.")
            if os.geteuid() == 0: # If script is root, try to create it
                try:
                    con.print_info(f"Attempting to create {etc_shells_path} as root.")
                    system_utils.run_command(f"sudo touch {shlex.quote(str(etc_shells_path))}", shell=True, logger=_log, print_fn_info=con.print_info)
                    system_utils.run_command(["sudo", "chown", "root:root", str(etc_shells_path)], logger=_log, print_fn_info=con.print_info)
                    system_utils.run_command(["sudo", "chmod", "644", str(etc_shells_path)], logger=_log, print_fn_info=con.print_info)
                    _log.info(f"Created {etc_shells_path}.")
                except Exception as e_create:
                    con.print_error(f"Failed to create {etc_shells_path}: {e_create}")
                    _log.error(f"Failed to create {etc_shells_path}: {e_create}")
                    return False
            else: # Not root and file doesn't exist, cannot proceed
                con.print_error(f"Cannot create {etc_shells_path} without root privileges.")
                return False

        current_shells_content = ""
        if os.geteuid() == 0:
            try:
                 cat_proc = system_utils.run_command(
                    ["sudo", "cat", str(etc_shells_path)],
                    capture_output=True, check=True, logger=_log, print_fn_info=None
                 )
                 current_shells_content = cat_proc.stdout
            except Exception as e_cat: 
                _log.warning(f"Reading {etc_shells_path} with `sudo cat` failed ({e_cat}). Attempting direct read (may fail due to permissions).")
                if etc_shells_path.exists(): 
                    current_shells_content = etc_shells_path.read_text(encoding='utf-8')
                else:
                    _log.error(f"{etc_shells_path} still not found after creation attempt. Cannot verify shells.")
                    return False
        else: 
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
    """Sets the default login shell for the specified user. Requires root privileges."""
    _log = logger or app_logger
    current_shell = _get_user_shell(username) 
    if current_shell == shell_path:
        con.print_info(f"Shell '{shell_path}' is already the default shell for user '{username}'.")
        _log.info(f"'{shell_path}' is already default for '{username}'.")
        return True

    con.print_sub_step(f"Setting Zsh ('{shell_path}') as default shell for user '{username}'...")
    _log.info(f"Setting '{shell_path}' as default for '{username}'.")
    
    if os.geteuid() != 0: 
        con.print_error(f"Cannot change shell for user '{username}'. This script part must be run as root to use 'chsh -s'.")
        _log.error(f"Cannot change shell for '{username}': not root for 'chsh -s'.")
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
            _log.warning(f"chsh for '{username}' to '{shell_path}' ran, but getent shows '{new_shell_check}'. Shell change likely takes effect on next login.")
            con.print_info("Please verify the shell after the user's next login.")
        
        return True 
    except subprocess.CalledProcessError as e:
        con.print_error(f"The 'chsh' command failed to set shell for '{username}'. Exit code: {e.returncode}")
        if e.stderr: con.print_error(f"chsh STDERR: {e.stderr.strip()}")
        _log.error(f"chsh command failed for '{username}' (CalledProcessError): {e}", exc_info=False)
        return False
    except Exception as e: 
        con.print_error(f"An unexpected error occurred while trying to set default shell for '{username}': {e}")
        _log.error(f"Unexpected error setting default shell for '{username}': {e}", exc_info=True)
        return False


def _get_user_home(username: str) -> Optional[Path]:
    """Gets the home directory for the specified username."""
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
    """
    Copies a configuration file from the project's config directory to the target user's home.
    Manages backup of existing files. Uses `run_as_user` for file operations in user's home.
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
        test_exists_proc = system_utils.run_command(
            f"test -f {shlex.quote(str(target_file_path))}",
            run_as_user=target_user, shell=True, check=False, capture_output=True,
            print_fn_info=None, 
            logger=app_logger
        )
        target_exists_as_user = (test_exists_proc.returncode == 0)
        
        if target_exists_as_user:
            timestamp_str = f"backup_{int(time.time())}_{Path.cwd().name.replace(' ','_')}"
            backup_target_path_obj = target_user_home / f"{source_filename}.{timestamp_str}"
            
            backup_command_str = f"cp -pf {shlex.quote(str(target_file_path))} {shlex.quote(str(backup_target_path_obj))}"
            con.print_info(f"Existing '{target_file_path.name}' found. Will attempt to back it up to '{backup_target_path_obj.name}'.")
            app_logger.info(f"Target file '{target_file_path}' exists. Backup command (as user '{target_user}'): {backup_command_str}")
        else:
            app_logger.info(f"Target file '{target_file_path}' does not exist. No backup needed for user '{target_user}'.")
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
        app_logger.info(f"Successfully copied '{source_filename}' to '{target_user_home}' as user '{target_user}'.")
        return True
    except Exception as e_copy: 
        app_logger.error(f"Failed to copy '{source_filename}' to '{target_user_home}' (user: {target_user}): {e_copy}", exc_info=True)
        return False

# --- Main Phase Function ---

def run_phase3(app_config: dict) -> bool:
    con.print_step("PHASE 3: Terminal Enhancement")
    app_logger.info("Starting Phase 3: Terminal Enhancement.")
    overall_success = True # Assume success initially, set to False on critical errors

    target_user = system_utils.get_target_user(
        logger=app_logger, print_fn_info=con.print_info,
        print_fn_error=con.print_error, print_fn_warning=con.print_warning
    )
    if not target_user:
        app_logger.error("Cannot determine target user for Phase 3. Aborting phase.")
        return False # Critical failure

    target_user_home = _get_user_home(target_user)
    if not target_user_home: 
        con.print_error(f"Cannot determine home directory for '{target_user}'. Aborting user-specific Phase 3 steps.")
        app_logger.error(f"Target user home for '{target_user}' not found. Aborting user-specific part of Phase 3.")
        return False # Critical failure

    con.print_info(f"Running terminal enhancements for user: [bold cyan]{target_user}[/bold cyan]")
    app_logger.info(f"Running Phase 3 for user: {target_user}")

    zsh_path = _check_zsh_installed()
    current_shell = _get_user_shell(target_user) 
    is_zsh_default = current_shell is not None and "zsh" in Path(current_shell).name.lower()
    
    phase2_config = config_loader.get_phase_data(app_config, "phase2_basic_configuration")
    zsh_should_be_dnf_installed = False
    if isinstance(phase2_config, dict):
        zsh_should_be_dnf_installed = "zsh" in [pkg.lower() for pkg in phase2_config.get("dnf_packages", [])]

    user_wants_to_proceed_with_enhancements = True 

    if not zsh_path:
        if zsh_should_be_dnf_installed:
            con.print_warning("Zsh was expected from Phase 2 DNF packages but is not currently found.")
            con.print_info("This might mean Phase 2 failed, Zsh isn't in PATH, or it wasn't installed correctly.")
            if not con.confirm_action("Proceed with Zsh-specific terminal enhancements (Oh My Zsh, etc.)? (These may fail if Zsh is truly unavailable).", default=False):
                user_wants_to_proceed_with_enhancements = False
        else: 
            con.print_warning("Zsh is not installed. It's highly recommended to add 'zsh' to Phase 2 DNF packages for Oh My Zsh.")
            if not con.confirm_action("Zsh is not found. Do you want to attempt Oh My Zsh installation and other terminal enhancements? (OMZ might try to install Zsh or fail).", default=False):
                user_wants_to_proceed_with_enhancements = False
    elif not is_zsh_default:
        con.print_info(f"Zsh is installed ('{zsh_path}') but is not the default shell for '{target_user}'. Current shell: '{current_shell or 'Not set/Unknown'}'.")
        if con.confirm_action(f"Set Zsh as default shell for '{target_user}' and proceed with enhancements?", default=True):
            if not _set_default_shell(target_user, zsh_path, logger=app_logger): 
                # _set_default_shell already prints errors.
                # This is a significant issue for OMZ.
                con.print_error("CRITICAL: Failed to set Zsh as default. Oh My Zsh relies on Zsh being the login shell.")
                app_logger.error(f"CRITICAL: Failed to set Zsh as default for {target_user}. Aborting Phase 3 Zsh enhancements.")
                # Copy .nanorc as it's independent
                project_root_nano = Path(__file__).resolve().parent.parent
                _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root_nano)
                return False # Treat failure to set Zsh as default (when user wants it) as critical for OMZ part.
            else:
                is_zsh_default = True # Assume success for the rest of this script run
        else: # User chose not to set Zsh as default
            user_wants_to_proceed_with_enhancements = False
            con.print_info("Zsh will not be set as default. Oh My Zsh and related enhancements will be skipped.")
            app_logger.info(f"User declined setting Zsh as default for '{target_user}'. OMZ enhancements skipped.")


    if not user_wants_to_proceed_with_enhancements:
        con.print_info("Skipping Zsh-specific terminal enhancements (including Oh My Zsh and plugins).")
        app_logger.info("User opted out of Zsh-specific terminal enhancements or a prerequisite (like setting Zsh default) failed.")
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
        # If Zsh is default, still try to copy .zshrc
        if zsh_path and is_zsh_default:
            project_root_zsh = Path(__file__).resolve().parent.parent
            _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root_zsh)
        project_root_nano = Path(__file__).resolve().parent.parent
        _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root_nano)
        return True # No specific OMZ config, but basic dotfiles might be copied.

    phase3_config_commands = phase3_config_data.copy() 
    
    omz_install_key = "omz" 
    omz_install_command_template = phase3_config_commands.pop(omz_install_key, None)
    omz_installed_successfully_this_run = False # Tracks if OMZ *installer* ran successfully *now*
    omz_base_dir_exists = False
    omz_custom_dir_exists = False # $ZSH_CUSTOM, e.g., $HOME/.oh-my-zsh/custom

    if omz_install_command_template:
        con.print_sub_step("Processing Oh My Zsh installation...")
        app_logger.info("Checking for existing Oh My Zsh installation before running installer.")
        omz_base_path_check_cmd = "test -d $HOME/.oh-my-zsh" 
        try:
            omz_exists_proc = system_utils.run_command(
                omz_base_path_check_cmd, run_as_user=target_user, shell=True,
                check=False, capture_output=True, logger=app_logger, print_fn_info=None 
            )
            if omz_exists_proc.returncode == 0:
                con.print_info("Oh My Zsh directory ($HOME/.oh-my-zsh) already exists. Skipping OMZ installation script.")
                app_logger.info("OMZ directory $HOME/.oh-my-zsh exists, skipping installer.")
                omz_base_dir_exists = True # It exists
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
                
                omz_env_vars = {"RUNZSH": "no", "CHSH": "no"} 
                
                # The OMZ command from config is usually like: "sh -c \"$(curl ...)\""
                # We want to execute this string directly using bash -c
                # The existing command: "sh -c '$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)'"
                # To fix "sh: line 1: #!/bin/sh: No such file or directory", we can try ensuring the subshell invoked by bash -c
                # directly executes the script content from curl, or make sure `sh` is callable.
                # A more direct way: curl ... | sh (or bash)
                # Let's try to make the original config command work by ensuring `sh` is in PATH or by using `bash` explicitly if `sh` causes issues.
                # The error "sh: line 1: #!/bin/sh: No such file or directory" for the *inner* sh is odd if /bin/sh exists.
                # It might be an issue with how the output of curl is being processed or if the curl command itself fails silently before sh -c.

                # Simplification: try to pipe curl output directly to bash
                # This requires `curl` to be installed. Add it as a dependency to phase1 or check here.
                # Example: "curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh | bash"
                # However, the config has "sh -c '$(curl...)'". Let's make that robust.
                # The issue might be that the 'sh -c' part *within* the string passed to 'bash -c' is the problem.
                # The command from config: `omz_install_command_template`
                # Original execution: `sudo -u user bash -c "CONFIG_COMMAND"`
                # If CONFIG_COMMAND is "sh -c '$(curl...)'", then `bash -c` tries to run `sh`.
                # The `#!/bin/sh` not found error (127) usually means the *interpreter* (`/bin/sh`) for the script downloaded by `curl`
                # is not found or the script content itself is bad.
                # Let's ensure `curl` is available.

                curl_check = system_utils.run_command("command -v curl", run_as_user=target_user, shell=True, check=False, capture_output=True, logger=app_logger)
                if curl_check.returncode != 0:
                    con.print_error("`curl` command not found. Cannot download Oh My Zsh installer.")
                    app_logger.error("`curl` not found for Oh My Zsh installation. Add `curl` to DNF packages.")
                    return False # Critical failure for OMZ install

                # The original command in config is likely fine. The `127` error is puzzling if /bin/sh exists.
                # Could be that `install.sh` itself has an issue when run this way, or some env var is missing.
                # Let's stick to the configured command and log more if it fails.
                final_omz_command_from_config = str(omz_install_command_template)
                                
                system_utils.run_command(
                    final_omz_command_from_config,
                    run_as_user=target_user,
                    shell=True, # The command from config likely requires a shell
                    capture_output=False, 
                    check=True, 
                    env_vars=omz_env_vars, 
                    print_fn_info=None, 
                    print_fn_error=con.print_error, 
                    logger=app_logger
                )
                con.print_success("Oh My Zsh installation script finished successfully.")
                app_logger.info("OMZ installation script finished successfully.")
                omz_installed_successfully_this_run = True
                omz_base_dir_exists = True # Installer should have created it
                con.print_warning("A new Zsh shell session (new terminal or re-login) is required for all OMZ changes to take full effect.")
        
        except subprocess.CalledProcessError as e_omz_script:
            # Detailed error logging
            con.print_error(f"Oh My Zsh installation script failed! Exit code: {e_omz_script.returncode}")
            if e_omz_script.stdout: con.print_error(f"OMZ Installer STDOUT:\n{e_omz_script.stdout.strip()}") # Use ERROR level for output on failure
            if e_omz_script.stderr: con.print_error(f"OMZ Installer STDERR:\n{e_omz_script.stderr.strip()}")
            app_logger.error(f"OMZ installation script execution failed: {e_omz_script}", exc_info=False)
            app_logger.error(f"Failed OMZ command was (as {target_user}, with RUNZSH/CHSH=no): {final_omz_command_from_config if 'final_omz_command_from_config' in locals() else omz_install_command_template}")
            con.print_error("Oh My Zsh installation is CRITICAL for subsequent terminal enhancements. Aborting Phase 3.")
            return False # CRITICAL FAILURE - terminate phase

        except Exception as e_unexpected_omz: 
            con.print_error(f"Oh My Zsh installation process encountered an unexpected error: {e_unexpected_omz}")
            app_logger.error(f"OMZ installation - unexpected error: {e_unexpected_omz}", exc_info=True)
            con.print_error("Oh My Zsh installation is CRITICAL. Aborting Phase 3.")
            return False # CRITICAL FAILURE - terminate phase
    
    else: # No OMZ install command in config, just check if $HOME/.oh-my-zsh exists
        omz_base_path_check_cmd = "test -d $HOME/.oh-my-zsh"
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


    # At this point, if omz_install_command_template was present, installer either succeeded or phase was aborted.
    # If omz_install_command_template was NOT present, omz_base_dir_exists reflects current state.

    # Check for $ZSH_CUSTOM (e.g., $HOME/.oh-my-zsh/custom) IFF OMZ base dir exists
    if omz_base_dir_exists:
        zsh_custom_check_cmd = "test -d ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}"
        custom_exists_proc = system_utils.run_command(
            zsh_custom_check_cmd, run_as_user=target_user, shell=True,
            check=False, capture_output=True, logger=app_logger, print_fn_info=None
        )
        if custom_exists_proc.returncode == 0:
            omz_custom_dir_exists = True
            app_logger.info("OMZ custom directory (e.g., $HOME/.oh-my-zsh/custom) found.")
        else:
            app_logger.warning("OMZ custom directory (e.g., $HOME/.oh-my-zsh/custom) NOT found.")
            if omz_installed_successfully_this_run: # If we just ran the installer and it "succeeded" but custom dir is missing
                con.print_error("CRITICAL: Oh My Zsh installer seemed to finish, but its 'custom' directory is missing. This indicates a problem with OMZ setup. Aborting further OMZ enhancements.")
                app_logger.error("CRITICAL: OMZ 'custom' directory missing after presumed successful install. Aborting OMZ enhancements.")
                # We don't return False for the whole phase here, as OMZ base might exist, but plugins won't work.
                # The main OMZ setup is the critical part. If that fails, the phase already returned False.
                # If it "succeeded" but `custom` is missing, plugins are skipped.
                overall_success = False # Mark that plugins part will fail/be skipped.
            # If OMZ existed before and `custom` is missing, that's an existing user misconfiguration. We can't fix that.
            # Plugins will be skipped.
    else: # OMZ base dir does not exist (either install failed before this point, or was never there and not in config)
        app_logger.info("OMZ base directory $HOME/.oh-my-zsh not found. Skipping plugin setup.")
        # Dotfiles will still be copied at the end.

    # Proceed with plugins ONLY IF OMZ base AND its custom directory exist
    if omz_base_dir_exists and omz_custom_dir_exists:
        omz_custom_plugins_dir_cmd = "mkdir -p ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
        try:
            system_utils.run_command(
                omz_custom_plugins_dir_cmd, run_as_user=target_user, shell=True,
                logger=app_logger, print_fn_info=con.print_info, print_fn_error=con.print_error
            )
            app_logger.info(f"Ensured OMZ custom plugins subdirectory exists using: {omz_custom_plugins_dir_cmd}")
        except Exception:
            con.print_warning("Could not create Oh My Zsh custom plugins subdirectory. Plugin installations will likely fail.")
            app_logger.warning("Failed to create OMZ custom plugins subdirectory.", exc_info=True)
            overall_success = False 

        if overall_success: 
            for item_name, command_str in phase3_config_commands.items():
                # ... (Plugin installation loop - remains the same)
                app_logger.debug(f"Processing enhancement item: {item_name}, command: {command_str}")
                if not isinstance(command_str, str) or not command_str.strip():
                    con.print_warning(f"Skipping invalid command for item '{item_name}' (not a string or empty).")
                    app_logger.warning(f"Invalid command for '{item_name}'.")
                    continue
                
                con.print_sub_step(f"Processing: {item_name}")
                
                if "ZSH_CUSTOM:~" in command_str: 
                    con.print_warning(f"Warning for '{item_name}': Command uses 'ZSH_CUSTOM:~'. Standard is 'ZSH_CUSTOM:-'. Ensure correct variable expansion.")
                if item_name == "zsh-eza" and "plugins/you-should-use" in command_str: 
                    con.print_warning(f"Warning for 'zsh-eza': Command might have an incorrect target directory '.../plugins/you-should-use'. Expected '.../plugins/zsh-eza'. Verify config.")

                is_git_clone_cmd = "git clone" in command_str.lower()
                should_skip_due_to_existence = False
                if is_git_clone_cmd:
                    try:
                        cmd_parts = shlex.split(command_str)
                        target_dir_in_cmd_unexpanded = ""
                        if len(cmd_parts) > 0: 
                            clone_idx = -1
                            try: clone_idx = cmd_parts.index("clone")
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
                                app_logger.debug(f"Checking plugin existence with command: {check_dir_exists_cmd}")
                                proc = system_utils.run_command(
                                    check_dir_exists_cmd, run_as_user=target_user, shell=True, 
                                    capture_output=True, check=False, print_fn_info=None, logger=app_logger
                                )
                                if proc.returncode == 0: 
                                    con.print_info(f"Destination for '{item_name}' ('{expanded_target_dir_str}') seems to exist. Skipping git clone.")
                                    app_logger.info(f"Git clone for '{item_name}' skipped, dir '{expanded_target_dir_str}' likely exists.")
                                    should_skip_due_to_existence = True
                                elif proc.returncode != 1: 
                                    con.print_warning(f"Could not reliably check existence for '{item_name}' (test cmd error {proc.returncode}). Will attempt command.")
                                    app_logger.warning(f"test -d for '{item_name}' (target: {expanded_target_dir_str}) errored: {proc.stderr.strip() if proc.stderr else 'N/A'}")
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
                        ("destination path" in e_cmd.stderr.lower() and "already exists" in e_cmd.stderr.lower())):
                        con.print_info(f"Git clone for '{item_name}' reported destination exists (stderr). Considered skipped.")
                        app_logger.info(f"Git clone for '{item_name}' skipped (error 128, dir exists based on stderr).")
                    else: 
                        app_logger.error(f"Failed applying enhancement '{item_name}'. Exit: {e_cmd.returncode}, Stderr: {e_cmd.stderr.strip() if e_cmd.stderr else 'N/A'}", exc_info=False)
                        overall_success = False # Mark as error for this specific plugin
                except Exception as e_cmd_unexpected: 
                    con.print_error(f"Unexpected error applying '{item_name}': {e_cmd_unexpected}")
                    app_logger.error(f"Unexpected error for '{item_name}': {e_cmd_unexpected}", exc_info=True)
                    overall_success = False # Mark as error
    elif not (omz_base_dir_exists and omz_custom_dir_exists) : # If OMZ base or custom dir is missing
        con.print_warning("Oh My Zsh base or custom directory not found/verified. Skipping OMZ plugin configuration.")
        app_logger.warning("OMZ base or custom directory not found/verified. Skipping plugin config.")


    # --- Dotfile Copying (always attempted if user wanted enhancements) ---
    project_root = Path(__file__).resolve().parent.parent
    if user_wants_to_proceed_with_enhancements: # This was the initial gate for Zsh stuff
        # Copy .zshrc if Zsh is installed and is_zsh_default is true (or was made true)
        if zsh_path and is_zsh_default: 
            if not _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root):
                con.print_warning("Failed to copy .zshrc. Your Zsh terminal might not use the custom configuration.")
                app_logger.warning("Failed to copy .zshrc")
                overall_success = False # Custom .zshrc is important
        elif zsh_path: # Zsh installed but not default, but user wanted enhancements. Copy .zshrc anyway.
            con.print_info("Zsh is installed but might not be default. .zshrc will be copied as enhancements were requested.")
            if not _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root):
                overall_success = False
    
    # Always attempt to copy .nanorc if home directory is valid
    if not _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root):
        con.print_warning("Failed to copy .nanorc.")
        app_logger.warning("Failed to copy .nanorc")
        # overall_success = False # Nanorc is less critical than .zshrc for terminal *enhancements*
                
    if overall_success:
        con.print_success("Phase 3: Terminal Enhancement completed.")
        app_logger.info("Phase 3 completed successfully.")
    else:
        con.print_error("Phase 3: Terminal Enhancement completed with errors. Please review the output and logs.")
        app_logger.error("Phase 3 completed with errors.")
    
    return overall_success