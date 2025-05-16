# Fedora-AutoEnv-Setup/scripts/phase3_terminal_enhancement.py

import subprocess 
import sys
import os
import shutil
import shlex 
from pathlib import Path
from typing import Optional, Dict 

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils

# ... (_get_target_user, _get_user_shell, _check_zsh_installed, _set_default_shell, _get_user_home, _copy_config_file_to_user_home remain the same) ...

def run_phase3(app_config: dict) -> bool:
    """Executes Phase 3: Terminal Enhancement."""
    con.print_step("PHASE 3: Terminal Enhancement")
    overall_success = True

    target_user = _get_target_user()
    if not target_user:
        return False 

    target_user_home = _get_user_home(target_user)
    if not target_user_home:
        con.print_error(f"Cannot determine home directory for target user '{target_user}'. Config file copy will be skipped.")
        # Not necessarily a critical failure for plugin installs if $HOME is used in commands.

    con.print_info(f"Running terminal enhancements for user: [bold cyan]{target_user}[/bold cyan]")

    zsh_path = _check_zsh_installed()
    if not zsh_path:
        con.print_error("Cannot proceed with Zsh enhancements because Zsh is not found.")
        return False 
    
    if not _set_default_shell(target_user, zsh_path):
        overall_success = False 

    phase3_config: Optional[Dict[str,str]] = config_loader.get_phase_data(app_config, "phase3_terminal_enhancement")
    if not phase3_config:
        con.print_info("No terminal enhancement commands found in 'phase3_terminal_enhancement' (YAML). Skipping plugin/tool installations.")
    else:
        con.print_info(f"\nApplying terminal enhancement commands for user '{target_user}'...")
        
        # Ensure the base custom plugins directory exists.
        # Use $HOME explicitly for robustness in `sudo -u ... bash -c` context.
        omz_custom_plugins_dir_cmd = "mkdir -p ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins"
        try:
            system_utils.run_command(
                omz_custom_plugins_dir_cmd, run_as_user=target_user, shell=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error # Use sub_step for less noise
            )
            # No explicit success message here, mkdir -p is idempotent.
        except Exception: 
            con.print_warning(f"Could not ensure Oh My Zsh custom plugins directory for '{target_user}'. Plugin installs might fail if they rely on specific subdirectories being pre-created by this step (though most git clone commands create the final dir).")

        for item_name, command_str in phase3_config.items():
            if not isinstance(command_str, str) or not command_str.strip():
                con.print_warning(f"Skipping invalid command for item '{item_name}': Command is not a valid string.")
                continue
            
            con.print_sub_step(f"Processing enhancement: {item_name}")
            
            # Check for common YAML issues (can be expanded)
            if "ZSH_CUSTOM:~" in command_str: 
                con.print_warning(f"Warning: Command for '{item_name}' uses 'ZSH_CUSTOM:~'. Standard is 'ZSH_CUSTOM:-'. Please verify YAML for robustness (e.g., use '$HOME' in default path).")
            if item_name == "zsh-eza" and "plugins/you-should-use" in command_str:
                 con.print_warning(f"Warning: Command for 'zsh-eza' might have an incorrect target directory '.../plugins/you-should-use'. Expected '.../plugins/zsh-eza'. Please verify YAML.")


            is_git_clone_cmd = "git clone" in command_str.lower() # More general check
            should_skip_command_due_to_existence = False

            if is_git_clone_cmd:
                # Attempt to parse the target directory from the git clone command
                # This is a basic parsing, assumes "git clone <url> <target_dir>"
                cmd_parts = shlex.split(command_str) # Use shlex to handle quoted paths if any
                target_dir_in_cmd = ""
                if len(cmd_parts) > 0:
                    try:
                        # Find 'git', then 'clone', then the next two args are url and target_dir
                        git_idx = cmd_parts.index("git")
                        clone_idx = cmd_parts.index("clone", git_idx)
                        if len(cmd_parts) > clone_idx + 2:
                             target_dir_in_cmd = cmd_parts[clone_idx + 2]
                    except ValueError:
                        pass # 'git' or 'clone' not found as expected

                if target_dir_in_cmd:
                    # The target_dir_in_cmd from YAML (e.g., "${ZSH_CUSTOM:-$HOME/...}/plugin_name")
                    # will be expanded by the shell when `bash -c` runs the `test -d` command.
                    check_dir_exists_cmd = f"test -d {target_dir_in_cmd}" # No need to shlex.quote here as it's part of the bash -c string
                    
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
                        else: # test command itself had an error
                             con.print_warning(f"Command '{check_dir_exists_cmd}' for '{item_name}' failed with unexpected exit code {proc.returncode}. Will attempt clone anyway.")
                             if proc.stderr: con.print_warning(f"Stderr from test: {proc.stderr.strip()}")

                    except Exception as e_check: 
                        con.print_warning(f"Could not verify existence for '{item_name}' due to an exception: {e_check}. Will attempt command.")
                else:
                    con.print_warning(f"Could not reliably determine target directory for '{item_name}' from command '{command_str}'. Will attempt command without existence check.")

            
            if should_skip_command_due_to_existence:
                # If we skipped due to existence, we can mark it as a "soft success" or just move on.
                # For now, if it exists, we assume it's correctly installed from a previous run.
                con.print_info(f"Skipped applying '{item_name}' as target seems to exist.")
                continue

            try:
                system_utils.run_command(
                    command_str, # This is the full command string from YAML
                    run_as_user=target_user,
                    shell=True, # Crucial for variable expansion and pipes in commands
                    capture_output=True,
                    check=True, # Let it raise error on failure of the actual command
                    print_fn_info=con.print_info, # Full command shown by run_command
                    print_fn_error=con.print_error,
                    print_fn_sub_step=con.print_sub_step
                )
                con.print_success(f"Enhancement '{item_name}' applied successfully.")
            except subprocess.CalledProcessError as e: 
                # run_command already prints detailed errors from CalledProcessError
                # We can add context here.
                # Git clone often returns 128 if path already exists and is not an empty dir.
                if is_git_clone_cmd and e.returncode == 128 and e.stderr and "already exists and is not an empty directory" in e.stderr.lower():
                    con.print_info(f"Clone for '{item_name}' failed because destination likely already exists and is not empty (git reported). Consider it skipped/existing.")
                else:
                    con.print_error(f"Failed to apply enhancement '{item_name}'. Review errors above.")
                    overall_success = False
            except Exception as e_cmd: # Other exceptions from run_command (e.g., FileNotFoundError for a command in the string)
                con.print_error(f"An unexpected error occurred while applying enhancement '{item_name}': {e_cmd}")
                overall_success = False

    # 3. Copy custom .zshrc and .nanorc if user home is known
    if target_user_home:
        con.print_info(f"\nCopying custom configuration files for user '{target_user}'...")
        project_root = Path(__file__).resolve().parent.parent 
        
        if not _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root):
            con.print_warning("Failed to copy .zshrc. User's Zsh experience might not be as intended.")
            # overall_success = False # Decide if this makes the whole phase fail

        if not _copy_config_file_to_user_home(".nanorc", "nano", target_user, target_user_home, project_root):
            con.print_warning("Failed to copy .nanorc.")
            # overall_success = False 
    else:
        con.print_warning("Skipping copy of .zshrc and .nanorc because target user's home directory could not be determined.")
                
    if overall_success:
        con.print_success("Phase 3: Terminal Enhancement completed successfully.")
    else:
        con.print_error("Phase 3: Terminal Enhancement completed with errors. Please review the output.")
    
    return overall_success

# ... (_get_target_user, _get_user_shell, _check_zsh_installed, _set_default_shell, _get_user_home, _copy_config_file_to_user_home functions from previous versions)
# Make sure these helper functions are included in the actual file. For brevity, I'm not repeating them here.
# The helper functions _get_target_user, _get_user_shell, etc. are essential.
# I'll paste them here just to ensure the file is complete for you.

def _get_target_user() -> Optional[str]:
    if os.geteuid() == 0: 
        target_user = os.environ.get("SUDO_USER")
        if not target_user:
            con.print_error("Script is running as root, but SUDO_USER is not set. Cannot determine target user.")
            return None
        try:
            system_utils.run_command(["id", "-u", target_user], capture_output=True, check=True, print_fn_info=con.print_info)
        except (subprocess.CalledProcessError, FileNotFoundError):
            con.print_error(f"User '{target_user}' (from SUDO_USER) does not appear to be a valid system user.")
            return None
        return target_user
    else: 
        con.print_warning("Script is not running as root. Terminal enhancements will target current user. Some actions like changing shell might fail.")
        return os.getlogin()

def _get_user_shell(username: str) -> Optional[str]:
    try:
        process = system_utils.run_command(
            ["getent", "passwd", username], capture_output=True, check=True, print_fn_info=con.print_info
        )
        return process.stdout.strip().split(":")[-1]
    except Exception: 
        con.print_warning(f"Could not determine current shell for user '{username}'.")
        return None

def _check_zsh_installed() -> Optional[str]:
    zsh_path = shutil.which("zsh")
    if not zsh_path:
        con.print_error("Zsh is not installed or not found in PATH. Please ensure Zsh is installed.")
        return None
    con.print_info(f"Zsh found at: {zsh_path}")
    return zsh_path

def _set_default_shell(username: str, shell_path: str) -> bool:
    current_shell = _get_user_shell(username)
    if current_shell == shell_path:
        con.print_info(f"Zsh ('{shell_path}') is already the default shell for user '{username}'.")
        return True

    con.print_sub_step(f"Setting Zsh ('{shell_path}') as default shell for user '{username}'...")
    if not con.confirm_action(f"Change default shell for user '{username}' to '{shell_path}'?", default=True):
        con.print_warning("Shell change skipped by user.")
        return True 

    if os.geteuid() != 0:
        con.print_error(f"Cannot change shell for user '{username}'. This script must be run as root (e.g., with sudo) to change user shells.")
        return False

    try:
        system_utils.run_command(
            ["chsh", "-s", shell_path, username], # No sudo needed here as script is already root
            print_fn_info=con.print_info, print_fn_error=con.print_error
        )
        # Verify by re-checking (getent output might be cached or take a moment to update)
        # For immediate check, this might not reflect, but it's the best we can do without login/logout
        time.sleep(1) # Brief pause
        new_shell_check = _get_user_shell(username)
        if new_shell_check == shell_path:
            con.print_success(f"Successfully set Zsh as the default shell for '{username}'.")
            con.print_info("Note: The shell change will take effect upon the user's next login.")
            return True
        else:
            # This might occur if /etc/passwd hasn't updated immediately for getent.
            con.print_warning(f"Attempted to set Zsh as default shell for '{username}'. chsh command executed. Please verify after next login. Current shell reported as: {new_shell_check or 'unknown'}")
            # Let's consider the chsh command success as script success here, as OS update can be slow.
            return True 
    except Exception as e:
        con.print_error(f"Failed to execute chsh command: {e}")
        return False


def _get_user_home(username: str) -> Optional[Path]:
    try:
        proc = system_utils.run_command(
            ["getent", "passwd", username], capture_output=True, check=True,
            print_fn_info=con.print_info
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
    source_file_path = project_root_dir / source_subdir / source_filename
    target_file_path = target_user_home / source_filename

    if not source_file_path.is_file():
        con.print_warning(f"Source configuration file '{source_file_path}' not found. Skipping copy.")
        return False 

    con.print_sub_step(f"Copying '{source_filename}' to {target_user}'s home directory ({target_file_path})...")

    backup_command_str = ""
    try:
        # Check if target file exists as the user
        # Use direct Python check if target_user_home is accessible by current euid,
        # or use a command if running as root and target_user_home might not be.
        # If script is sudo, target_user_home check might need to be as user.
        
        # Let's assume we can check existence directly if `target_user_home` path is known.
        # If not, use `run_command` as user.
        target_exists_as_user = False
        if os.geteuid() == 0 : # if root, test as target_user
             test_exists_proc = system_utils.run_command(
                f"test -f {shlex.quote(str(target_file_path))}",
                run_as_user=target_user, shell=True, check=False, capture_output=True,
                print_fn_info=con.print_info # Minimal logging
            )
             if test_exists_proc.returncode == 0:
                 target_exists_as_user = True
        elif target_file_path.exists(): # if not root, check as current user (who should be target_user)
            target_exists_as_user = True


        if target_exists_as_user:
            timestamp = Path.cwd().name # Simple timestamp from current dir name
            backup_target_path = target_user_home / f"{source_filename}.backup_{timestamp}"
            counter = 0
            # Ensure unique backup name if run multiple times from same dir
            unique_backup_path = backup_target_path
            while True:
                # Need to check existence of backup_target_path as the target_user
                backup_exists_check_cmd = f"test -e {shlex.quote(str(unique_backup_path))}"
                backup_exists_proc = system_utils.run_command(
                    backup_exists_check_cmd, run_as_user=target_user, shell=True,
                    check=False, capture_output=True, print_fn_info=con.print_info
                )
                if backup_exists_proc.returncode != 0: # Does not exist, unique name found
                    break
                counter += 1
                unique_backup_path = target_user_home / f"{source_filename}.backup_{timestamp}_{counter}"
            
            backup_target_path = unique_backup_path
            backup_command_str = f"cp -pf {shlex.quote(str(target_file_path))} {shlex.quote(str(backup_target_path))}"
            con.print_info(f"Existing '{target_file_path.name}' found. Will attempt to back it up to '{backup_target_path.name}'.")
        else:
            con.print_info(f"No existing '{target_file_path.name}' found in {target_user}'s home. No backup needed.")
    except Exception as e_check:
        con.print_warning(f"Could not check for existing '{target_file_path.name}' for backup: {e_check}. Proceeding with copy.")

    try:
        copy_command_str = f"cp -f {shlex.quote(str(source_file_path))} {shlex.quote(str(target_file_path))}"
        
        full_command_for_user = copy_command_str
        if backup_command_str:
            # Ensure backup runs first, then copy
            full_command_for_user = f"{backup_command_str} && {copy_command_str}"
            
        system_utils.run_command(
            full_command_for_user,
            run_as_user=target_user,
            shell=True, 
            print_fn_info=con.print_info,
            print_fn_error=con.print_error
        )
        # Chown to ensure correct ownership, especially if script is root and cp doesn't preserve it fully across users
        # when run via sudo -u. `sudo -u user cp` should handle ownership, but being explicit can help.
        # However, the `cp` itself is run as target_user, so this should be fine.
        # chown_command = f"chown {target_user}:{target_user} {shlex.quote(str(target_file_path))}"
        # system_utils.run_command(chown_command, run_as_user="root", shell=True) # This would need root if script isn't already root

        con.print_success(f"Successfully copied '{source_filename}' to {target_user_home}.")
        return True
    except Exception: 
        con.print_error(f"Failed to copy '{source_filename}' to {target_user_home}.")
        return False