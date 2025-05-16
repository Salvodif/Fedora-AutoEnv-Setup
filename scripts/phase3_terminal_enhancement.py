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
from scripts import system_utils

# --- Helper Functions ---

def _get_target_user() -> Optional[str]:
    """Determines the target user, typically from SUDO_USER when script is run as root."""
    if os.geteuid() == 0: # Script is running as root
        target_user = os.environ.get("SUDO_USER")
        if not target_user:
            con.print_error(
                "Script is running as root, but SUDO_USER environment variable is not set. "
                "Cannot determine the target user for Zsh configuration."
            )
            con.print_info("Tip: Run 'sudo ./install.py' from a regular user account.")
            return None
        try:
            # Verify user exists
            system_utils.run_command(["id", "-u", target_user], capture_output=True, check=True, print_fn_info=con.print_info)
        except (subprocess.CalledProcessError, FileNotFoundError):
            con.print_error(f"The user '{target_user}' (from SUDO_USER) does not appear to be a valid system user.")
            return None
        return target_user
    else: 
        # If not root, assume current user is the target.
        # Warn that some operations (like changing shell for another user) will fail.
        current_user = os.getlogin()
        con.print_warning(
            f"Script is not running as root. Terminal enhancements will target the current user ({current_user}). "
            "Changing the default shell might fail or only apply if you are this user and have permissions."
        )
        return current_user

def _get_user_shell(username: str) -> Optional[str]:
    """Gets the current login shell for a specified user using getent."""
    try:
        process = system_utils.run_command(
            ["getent", "passwd", username], 
            capture_output=True, 
            check=True, # Ensure the command succeeds and user exists
            print_fn_info=con.print_info # Minimal logging for this utility call
        )
        # passwd entry format: name:password:UID:GID:GECOS:home_directory:shell
        shell_path = process.stdout.strip().split(":")[-1]
        if not shell_path: # Should not happen if getent succeeds for a valid user
            con.print_warning(f"Could not determine shell for user '{username}' from getent output.")
            return None
        return shell_path
    except subprocess.CalledProcessError:
        # User not found by getent or other error
        con.print_warning(f"Could not find user '{username}' via getent to determine shell.")
        return None
    except Exception as e: 
        con.print_warning(f"Could not determine the current shell for user '{username}': {e}")
        return None

def _check_zsh_installed() -> Optional[str]:
    """
    Checks if Zsh is installed and returns its path. 
    Prefers common paths like /usr/bin/zsh or /bin/zsh.
    """
    common_paths = ["/usr/bin/zsh", "/bin/zsh"] # Most typical locations
    for zsh_path_str in common_paths:
        zsh_path_obj = Path(zsh_path_str)
        if zsh_path_obj.is_file() and os.access(zsh_path_obj, os.X_OK):
            con.print_info(f"Zsh found at standard location: {zsh_path_str}")
            return zsh_path_str
            
    # Fallback to shutil.which if not in common paths
    zsh_path_which = shutil.which("zsh")
    if zsh_path_which:
        con.print_warning(f"Zsh found via 'which' at non-standard location: {zsh_path_which}.")
        con.print_info("Standard paths like /usr/bin/zsh or /bin/zsh are generally preferred for /etc/shells compatibility.")
        return zsh_path_which
        
    con.print_error("Zsh is not installed or not found in PATH. Please ensure Zsh is installed (e.g., via Phase 2).")
    return None

def _ensure_shell_in_etc_shells(shell_path: str) -> bool:
    """
    Ensures the given shell_path is listed in /etc/shells. 
    Requires root privileges to modify /etc/shells.
    """
    if not shell_path: # Should not happen if _check_zsh_installed found something
        con.print_error("Cannot ensure empty shell path in /etc/shells.")
        return False

    # This function must run with effective root privileges to modify /etc/shells
    if os.geteuid() != 0:
        con.print_warning("Cannot modify /etc/shells without root privileges. Shell validity check for /etc/shells skipped.")
        # We'll let chsh attempt it; it will warn if the shell isn't listed.
        return True # Assume it's fine, or let chsh handle the warning/error.

    etc_shells_path = Path("/etc/shells")
    try:
        if not etc_shells_path.is_file():
            con.print_warning(f"File {etc_shells_path} not found. Cannot verify or add shell path.")
            # This is unusual. chsh will likely fail if /etc/shells is missing.
            return False 

        # Read existing shells, ignoring comments and empty lines
        current_shells = []
        with open(etc_shells_path, 'r', encoding='utf-8') as f:
            current_shells = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        if shell_path in current_shells:
            con.print_info(f"Shell '{shell_path}' is already listed in {etc_shells_path}.")
            return True
        
        con.print_info(f"Shell '{shell_path}' not found in {etc_shells_path}. Attempting to add it...")
        
        # Make a backup of /etc/shells before modifying
        # Using system_utils.run_command for sudo operations.
        # No sudo needed in command list if script is already root.
        backup_etc_shells_path = f"{str(etc_shells_path)}.bak_{int(time.time())}"
        system_utils.run_command(
            ["cp", "-pf", str(etc_shells_path), backup_etc_shells_path],
            print_fn_info=con.print_info, print_fn_error=con.print_error
        )

        # Append the shell path. Using tee -a is robust.
        # Need to ensure the echo command correctly handles the shell_path string.
        append_cmd_str = f"echo {shlex.quote(shell_path)} | tee -a {shlex.quote(str(etc_shells_path))} > /dev/null"
        system_utils.run_command(
            append_cmd_str,
            shell=True, # Necessary for the pipe and redirection
            check=True, # Fail if tee or echo fails
            print_fn_info=con.print_info,
            print_fn_error=con.print_error
        )
        con.print_success(f"Successfully added '{shell_path}' to {etc_shells_path}.")
        return True
    except Exception as e:
        con.print_error(f"Failed to process /etc/shells for '{shell_path}': {e}")
        return False


def _set_default_shell(username: str, shell_path: str) -> bool:
    """Sets the default login shell for the user. Requires root privileges."""
    current_shell = _get_user_shell(username)
    if current_shell == shell_path:
        con.print_info(f"Shell '{shell_path}' is already the default shell for user '{username}'.")
        return True

    con.print_sub_step(f"Setting Zsh ('{shell_path}') as default shell for user '{username}'...")
    
    # This operation requires root privileges.
    if os.geteuid() != 0:
        con.print_error(f"Cannot change shell for user '{username}'. This script part must be run as root (e.g., with sudo).")
        return False

    # Ensure the shell is listed in /etc/shells before calling chsh
    if not _ensure_shell_in_etc_shells(shell_path):
        con.print_warning(f"Could not ensure '{shell_path}' is in /etc/shells. `chsh` might warn or fail.")
        # We'll proceed and let chsh attempt it. If _ensure_shell_in_etc_shells returned False due to error,
        # it's better to halt, but if it returned False because it couldn't find /etc/shells, it's a system issue.
        # For now, let's make it a prerequisite for chsh attempt.
        if not Path("/etc/shells").is_file(): # If /etc/shells itself is missing.
             return False

    if not con.confirm_action(f"Change default shell for user '{username}' to '{shell_path}'?", default=True):
        con.print_warning("Shell change skipped by user.")
        return True # User skipped, not a script failure

    try:
        # chsh command itself doesn't need 'sudo' prefix if this script is already run with sudo.
        system_utils.run_command(
            ["chsh", "-s", shell_path, username],
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error
            # check=True is default in run_command and will raise CalledProcessError if chsh fails
        )
        # chsh typically prints "Shell changed." to STDOUT on success or warnings to STDERR.
        # These are captured and logged by system_utils.run_command if capture_output=True.
        # For this command, we might not need to capture output if we trust chsh's exit code.

        # Verification attempt after chsh
        time.sleep(0.5) # Brief pause for system to potentially update caches (e.g., nscd if running)
        new_shell_check = _get_user_shell(username)
        
        if new_shell_check == shell_path:
            con.print_success(f"Successfully set Zsh as the default shell for '{username}'.")
            con.print_info("Note: The shell change will take effect upon the user's next login.")
        else:
            # This might happen if getent output is cached or system hasn't fully processed the change yet.
            # chsh usually exits 0 on success, even if it printed warnings (like shell not in /etc/shells).
            con.print_warning(f"chsh command executed to set shell to '{shell_path}' for '{username}'.")
            con.print_warning(f"Verification via getent currently shows shell as: '{new_shell_check or 'unknown'}'.")
            con.print_info("Please verify the shell after the user's next login. The change likely succeeded if chsh reported no fatal errors.")
        
        return True # Consider chsh command execution success as script success for this step.
                     # The user is informed about the need to re-login.
    except subprocess.CalledProcessError as e:
        # system_utils.run_command already prints detailed error from CalledProcessError.
        con.print_error(f"The 'chsh' command failed to set shell for '{username}'. Exit code: {e.returncode}")
        return False
    except Exception as e: 
        # Catch other unexpected errors, e.g., if 'chsh' command itself is not found (FileNotFoundError).
        con.print_error(f"An unexpected error occurred while trying to set default shell for '{username}': {e}")
        return False


def _get_user_home(username: str) -> Optional[Path]:
    """Gets the home directory of a specified user."""
    try:
        proc = system_utils.run_command(
            ["getent", "passwd", username], capture_output=True, check=True,
            print_fn_info=con.print_info # Minimal logging for this utility call
        )
        home_dir_str = proc.stdout.strip().split(":")[5]
        if not home_dir_str:
            con.print_error(f"Could not determine home directory for user '{username}'.")
            return None
        return Path(home_dir_str)
    except Exception as e:
        con.print_error(f"Error getting home directory for user '{username}': {e}")
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

    if not source_file_path.is_file():
        con.print_warning(f"Source configuration file '{source_file_path}' not found. Skipping copy.")
        return False 

    con.print_sub_step(f"Copying '{source_filename}' to {target_user}'s home directory ({target_file_path})...")

    backup_command_str = ""
    try:
        # Check if target file exists as the user
        target_exists_as_user = False
        if os.geteuid() == 0 : # if script is root, test as target_user
             test_exists_proc = system_utils.run_command(
                f"test -f {shlex.quote(str(target_file_path))}",
                run_as_user=target_user, shell=True, check=False, capture_output=True,
                print_fn_info=con.print_info # Minimal logging for this check
            )
             if test_exists_proc.returncode == 0:
                 target_exists_as_user = True
        elif target_file_path.exists(): # if not root, check as current user (who should be target_user)
            target_exists_as_user = True


        if target_exists_as_user:
            # Using a more unique timestamp for backup
            timestamp_str = f"backup_{int(time.time())}_{Path.cwd().name.replace(' ','_')}"
            backup_target_path = target_user_home / f"{source_filename}.{timestamp_str}"
            # For simplicity, assume timestamp makes it unique enough for one run.
            # If multiple backups in quick succession are needed, a counter could be re-added.
            
            backup_command_str = f"cp -pf {shlex.quote(str(target_file_path))} {shlex.quote(str(backup_target_path))}"
            con.print_info(f"Existing '{target_file_path.name}' found. Will attempt to back it up to '{backup_target_path.name}'.")
        else:
            con.print_info(f"No existing '{target_file_path.name}' found in {target_user}'s home. No backup needed.")
    except Exception as e_check:
        con.print_warning(f"Could not check for existing '{target_file_path.name}' for backup: {e_check}. Proceeding with copy.")

    try:
        # Command to copy the file, executed as the target user to set correct ownership.
        copy_command_str = f"cp -f {shlex.quote(str(source_file_path))} {shlex.quote(str(target_file_path))}"
        
        full_command_for_user = copy_command_str
        if backup_command_str:
            # Ensure backup runs first, then copy
            full_command_for_user = f"{backup_command_str} && {copy_command_str}"
            
        system_utils.run_command(
            full_command_for_user,
            run_as_user=target_user,
            shell=True, # For `&&` if backup is included
            print_fn_info=con.print_info,
            print_fn_error=con.print_error
        )
        con.print_success(f"Successfully copied '{source_filename}' to {target_user_home}.")
        return True
    except Exception: # Error already logged by run_command
        con.print_error(f"Failed to copy '{source_filename}' to {target_user_home}.")
        return False

# --- Main Phase Function ---

def run_phase3(app_config: dict) -> bool:
    """Executes Phase 3: Terminal Enhancement."""
    con.print_step("PHASE 3: Terminal Enhancement")
    overall_success = True

    target_user = _get_target_user()
    if not target_user:
        return False # Critical: cannot determine user for this phase

    target_user_home = _get_user_home(target_user)
    if not target_user_home:
        # Not necessarily critical for plugin installs if $HOME is used in commands,
        # but config file copy will fail.
        con.print_warning(f"Cannot determine home directory for target user '{target_user}'. Config file copy will be skipped.")
        # If config files are essential, set overall_success = False here or later.

    con.print_info(f"Running terminal enhancements for user: [bold cyan]{target_user}[/bold cyan]")

    # 1. Check Zsh installation and attempt to set as default shell
    zsh_path = _check_zsh_installed()
    if not zsh_path:
        con.print_error("Zsh is not found. Cannot proceed with Zsh-specific enhancements.")
        return False # Zsh is critical for this phase's primary purpose.
    
    if not _set_default_shell(target_user, zsh_path):
        overall_success = False 
        # If setting default shell fails, it's a significant issue for user experience.
        con.print_error("Failed to set Zsh as the default shell. Terminal experience might not be as intended.")
        # Depending on strictness, you might 'return False' here if default shell is mandatory.

    # 2. Apply terminal enhancement commands (plugins, tools) from YAML
    phase3_config: Optional[Dict[str,str]] = config_loader.get_phase_data(app_config, "phase3_terminal_enhancement")
    if not phase3_config:
        con.print_info("No terminal enhancement commands found in 'phase3_terminal_enhancement' (YAML). Skipping plugin/tool installations.")
    else:
        con.print_info(f"\nApplying terminal enhancement commands for user '{target_user}'...")
        
        # Ensure the base custom plugins directory exists.
        # Using $HOME explicitly in the command string is robust for `sudo -u ... bash -c` context.
        omz_custom_plugins_dir_cmd = "mkdir -p ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
        try:
            system_utils.run_command(
                omz_custom_plugins_dir_cmd, run_as_user=target_user, shell=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error
            )
            # No explicit success message here, mkdir -p is idempotent and usually silent on success.
        except Exception: 
            # Error already logged by run_command
            con.print_warning(f"Could not ensure Oh My Zsh custom plugins directory for '{target_user}'. Plugin installs relying on it might fail.")

        for item_name, command_str in phase3_config.items():
            if not isinstance(command_str, str) or not command_str.strip():
                con.print_warning(f"Skipping invalid command for item '{item_name}': Command is not a valid string or is empty.")
                continue
            
            con.print_sub_step(f"Processing enhancement: {item_name}")
            
            # YAML sanity checks (can be expanded)
            if "ZSH_CUSTOM:~" in command_str: 
                con.print_warning(f"Warning for '{item_name}': Command uses 'ZSH_CUSTOM:~'. Standard is 'ZSH_CUSTOM:-'. Please verify YAML (e.g., use '$HOME' in default path for robustness).")
            # Example: Check for common typo in zsh-eza target path
            if item_name == "zsh-eza" and "plugins/you-should-use" in command_str:
                 con.print_warning(f"Warning for 'zsh-eza': Command might have an incorrect target directory '.../plugins/you-should-use'. Expected '.../plugins/zsh-eza'. Please verify YAML.")


            is_git_clone_cmd = "git clone" in command_str.lower() # More general check
            should_skip_command_due_to_existence = False

            if is_git_clone_cmd:
                cmd_parts = shlex.split(command_str) 
                target_dir_in_cmd = ""
                if len(cmd_parts) > 0:
                    try:
                        git_idx = cmd_parts.index("git")
                        clone_idx = cmd_parts.index("clone", git_idx)
                        if len(cmd_parts) > clone_idx + 2: # url is cmd_parts[clone_idx + 1], target_dir is cmd_parts[clone_idx + 2]
                             target_dir_in_cmd = cmd_parts[clone_idx + 2]
                    except ValueError: # 'git' or 'clone' not found as expected
                        pass 

                if target_dir_in_cmd:
                    # target_dir_in_cmd from YAML (e.g., "${ZSH_CUSTOM:-$HOME/...}/plugin_name")
                    # will be expanded by the shell when `bash -c` runs the `test -d` command.
                    check_dir_exists_cmd = f"test -d {target_dir_in_cmd}" 
                    
                    try:
                        proc = system_utils.run_command(
                            check_dir_exists_cmd,
                            run_as_user=target_user,
                            shell=True, 
                            capture_output=True,
                            check=False, # Allow non-zero exit for "not found"
                            print_fn_info=con.print_info # Minimal logging for this check
                        )
                        if proc.returncode == 0: # Directory exists
                            con.print_info(f"Destination for '{item_name}' ('{target_dir_in_cmd}') seems to exist. Skipping git clone.")
                            should_skip_command_due_to_existence = True
                        elif proc.returncode == 1: # Directory does not exist (expected for new clone)
                            pass # Proceed with clone
                        else: # test command itself had an error (e.g., bad permissions on parent of target_dir_in_cmd)
                             con.print_warning(f"Command '{check_dir_exists_cmd}' for '{item_name}' failed with unexpected exit code {proc.returncode}. Will attempt clone anyway.")
                             if proc.stderr: con.print_warning(f"Stderr from 'test -d' command: {proc.stderr.strip()}")

                    except Exception as e_check: 
                        con.print_warning(f"Could not verify existence for '{item_name}' due to an exception: {e_check}. Will attempt command.")
                else:
                    con.print_warning(f"Could not reliably determine target directory for '{item_name}' from command '{command_str}'. Will attempt command without existence check.")
            
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
                    print_fn_sub_step=con.print_sub_step
                )
                con.print_success(f"Enhancement '{item_name}' applied successfully.")
            except subprocess.CalledProcessError as e: 
                if is_git_clone_cmd and e.returncode == 128 and e.stderr and "already exists and is not an empty directory" in e.stderr.lower():
                    con.print_info(f"Clone for '{item_name}' failed because destination likely already exists and is not empty (git reported). Considered skipped/existing.")
                else:
                    # system_utils.run_command already prints detailed errors.
                    con.print_error(f"Failed to apply enhancement '{item_name}'. Review errors logged above.")
                    overall_success = False
            except Exception as e_cmd: 
                con.print_error(f"An unexpected error occurred while applying enhancement '{item_name}': {e_cmd}")
                overall_success = False

    # 3. Copy custom .zshrc and .nanorc if user home is known
    if target_user_home:
        con.print_info(f"\nCopying custom configuration files for user '{target_user}'...")
        project_root = Path(__file__).resolve().parent.parent 
        
        if not _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root):
            con.print_warning("Failed to copy .zshrc. User's Zsh experience might not be as intended.")
            # overall_success = False # Decide if this makes the whole phase fail based on importance

        if not _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root):
            con.print_warning("Failed to copy .nanorc.")
            # overall_success = False # Decide if this makes the whole phase fail
    else:
        con.print_warning("Skipping copy of .zshrc and .nanorc because target user's home directory could not be determined.")
                
    if overall_success:
        con.print_success("Phase 3: Terminal Enhancement completed successfully.")
    else:
        con.print_error("Phase 3: Terminal Enhancement completed with errors. Please review the output.")
    
    return overall_success