# Fedora-AutoEnv-Setup/scripts/phase3_terminal_enhancement.py

import subprocess # Retained for CalledProcessError if system_utils re-raises
import sys
import os
import shutil
import shlex # For shlex.quote
from pathlib import Path
from typing import Optional, Dict 

# Adjust import path
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
            system_utils.run_command(["id", "-u", target_user], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            con.print_error(f"The user '{target_user}' (from SUDO_USER) does not appear to be a valid system user.")
            return None
        return target_user
    else: 
        con.print_warning(
            "Script is not running as root. "
            "Changing user shell will likely fail. Proceeding for current user for plugin installs."
        )
        return os.getlogin()

def _get_user_shell(username: str) -> Optional[str]:
    """Gets the current login shell for a specified user."""
    try:
        process = system_utils.run_command(
            ["getent", "passwd", username], capture_output=True,
            print_fn_info=con.print_info
        )
        return process.stdout.strip().split(":")[-1]
    except Exception: 
        con.print_warning(f"Could not determine the current shell for user '{username}'.")
        return None

def _check_zsh_installed() -> Optional[str]:
    """Checks if Zsh is installed and returns its path."""
    zsh_path = shutil.which("zsh")
    if not zsh_path:
        con.print_error("Zsh is not installed or not found in PATH. Please ensure Zsh is installed (e.g., via Phase 2).")
        return None
    con.print_info(f"Zsh found at: {zsh_path}")
    return zsh_path

def _set_default_shell(username: str, shell_path: str) -> bool:
    """Sets the default login shell for the user. Requires root privileges."""
    current_shell = _get_user_shell(username)
    if current_shell == shell_path:
        con.print_info(f"Zsh ('{shell_path}') is already the default shell for user '{username}'.")
        return True

    con.print_sub_step(f"Setting Zsh ('{shell_path}') as default shell for user '{username}'...")
    if not con.confirm_action(f"Change default shell for user '{username}' to '{shell_path}'?", default=True):
        con.print_warning("Shell change skipped by user.")
        return True 

    try:
        system_utils.run_command(
            ["chsh", "-s", shell_path, username],
            print_fn_info=con.print_info, print_fn_error=con.print_error
        )
        new_shell_check = _get_user_shell(username)
        if new_shell_check == shell_path:
            con.print_success(f"Successfully set Zsh as the default shell for '{username}'.")
            con.print_info("Note: The shell change will take effect upon the user's next login.")
            return True
        else:
            con.print_error(f"Failed to set Zsh as default shell for '{username}'. Current shell is: {new_shell_check or 'unknown'}")
            return False
    except Exception: 
        return False

def _get_user_home(username: str) -> Optional[Path]:
    """Gets the home directory of a specified user."""
    try:
        # Using getent is more reliable for home directory
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
    source_subdir: str, # e.g., "zsh" or "nano"
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
        return False # Or True if skipping is not an error for the overall phase. Treat as minor failure.

    con.print_sub_step(f"Copying '{source_filename}' to {target_user}'s home directory...")

    # Backup existing file in user's home, if any
    # This needs to be done as the target_user to access their home correctly for backup,
    # or as root if copying to root-owned locations (not the case here).
    # For simplicity, we'll use sudo -u <user> cp for backup if file exists.
    backup_command_str = ""
    try:
        # Check if target file exists as the user
        system_utils.run_command(
            f"test -f {shlex.quote(str(target_file_path))}",
            run_as_user=target_user, shell=True, check=True, capture_output=True,
            print_fn_info=con.print_info
        )
        # If above succeeds, file exists. Create backup command.
        timestamp = Path.cwd().name # Simple timestamp
        backup_target_path = target_user_home / f"{source_filename}.backup_{timestamp}"
        backup_command_str = f"cp -pf {shlex.quote(str(target_file_path))} {shlex.quote(str(backup_target_path))}"
        con.print_info(f"Existing '{target_file_path.name}' found. Will attempt to back it up to '{backup_target_path.name}'.")
    except subprocess.CalledProcessError:
        con.print_info(f"No existing '{target_file_path.name}' found in {target_user}'s home. No backup needed.")
    except Exception as e_check:
        con.print_warning(f"Could not check for existing '{target_file_path.name}' for backup: {e_check}. Proceeding with copy.")


    try:
        # Command to copy the file, executed as the target user to set correct ownership.
        # If backup command was prepared, prepend it.
        copy_command_str = f"cp -f {shlex.quote(str(source_file_path))} {shlex.quote(str(target_file_path))}"
        
        full_command_for_user = copy_command_str
        if backup_command_str:
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
        return False 

    target_user_home = _get_user_home(target_user)
    if not target_user_home:
        con.print_error(f"Cannot determine home directory for target user '{target_user}'. Aborting config file copy.")
        # Mark as overall failure if home dir is essential for subsequent steps.
        # For now, this only affects the config file copy part.
        # overall_success = False # Consider if this is critical

    con.print_info(f"Running terminal enhancements for user: [bold cyan]{target_user}[/bold cyan]")

    # 1. Check Zsh installation and attempt to set as default shell
    zsh_path = _check_zsh_installed()
    if not zsh_path:
        con.print_error("Cannot proceed with Zsh enhancements because Zsh is not found.")
        return False 
    
    if not _set_default_shell(target_user, zsh_path):
        overall_success = False 

    # 2. Apply terminal enhancement commands (plugins, tools) from YAML
    phase3_config: Optional[Dict[str,str]] = config_loader.get_phase_data(app_config, "phase3_terminal_enhancement")
    if not phase3_config:
        con.print_info("No terminal enhancement commands found in 'phase3_terminal_enhancement' (YAML). Skipping plugin/tool installations.")
    else:
        con.print_info(f"\nApplying terminal enhancement commands for user '{target_user}'...")
        default_omz_custom_plugins_dir_cmd = "mkdir -p ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins"
        try:
            system_utils.run_command(
                default_omz_custom_plugins_dir_cmd, run_as_user=target_user, shell=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
            )
            con.print_sub_step(f"Ensured default Oh My Zsh custom plugins directory structure exists for '{target_user}'.")
        except Exception: 
            con.print_warning(f"Could not ensure Oh My Zsh custom plugins directory for '{target_user}'. Commands relying on it might fail.")

        for item_name, command_str in phase3_config.items():
            # ... (plugin/tool installation logic as before) ...
            if not isinstance(command_str, str) or not command_str.strip():
                con.print_warning(f"Skipping invalid command for item '{item_name}': Command is not a valid string.")
                continue
            con.print_sub_step(f"Applying: {item_name}")
            is_git_clone_cmd = command_str.strip().lower().startswith("git clone")
            if is_git_clone_cmd:
                if "ZSH_CUSTOM:~" in command_str: 
                    con.print_warning(f"Command for '{item_name}' uses 'ZSH_CUSTOM:~'. Standard is 'ZSH_CUSTOM:-'.")
                if item_name == "zsh-eza" and "plugins/you-should-use" in command_str:
                     con.print_warning("Command for 'zsh-eza' might have incorrect target. Please verify YAML.")

            should_skip_command_due_to_existence = False
            if is_git_clone_cmd:
                parts = command_str.strip().split()
                if len(parts) >= 3:
                    target_dir_in_cmd = parts[-1] 
                    check_dir_exists_cmd = f"test -d {shlex.quote(target_dir_in_cmd)}"
                    try:
                        system_utils.run_command(
                            check_dir_exists_cmd, run_as_user=target_user, shell=True, 
                            capture_output=True, check=True, print_fn_info=con.print_info
                        )
                        con.print_info(f"Destination for '{item_name}' ('{target_dir_in_cmd}') seems to exist. Skipping command.")
                        should_skip_command_due_to_existence = True
                    except subprocess.CalledProcessError: pass 
                    except Exception as e_check: 
                        con.print_warning(f"Could not verify existence for '{item_name}': {e_check}. Will attempt command.")
            
            if should_skip_command_due_to_existence: continue

            try:
                system_utils.run_command(
                    command_str, run_as_user=target_user, shell=True, capture_output=True,
                    print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
                )
                con.print_success(f"Enhancement '{item_name}' applied successfully.")
            except subprocess.CalledProcessError as e: 
                if is_git_clone_cmd and e.returncode == 128 and e.stderr and "already exists and is not an empty directory" in e.stderr.lower():
                    con.print_info(f"Destination for '{item_name}' already exists (git reported). Skipped.")
                else:
                    con.print_error(f"Failed to apply enhancement '{item_name}'. Check logs.")
                    overall_success = False
            except Exception: 
                overall_success = False

    # 3. Copy custom .zshrc and .nanorc if user home is known
    if target_user_home:
        con.print_info(f"\nCopying custom configuration files for user '{target_user}'...")
        project_root = Path(__file__).resolve().parent.parent # Fedora-AutoEnv-Setup/
        
        # Copy .zshrc
        if not _copy_config_file_to_user_home(".zshrc", "zsh", target_user, target_user_home, project_root):
            # Not necessarily a critical failure for the whole phase, but a failure for this part.
            con.print_warning("Failed to copy .zshrc. User's Zsh experience might not be as intended.")
            # overall_success = False # Decide if this makes the whole phase fail

        # Copy .nanorc
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