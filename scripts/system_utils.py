# Fedora-AutoEnv-Setup/scripts/system_utils.py

import subprocess
import os
import shlex
import sys
import time # Added for backup_system_file
from pathlib import Path
from typing import List, Optional, Union, Dict, Callable
import logging

try:
    from scripts.logger_utils import app_logger as default_script_logger
except ImportError:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    default_script_logger = logging.getLogger("system_utils_fallback")
    default_script_logger.info("Default fallback logger initialized for system_utils.")

PRINT_FN_INFO_DEFAULT: Callable[[str], None] = lambda msg: print(f"INFO: {msg}")
PRINT_FN_ERROR_DEFAULT: Callable[[str], None] = lambda msg: print(f"ERROR: {msg}", file=sys.stderr)
PRINT_FN_SUB_STEP_DEFAULT: Callable[[str], None] = lambda msg: print(f"  SUB: {msg}")
PRINT_FN_WARNING_DEFAULT: Callable[[str], None] = lambda msg: print(f"WARNING: {msg}", file=sys.stderr)
PRINT_FN_SUCCESS_DEFAULT: Callable[[str], None] = lambda msg: print(f"SUCCESS: {msg}")


def run_command(
    command: Union[str, List[str]],
    capture_output: bool = False,
    check: bool = True,
    shell: bool = False,
    run_as_user: Optional[str] = None,
    cwd: Optional[Union[str, Path]] = None,
    env_vars: Optional[Dict[str, str]] = None,
    print_fn_info: Optional[Callable[[str], None]] = None,
    print_fn_error: Optional[Callable[[str], None]] = None,
    print_fn_sub_step: Optional[Callable[[str], None]] = None,
    logger: Optional[logging.Logger] = None
) -> subprocess.CompletedProcess:
    log = logger or default_script_logger
    _p_info = print_fn_info or PRINT_FN_INFO_DEFAULT
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or PRINT_FN_SUB_STEP_DEFAULT
    # _p_warning and _p_success are not used directly in this function but this pattern would apply.

    command_to_execute: Union[str, List[str]]
    effective_shell = shell
    display_command_str: str

    current_env = os.environ.copy()
    if env_vars:
        current_env.update(env_vars)

    if run_as_user:
        if isinstance(command, list):
            # Ensure all elements are strings for list2cmdline
            str_command = [str(item) for item in command]
            cmd_str_for_bash_c = subprocess.list2cmdline(str_command)
        elif isinstance(command, str):
            cmd_str_for_bash_c = command
        else:
            log.error("Invalid command type for 'run_as_user'. Must be string or list.")
            if _p_error: _p_error("Invalid command type for 'run_as_user'. Must be string or list.")
            raise TypeError("Command must be a string or list of strings for run_as_user execution via bash -c.")

        command_to_execute = ["sudo", "-Hn", "-u", run_as_user, "bash", "-c", cmd_str_for_bash_c]
        effective_shell = False # sudo -u bash -c handles the shell part for the user command
        display_command_str = f"(as {run_as_user}) {cmd_str_for_bash_c}"
    else:
        command_to_execute = command
        if isinstance(command, list):
             # Ensure all elements are strings for list2cmdline
            str_command = [str(item) for item in command]
            display_command_str = subprocess.list2cmdline(str_command)
        elif isinstance(command, str):
            display_command_str = command
        else:
            log.error("Invalid command type. Must be string or list.")
            if _p_error: _p_error("Invalid command type. Must be string or list.")
            raise TypeError("Command must be a string or list of strings.")

    log.info(f"Executing: {display_command_str}")
    _p_info(f"Executing: {display_command_str}") # This will be a no-op if _p_info is PRINT_FN_INFO_DEFAULT


    try:
        process = subprocess.run(
            command_to_execute,
            check=False, # We will check manually to provide better error logging via CalledProcessError
            capture_output=capture_output,
            text=True,
            shell=effective_shell,
            cwd=str(cwd) if cwd else None,
            env=current_env
        )

        if process.stdout and process.stdout.strip():
            log.debug(f"CMD STDOUT for '{display_command_str}':\n{process.stdout.strip()}")
            if capture_output: # Check if output should be captured (and thus potentially printed)
                stdout_summary = (process.stdout.strip()[:150] + '...') if len(process.stdout.strip()) > 150 else process.stdout.strip()
                _p_sub(f"STDOUT: {stdout_summary}") # This will be a no-op if _p_sub is PRINT_FN_SUB_STEP_DEFAULT


        if process.stderr and process.stderr.strip():
            # Log stderr as warning, as some commands use stderr for non-fatal info
            log.warning(f"CMD STDERR for '{display_command_str}':\n{process.stderr.strip()}")
            if capture_output: # Check if output should be captured
                stderr_summary = (process.stderr.strip()[:150] + '...') if len(process.stderr.strip()) > 150 else process.stderr.strip()
                _p_sub(f"STDERR: {stderr_summary}") # This will be a no-op if _p_sub is PRINT_FN_SUB_STEP_DEFAULT


        if check and process.returncode != 0:
            # Construct a more informative error message for CalledProcessError
            error_message = f"Command '{display_command_str}' returned non-zero exit status {process.returncode}."
            log.error(error_message)
            if process.stderr:
                log.error(f"STDERR: {process.stderr.strip()}")
            if process.stdout: # Also log stdout on error if it exists
                log.error(f"STDOUT: {process.stdout.strip()}")
            
            # Raise the exception so callers can handle it if needed
            # The cmd attribute of CalledProcessError is args, which is command_to_execute
            raise subprocess.CalledProcessError(
                returncode=process.returncode,
                cmd=command_to_execute, # Use the actual command list/string passed to Popen
                output=process.stdout,
                stderr=process.stderr
            )

        return process

    except subprocess.CalledProcessError as e: # This will re-raise if check=True caused it above
        # If check=False and we manually raise, this block might not be hit as expected unless subprocess.run(check=True) itself is used.
        # The above manual raise should be sufficient. This is a fallback.
        if not (check and process.returncode !=0) : # Avoid double logging if already handled by manual check.
            log.error(f"Command failed: '{subprocess.list2cmdline(e.cmd) if isinstance(e.cmd, list) else e.cmd}' (Exit code: {e.returncode})") 
            if e.stdout: log.error(f"Failed command STDOUT from exception:\n{e.stdout.strip()}")
            if e.stderr: log.error(f"Failed command STDERR from exception:\n{e.stderr.strip()}")
        if _p_error: _p_error(f"Command failed: '{subprocess.list2cmdline(e.cmd) if isinstance(e.cmd, list) else e.cmd}' (Exit code: {e.returncode}). Check logs.")
        raise
    except FileNotFoundError:
        cmd_part_not_found = ""
        # Try to determine which part of the command was not found
        if isinstance(command_to_execute, list) and command_to_execute:
            cmd_part_not_found = str(command_to_execute[0])
        elif isinstance(command_to_execute, str):
            cmd_part_not_found = shlex.split(command_to_execute)[0] if command_to_execute else ""
        
        log.error(f"Command executable not found: '{cmd_part_not_found}' (Full command attempted: '{display_command_str}')", exc_info=True)
        if _p_error: _p_error(f"Command executable not found: '{cmd_part_not_found}'. Ensure it's installed and in PATH.")
        raise
    except Exception as e: # Catch-all for other unexpected issues
        log.error(f"An unexpected error occurred while executing command '{display_command_str}': {e}", exc_info=True)
        if _p_error: _p_error(f"An unexpected error occurred while executing '{display_command_str}'. Check logs.")
        raise

def get_target_user(
    logger: Optional[logging.Logger] = None,
    print_fn_info: Optional[Callable[[str], None]] = None,
    print_fn_error: Optional[Callable[[str], None]] = None,
    print_fn_warning: Optional[Callable[[str], None]] = None
) -> Optional[str]:
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None) 
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_warning = print_fn_warning or PRINT_FN_WARNING_DEFAULT

    if os.geteuid() == 0: 
        target_user = os.environ.get("SUDO_USER")
        if not target_user:
            log.error("Script is running as root, but SUDO_USER environment variable is not set.")
            if _p_error: _p_error("Script is running as root, but SUDO_USER environment variable is not set. Cannot determine the target user.")
            return None
        try:
            # Verify SUDO_USER is a real user
            run_command(
                ["id", "-u", target_user],
                capture_output=True, check=True, logger=log,
                print_fn_info=None, print_fn_error=_p_error 
            )
            log.info(f"Target user determined: {target_user} (from SUDO_USER with root privileges)")
            return target_user
        except (subprocess.CalledProcessError, FileNotFoundError):
            log.error(f"The user '{target_user}' (from SUDO_USER) does not appear to be a valid system user.")
            if _p_error: _p_error(f"The user '{target_user}' (from SUDO_USER) does not appear to be a valid system user.")
            return None
    else: # Not root
        try:
            current_user = os.getlogin()
        except OSError: 
            # Fallback if os.getlogin() fails (e.g., in some non-interactive environments)
            import pwd
            try:
                current_user = pwd.getpwuid(os.getuid())[0]
                log.info(f"os.getlogin() failed, using UID's username: {current_user}")
            except Exception as e_pwd:
                log.error(f"Could not determine current user: os.getlogin() failed and pwd.getpwuid() failed: {e_pwd}")
                if _p_error: _p_error("Could not determine current user.")
                return None
        
        log.warning(f"Script is not running as root. Operations will target the current user ({current_user}).")
        if _p_warning and _p_warning is not PRINT_FN_WARNING_DEFAULT: _p_warning(f"Script is not running as root. Operations will target the current user ({current_user}).")
        return current_user

# --- Filesystem & User Info ---

def is_package_installed_rpm(
    package_name: str,
    logger: Optional[logging.Logger] = None,
    print_fn_info: Optional[Callable[[str], None]] = None # Note: Changed from default PRINT_FN_INFO_DEFAULT to None for quieter internal use
) -> bool:
    """Checks if a DNF package is already installed using 'rpm -q'."""
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None) 

    if not package_name:
        log.debug("Empty package name passed to is_package_installed_rpm.")
        return False
    log.debug(f"Checking if package '{package_name}' is installed via RPM.")
    try:
        proc = run_command(
            ["rpm", "-q", package_name],
            capture_output=True,
            check=False, # Non-zero means not installed or error
            print_fn_info=None, # Be quiet for this internal check, _p_info below is conditional
            logger=log
        )
        if proc.returncode == 0:
            log.info(f"RPM package '{package_name}' is already installed.")
            if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None:
                 _p_info(f"Package '{package_name}' is already installed.")
            return True
        else:
            # This is not an error, just means package isn't installed.
            log.info(f"RPM package '{package_name}' is not installed (rpm -q exit code: {proc.returncode}).")
            return False
    except FileNotFoundError:
        log.error("'rpm' command not found. Cannot accurately check if package is installed.", exc_info=True)
        # Re-raise FileNotFoundError so caller knows rpm is missing, they might handle it.
        # (e.g., phase1 before dnf is confirmed, or if rpm is truly not on system)
        raise 
    except Exception as e: # Catch other subprocess errors or unexpected issues
        log.warning(f"Error checking if RPM package '{package_name}' is installed: {e}", exc_info=True)
        return False # Assume not installed on other errors to be safe for install logic.

def get_user_home_dir(
    username: str,
    logger: Optional[logging.Logger] = None,
    print_fn_error: Optional[Callable[[str], None]] = None
) -> Optional[Path]:
    """Gets the home directory for the specified username using getent."""
    log = logger or default_script_logger
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    
    log.debug(f"Getting home directory for user '{username}'.")
    try:
        cmd = f"getent passwd {shlex.quote(username)}"
        process = run_command(
            cmd, shell=True, # Using shell=True as getent is simple and username is quoted
            capture_output=True, check=True,
            print_fn_info=None, # Quiet for this internal check
            print_fn_error=_p_error, # Pass error printer for run_command
            logger=log
        )
        passwd_line = process.stdout.strip()
        if not passwd_line: # Should be caught by check=True if user not found
            log.error(f"User '{username}' not found via getent (empty output after successful command).")
            if _p_error: _p_error(f"Could not find user '{username}' via getent.")
            return None

        home_dir_str = passwd_line.split(":")[5]
        if not home_dir_str:
            log.error(f"Empty home directory field from getent for '{username}'.")
            if _p_error: _p_error(f"Could not determine home directory for user '{username}' from getent output.")
            return None
        log.info(f"Home directory for '{username}' is '{home_dir_str}'.")
        return Path(home_dir_str)
    except subprocess.CalledProcessError:
        # run_command already logs and calls _p_error
        log.warning(f"Failed to get home directory for user '{username}' (getent probably failed or user not found).")
        return None
    except IndexError:
        log.error(f"IndexError parsing getent output for home directory of '{username}'. Output: {passwd_line if 'passwd_line' in locals() else 'N/A'}")
        if _p_error: _p_error(f"Could not parse home directory for user '{username}' from getent output.")
        return None
    except Exception as e:
        log.error(f"Unexpected error getting home dir for '{username}': {e}", exc_info=True)
        if _p_error: _p_error(f"An unexpected error occurred while getting home directory for user '{username}': {e}")
        return None

def backup_system_file(
    filepath: Path,
    sudo_required: bool = True,
    backup_suffix_extra: str = "",
    logger: Optional[logging.Logger] = None,
    print_fn_info: Optional[Callable[[str], None]] = None,
    print_fn_warning: Optional[Callable[[str], None]] = None
) -> bool:
    """Creates a timestamped backup of a file, typically needing sudo for /etc files."""
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None)
    _p_warning = print_fn_warning or PRINT_FN_WARNING_DEFAULT

    if not filepath.exists():
        log.info(f"File {filepath} does not exist, no backup needed.")
        if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info(f"File {filepath} does not exist, no backup needed.")
        return True # Successfully did nothing as file doesn't exist

    # Create a more identifiable backup name
    project_name_part = Path.cwd().name.replace(' ','_').replace('/','_')
    timestamp_part = f"{project_name_part}_{int(time.time())}"
    
    final_suffix = "backup_"
    if backup_suffix_extra:
        final_suffix += f"{backup_suffix_extra}_"
    final_suffix += timestamp_part
    
    backup_path = filepath.with_name(f"{filepath.name}.{final_suffix}")

    log.info(f"Backing up {filepath} to {backup_path}...")
    if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info(f"Backing up {filepath} to {backup_path}...")
    
    cmd = ["cp", "-pf", str(filepath), str(backup_path)]
    if sudo_required:
        cmd.insert(0, "sudo")
    
    try:
        run_command(
            cmd,
            # Show "Executing..." only if a custom info printer is explicitly passed
            print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None,
            print_fn_error=_p_warning, # Use warning printer for errors from backup command
            logger=log
        )
        log.info(f"Successfully backed up {filepath} to {backup_path}")
        return True
    except Exception as e: # run_command will raise CalledProcessError for command failure
        # This catch is for unexpected issues in this function's logic itself, though less likely here.
        log.warning(f"Backup of {filepath} to {backup_path} failed: {e}", exc_info=True)
        if _p_warning: _p_warning(f"Could not back up {filepath}. Error: {e}")
        return False

def create_file_as_user(
    file_path: Path,
    content: str,
    target_user: str,
    logger: Optional[logging.Logger] = None,
    print_fn_info: Optional[Callable[[str], None]] = None,
    print_fn_error: Optional[Callable[[str], None]] = None
) -> bool:
    """Creates a file with the given content as the specified user."""
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None)
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT

    log.info(f"Creating file '{file_path}' as user '{target_user}'.")
    if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None:
        _p_info(f"Creating file '{file_path}' as user '{target_user}'.")

    try:
        # Use shell redirection to write the file content
        # This is a common and effective way to write a file as another user with sudo
        # The content is passed via stdin to `tee`
        cmd = f"tee {shlex.quote(str(file_path))}"

        # We need to run this with `sudo -u` and `bash -c` to handle the redirection correctly
        full_cmd = ["sudo", "-u", target_user, "bash", "-c", cmd]

        process = subprocess.run(
            full_cmd,
            input=content,
            text=True,
            check=True,
            capture_output=True
        )

        if process.stderr:
            log.warning(f"Stderr from tee command for '{file_path}': {process.stderr.strip()}")

        log.info(f"Successfully created file '{file_path}' for user '{target_user}'.")
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"Failed to create file '{file_path}' as user '{target_user}'. Error: {e.stderr or e.stdout or e}", exc_info=True)
        if _p_error:
            _p_error(f"Failed to create file '{file_path}': {e.stderr or e.stdout}")
        return False
    except Exception as e:
        log.error(f"An unexpected error occurred while creating file '{file_path}': {e}", exc_info=True)
        if _p_error:
            _p_error(f"An unexpected error occurred while creating file '{file_path}': {e}")
        return False

def ensure_dir_exists(
    dir_path: Path,
    target_user: Optional[str] = None,
    mode: Optional[str] = None, # e.g., "0755"
    logger: Optional[logging.Logger] = None,
    print_fn_info: Optional[Callable[[str], None]] = None,
    print_fn_error: Optional[Callable[[str], None]] = None,
    print_fn_success: Optional[Callable[[str], None]] = None
) -> bool:
    """Ensures a directory exists, creating it if necessary, optionally as a user and with a mode."""
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None)
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_success = print_fn_success or (lambda msg: None)

    log.info(f"Ensuring directory exists: {dir_path} (User: {target_user or 'current/root'}, Mode: {mode or 'default'})")

    # Check if directory exists (as the target user if specified, otherwise as current euid)
    check_cmd = f"test -d {shlex.quote(str(dir_path))}"
    try:
        proc = run_command(
            check_cmd,
            run_as_user=target_user,
            shell=True, # test -d needs shell when run with sudo -u bash -c
            check=False, capture_output=True,
            print_fn_info=None, logger=log # Quiet check
        )
        if proc.returncode == 0:
            log.info(f"Directory '{dir_path}' already exists.")
            if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None : _p_info(f"Directory '{dir_path}' already exists.")
            return True
    except Exception as e_check: # Could be sudo failure, or other issues
        log.warning(f"Could not check existence of directory '{dir_path}' (as user: {target_user}): {e_check}. Will attempt to create.")
        # Continue to attempt creation

    if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None : _p_info(f"Directory '{dir_path}' not found. Attempting to create it...")

    mkdir_cmd_parts = ["mkdir", "-p", str(dir_path)]
    
    # Determine if sudo is needed for mkdir itself (not via run_as_user)
    # run_as_user handles its own sudo for user context.
    # This 'sudo_for_mkdir' is if the script isn't root and making a system dir.
    sudo_for_mkdir = False
    if not target_user and os.geteuid() != 0:
        # Heuristic: if path starts with system-like dirs, and we are not root, and not targeting a user (who would get sudo -u)
        # then mkdir itself needs sudo.
        system_dirs_prefixes = ("/etc", "/opt", "/usr/local", "/var")
        if str(dir_path).startswith(system_dirs_prefixes):
            log.info("Prepending sudo for mkdir as it's a system directory and script is not root (and not targeting a specific user for the command).")
            sudo_for_mkdir = True
            
    final_mkdir_cmd = ["sudo"] + mkdir_cmd_parts if sudo_for_mkdir else mkdir_cmd_parts

    try:
        run_command(
            final_mkdir_cmd if not target_user else mkdir_cmd_parts, # If target_user, run_command adds sudo -u
            run_as_user=target_user,
            shell=bool(target_user), # Use shell if running as user for `mkdir -p` via bash -c
            check=True,
            print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None,
            print_fn_error=_p_error,
            logger=log
        )
        if mode:
            chmod_cmd_parts = ["chmod", mode, str(dir_path)]
            sudo_for_chmod = False
            if not target_user and os.geteuid() != 0:
                 system_dirs_prefixes = ("/etc", "/opt", "/usr/local", "/var")
                 if str(dir_path).startswith(system_dirs_prefixes):
                    sudo_for_chmod = True
            
            final_chmod_cmd = ["sudo"] + chmod_cmd_parts if sudo_for_chmod else chmod_cmd_parts

            run_command(
                final_chmod_cmd if not target_user else chmod_cmd_parts,
                run_as_user=target_user, 
                shell=bool(target_user), 
                check=True,
                print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None,
                print_fn_error=_p_error, logger=log
            )
        log.info(f"Successfully created/verified directory: {dir_path}")
        if _p_success and _p_success is not PRINT_FN_SUCCESS_DEFAULT and _p_success is not None : _p_success(f"Successfully ensured directory exists: {dir_path}")
        return True
    except Exception as e:
        log.error(f"Failed to create directory {dir_path} (User: {target_user}, Mode: {mode}): {e}", exc_info=True)
        if _p_error : _p_error(f"Failed to create directory {dir_path}: {e}")
        return False

# --- User Shell Management ---

def get_user_shell(
    username: str,
    logger: Optional[logging.Logger] = None,
    print_fn_warning: Optional[Callable[[str], None]] = None
) -> Optional[str]:
    """Gets the current login shell for a specified user using getent."""
    log = logger or default_script_logger
    _p_warning = print_fn_warning or (lambda msg: None)

    log.debug(f"Getting login shell for user '{username}'.")
    try:
        cmd = f"getent passwd {shlex.quote(username)}"
        process = run_command(
            cmd, shell=True, 
            capture_output=True,
            check=True, # Will raise CalledProcessError if user not found
            print_fn_info=None, # Quiet for this internal check
            logger=log
        )
        passwd_line = process.stdout.strip()
        # No need to check for empty passwd_line if check=True
        
        shell_path = passwd_line.split(":")[-1]
        if not shell_path: # Should not happen if format is correct, but good to check
            log.warning(f"Empty shell path from getent for user '{username}' despite successful command.")
            if _p_warning and _p_warning is not PRINT_FN_WARNING_DEFAULT and _p_warning is not None: _p_warning(f"Could not determine shell for user '{username}' from getent output (empty field).")
            return None
        log.info(f"Login shell for '{username}' is '{shell_path}'.")
        return shell_path
    except subprocess.CalledProcessError: # User not found or other getent error
        log.warning(f"Failed to get login shell for user '{username}' (getent failed or user not found).")
        if _p_warning and _p_warning is not PRINT_FN_WARNING_DEFAULT and _p_warning is not None: _p_warning(f"Could not find user '{username}' via getent to determine shell.")
        return None
    except IndexError: # Malformed passwd line from getent (unlikely)
        log.warning(f"IndexError parsing getent output for shell of '{username}'. Output: {passwd_line if 'passwd_line' in locals() else 'N/A'}")
        if _p_warning and _p_warning is not PRINT_FN_WARNING_DEFAULT and _p_warning is not None: _p_warning(f"Could not determine shell for user '{username}' from getent output (parse error).")
        return None
    except Exception as e: # Catch-all for other unexpected issues
        log.error(f"Unexpected error getting shell for user '{username}': {e}", exc_info=True)
        if _p_warning and _p_warning is not PRINT_FN_WARNING_DEFAULT and _p_warning is not None: _p_warning(f"Could not determine the current shell for user '{username}': {e}")
        return None

def ensure_shell_in_etc_shells(
    shell_path: str,
    logger: Optional[logging.Logger] = None,
    print_fn_info: Optional[Callable[[str], None]] = None,
    print_fn_error: Optional[Callable[[str], None]] = None,
    print_fn_success: Optional[Callable[[str], None]] = None,
    print_fn_warning: Optional[Callable[[str], None]] = None
) -> bool:
    """Ensures the given shell_path is listed in /etc/shells. Requires sudo for modification."""
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None)
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_success = print_fn_success or (lambda msg: None)
    _p_warning = print_fn_warning or (lambda msg: None)

    if not shell_path or not Path(shell_path).is_absolute(): # Basic validation
        log.error(f"Invalid shell_path '{shell_path}' passed to ensure_shell_in_etc_shells (empty or not absolute).")
        if _p_error: _p_error(f"Cannot ensure invalid shell path '{shell_path}' in /etc/shells.")
        return False
    
    log.info(f"Ensuring '{shell_path}' is in /etc/shells.")
    etc_shells_path = Path("/etc/shells")
    
    try:
        # Ensure /etc/shells exists, creating if root and missing
        if not etc_shells_path.is_file():
            log.warning(f"{etc_shells_path} not found.")
            if _p_warning and _p_warning is not PRINT_FN_WARNING_DEFAULT and _p_warning is not None : _p_warning(f"File {etc_shells_path} not found.")
            if os.geteuid() == 0: # If script is root, try to create it
                try:
                    if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info(f"Attempting to create {etc_shells_path} as root.")
                    # Use run_command for atomicity and logging
                    run_command(["sudo", "touch", str(etc_shells_path)], logger=log, print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None)
                    run_command(["sudo", "chown", "root:root", str(etc_shells_path)], logger=log, print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None)
                    run_command(["sudo", "chmod", "644", str(etc_shells_path)], logger=log, print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None)
                    log.info(f"Created {etc_shells_path}.")
                except Exception as e_create:
                    log.error(f"Failed to create {etc_shells_path}: {e_create}", exc_info=True)
                    if _p_error: _p_error(f"Failed to create {etc_shells_path}: {e_create}")
                    return False
            else: # Not root and file doesn't exist, cannot proceed with modification
                log.error(f"Cannot create or modify {etc_shells_path} without root privileges and file does not exist.")
                if _p_error: _p_error(f"Cannot create or modify {etc_shells_path} without root privileges as it does not exist.")
                return False

        # Read /etc/shells content with sudo cat to handle permissions if not root.
        # If root, can read directly, but sudo cat is safer for consistency if perms are weird.
        cat_cmd = ["sudo", "cat", str(etc_shells_path)] if os.geteuid() != 0 else ["cat", str(etc_shells_path)]
        cat_proc = run_command(
            cat_cmd,
            capture_output=True, check=True, logger=log, print_fn_info=None # Quiet read
        )
        current_shells_content = cat_proc.stdout
        current_shells = [line.strip() for line in current_shells_content.splitlines() if line.strip() and not line.startswith('#')]

        if shell_path in current_shells:
            log.info(f"'{shell_path}' already in {etc_shells_path}.")
            if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info(f"Shell '{shell_path}' already listed in {etc_shells_path}.")
            return True
        
        if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info(f"Shell '{shell_path}' not found in {etc_shells_path}. Attempting to add it (requires sudo)...")
        
        # Use sudo tee to append. This requires the script to have sudo rights or the user to enter password.
        quoted_shell_path = shlex.quote(shell_path)
        # The `echo ... | sudo tee -a ...` pattern is robust.
        append_cmd_str = f"echo {quoted_shell_path} | sudo tee -a {shlex.quote(str(etc_shells_path))} > /dev/null"

        run_command(
            append_cmd_str,
            shell=True, # sudo tee -a needs shell for pipeline
            check=True,
            # Show "Executing..." only if a custom info printer is explicitly passed
            print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None, 
            print_fn_error=_p_error,
            logger=log
        )

        log.info(f"Added '{shell_path}' to {etc_shells_path}.")
        if _p_success and _p_success is not PRINT_FN_SUCCESS_DEFAULT and _p_success is not None : _p_success(f"Successfully added '{shell_path}' to {etc_shells_path}.")
        return True
    except Exception as e: 
        log.error(f"Error processing /etc/shells for '{shell_path}': {e}", exc_info=True)
        if _p_error: _p_error(f"Failed to process /etc/shells for '{shell_path}': {e}")
        return False

def set_default_shell(
    username: str,
    shell_path: str,
    logger: Optional[logging.Logger] = None,
    print_fn_info: Optional[Callable[[str], None]] = None,
    print_fn_error: Optional[Callable[[str], None]] = None,
    print_fn_sub_step: Optional[Callable[[str], None]] = None,
    print_fn_warning: Optional[Callable[[str], None]] = None,
    print_fn_success: Optional[Callable[[str], None]] = None
) -> bool:
    """Sets the default login shell for the specified user. Requires root privileges if changing for another user."""
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None)
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or (lambda msg: None)
    _p_warning = print_fn_warning or (lambda msg: None)
    _p_success = print_fn_success or (lambda msg: None)

    current_shell = get_user_shell(username, logger=log, print_fn_warning=_p_warning)
    if current_shell == shell_path:
        log.info(f"Shell '{shell_path}' is already the default shell for user '{username}'.")
        if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None : _p_info(f"Shell '{shell_path}' is already the default for '{username}'.")
        return True

    if _p_sub and _p_sub is not PRINT_FN_SUB_STEP_DEFAULT and _p_sub is not None: _p_sub(f"Setting '{shell_path}' as default shell for user '{username}'...")
    log.info(f"Setting '{shell_path}' as default for '{username}'.")
    
    is_root = os.geteuid() == 0
    # Determine the actual user running the script (even if via sudo)
    script_runner_user = os.environ.get("SUDO_USER") if "SUDO_USER" in os.environ else os.getlogin()
    is_changing_own_shell = script_runner_user == username

    # Ensure shell is in /etc/shells (always needs sudo for modification)
    if not ensure_shell_in_etc_shells(shell_path, logger=log, print_fn_info=_p_info, print_fn_error=_p_error, print_fn_success=_p_success, print_fn_warning=_p_warning):
        # Error already printed by ensure_shell_in_etc_shells
        if _p_warning and _p_warning is not PRINT_FN_WARNING_DEFAULT and _p_warning is not None : _p_warning(f"Could not ensure '{shell_path}' is in /etc/shells. `chsh` might warn or fail.")
        # Don't fail here, let chsh attempt it.
    
    chsh_cmd_list = ["chsh", "-s", shell_path, username]
    
    # Determine if chsh itself needs sudo.
    # If script is root, no sudo prefix for chsh.
    # If script is not root BUT changing own shell, no sudo prefix for chsh.
    # If script is not root AND changing for another user, chsh needs sudo.
    if not is_root and not is_changing_own_shell:
         chsh_cmd_list.insert(0, "sudo")

    try:
        run_command(
            chsh_cmd_list,
            # Show "Executing..." only if a custom info printer is explicitly passed
            print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None,
            print_fn_error=_p_error,
            logger=log
        )
        
        time.sleep(0.5) # Give a moment for system changes to potentially propagate to getent
        new_shell_check = get_user_shell(username, logger=log, print_fn_warning=_p_warning)
        
        if new_shell_check == shell_path:
            log.info(f"Successfully set '{shell_path}' as the default shell for '{username}'.")
            if _p_success and _p_success is not PRINT_FN_SUCCESS_DEFAULT and _p_success is not None : _p_success(f"Successfully set '{shell_path}' as default shell for '{username}'.")
            if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None : _p_info("Note: The shell change will take effect upon the user's next login.")
        else:
            log.warning(f"chsh command for '{username}' to '{shell_path}' executed. Verification via getent currently shows shell as: '{new_shell_check or 'unknown'}'. This is sometimes delayed after chsh.")
            if _p_warning and _p_warning is not PRINT_FN_WARNING_DEFAULT and _p_warning is not None :
                _p_warning(f"chsh for '{username}' to '{shell_path}' ran. Verification (getent) shows: '{new_shell_check or 'unknown'}'.")
                _p_info("Shell change likely takes effect on next login. Please verify then.")
        
        return True # chsh command itself succeeded
    except subprocess.CalledProcessError as e:
        # run_command already logs and calls _p_error
        log.error(f"The 'chsh' command failed to set shell for '{username}'. Exit code: {e.returncode}", exc_info=False)
        # _p_error already called by run_command
        return False
    except Exception as e_unexp: 
        log.error(f"An unexpected error occurred while trying to set default shell for '{username}': {e_unexp}", exc_info=True)
        if _p_error: _p_error(f"An unexpected error occurred setting default shell for '{username}': {e_unexp}")
        return False


# --- DNF Operations ---
def install_dnf_packages(
    packages: List[str],
    allow_erasing: bool = False,
    capture_output: bool = True,
    print_fn_info: Optional[Callable[[str], None]] = None, # Changed default
    print_fn_error: Optional[Callable[[str], None]] = None, # Changed default
    print_fn_sub_step: Optional[Callable[[str], None]] = None, # Changed default
    logger: Optional[logging.Logger] = None,
    extra_args: Optional[List[str]] = None
) -> bool:
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None)
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or (lambda msg: None)

    if not packages:
        log.info("No DNF packages specified for installation.")
        if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info("No DNF packages specified for installation.")
        return True

    cmd = ["sudo", "dnf", "install", "-y"]
    if allow_erasing:
        cmd.append("--allowerasing")
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(packages)

    action_verb = "Installing"
    if allow_erasing:
        action_verb = "Installing (allowing erasing)"
    
    packages_str = ', '.join(packages)
    log.info(f"{action_verb} DNF packages: {packages_str}")
    if _p_sub and _p_sub is not PRINT_FN_SUB_STEP_DEFAULT and _p_sub is not None: _p_sub(f"{action_verb} DNF packages: {packages_str}") 

    try:
        run_command(
            cmd, capture_output=capture_output, check=True,
            print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None, 
            print_fn_error=_p_error, 
            print_fn_sub_step=_p_sub if (_p_sub and _p_sub is not PRINT_FN_SUB_STEP_DEFAULT and _p_sub is not None) else None,
            logger=log
        )
        if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info(f"DNF packages processed successfully: {packages_str}") 
        log.info(f"DNF packages processed successfully: {packages_str}")
        return True
    except Exception as e: # run_command raises CalledProcessError on failure
        log.error(f"Failed to process DNF packages: {packages_str}. Error: {e}", exc_info=True)
        # _p_error is called by run_command on failure
        return False

def install_dnf_groups(
    groups: List[str],
    allow_erasing: bool = True, 
    capture_output: bool = True,
    print_fn_info: Optional[Callable[[str], None]] = None, 
    print_fn_error: Optional[Callable[[str], None]] = None, 
    print_fn_sub_step: Optional[Callable[[str], None]] = None, 
    logger: Optional[logging.Logger] = None
) -> bool:
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None)
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or (lambda msg: None)

    if not groups:
        log.info("No DNF groups specified for installation.")
        if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info("No DNF groups specified for installation.")
        return True

    all_successful = True
    groups_str = ', '.join(groups)
    log.info(f"Installing DNF groups: {groups_str}")
    if _p_sub and _p_sub is not PRINT_FN_SUB_STEP_DEFAULT and _p_sub is not None: _p_sub(f"Installing DNF groups: {groups_str}")

    for group_id_or_name in groups:
        cmd = ["sudo", "dnf", "group", "install", "-y"]
        if allow_erasing:
            cmd.append("--allowerasing")
        cmd.append(group_id_or_name)
        
        if _p_sub and _p_sub is not PRINT_FN_SUB_STEP_DEFAULT and _p_sub is not None: _p_sub(f"Processing DNF group: {group_id_or_name}")
        try:
            run_command(
                cmd, capture_output=capture_output, check=True,
                print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None, 
                print_fn_error=_p_error, 
                print_fn_sub_step=_p_sub if (_p_sub and _p_sub is not PRINT_FN_SUB_STEP_DEFAULT and _p_sub is not None) else None,
                logger=log
            )
            if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info(f"DNF group '{group_id_or_name}' processed successfully.")
            log.info(f"DNF group '{group_id_or_name}' processed successfully.")
        except Exception as e:
            log.error(f"Failed to process DNF group '{group_id_or_name}'. Error: {e}", exc_info=True)
            all_successful = False
    return all_successful

def swap_dnf_packages(
    from_pkg: str,
    to_pkg: str,
    allow_erasing: bool = True, 
    capture_output: bool = True,
    print_fn_info: Optional[Callable[[str], None]] = None, 
    print_fn_error: Optional[Callable[[str], None]] = None, 
    print_fn_sub_step: Optional[Callable[[str], None]] = None, 
    logger: Optional[logging.Logger] = None
) -> bool:
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None)
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or (lambda msg: None)

    if not from_pkg or not to_pkg:
        if _p_error: _p_error("Invalid 'from' or 'to' package name for DNF swap.")
        log.error(f"Invalid DNF swap params: from='{from_pkg}', to='{to_pkg}'")
        return False

    log.info(f"Attempting DNF swap: from '{from_pkg}' to '{to_pkg}'")
    if _p_sub and _p_sub is not PRINT_FN_SUB_STEP_DEFAULT and _p_sub is not None: _p_sub(f"Attempting DNF swap: from '{from_pkg}' to '{to_pkg}'")

    try:
        from_pkg_installed = False
        try:
            # Use the new utility, be quiet on success/failure of this check
            from_pkg_installed = is_package_installed_rpm(from_pkg, logger=log, print_fn_info=None)
        except FileNotFoundError: 
             log.error("'rpm' command not found. Cannot accurately check if 'from_pkg' for swap is installed. Proceeding with swap command directly assuming it might be needed.", exc_info=True)
             # If rpm is not found, we can't reliably check. DNF swap will handle it if 'from_pkg' is not installed.
             from_pkg_installed = True # Assume it might be installed to trigger swap logic
        except Exception as e_rpm_check:
            log.warning(f"Could not determine if '{from_pkg}' is installed due to: {e_rpm_check}. Proceeding with swap attempt.")
            from_pkg_installed = True # Assume it might be installed

        if not from_pkg_installed:
            if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info(f"Package '{from_pkg}' is not installed. Attempting direct install of '{to_pkg}'.")
            log.info(f"'{from_pkg}' not installed. Directly installing '{to_pkg}'.")
            return install_dnf_packages(
                [to_pkg], allow_erasing=allow_erasing, capture_output=capture_output,
                print_fn_info=_p_info, print_fn_error=_p_error, print_fn_sub_step=_p_sub,
                logger=log
            )

        # If from_pkg is (assumed to be) installed, proceed with swap
        cmd = ["sudo", "dnf", "swap", "-y"]
        if allow_erasing:
            cmd.append("--allowerasing")
        cmd.extend([from_pkg, to_pkg])
        
        run_command(
            cmd, capture_output=capture_output, check=True,
            print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None, 
            print_fn_error=_p_error, 
            print_fn_sub_step=_p_sub if (_p_sub and _p_sub is not PRINT_FN_SUB_STEP_DEFAULT and _p_sub is not None) else None,
            logger=log
        )
        if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info(f"DNF package '{from_pkg}' successfully swapped with '{to_pkg}'.")
        log.info(f"Successfully swapped '{from_pkg}' with '{to_pkg}'.")
        return True
    except Exception as e: # run_command raises CalledProcessError
        log.error(f"Failed DNF swap from '{from_pkg}' to '{to_pkg}'. Error: {e}", exc_info=True)
        # _p_error is called by run_command
        return False

def upgrade_system_dnf(
    capture_output: bool = False, 
    print_fn_info: Optional[Callable[[str], None]] = None, 
    print_fn_error: Optional[Callable[[str], None]] = None, 
    logger: Optional[logging.Logger] = None
) -> bool:
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None)
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT

    cmd = ["sudo", "dnf", "upgrade", "-y"]
    log.info("Attempting system upgrade using DNF...")
    if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info("Attempting system upgrade (sudo dnf upgrade -y)...")
    try:
        run_command(
            cmd, capture_output=capture_output, check=True,
            print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None, 
            print_fn_error=_p_error,
            logger=log
        )
        if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info("System DNF upgrade completed successfully.")
        log.info("System DNF upgrade completed successfully.")
        return True
    except Exception as e:
        log.error(f"System DNF upgrade failed. Error: {e}", exc_info=True)
        # _p_error is called by run_command
        return False

def clean_dnf_cache(
    clean_type: str = "all", 
    capture_output: bool = True,
    print_fn_info: Optional[Callable[[str], None]] = None, 
    print_fn_error: Optional[Callable[[str], None]] = None, 
    logger: Optional[logging.Logger] = None
) -> bool:
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None)
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT

    cmd = ["sudo", "dnf", "clean", clean_type]
    log.info(f"Attempting to clean DNF cache ({clean_type})...")
    if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info(f"Attempting to clean DNF cache (sudo dnf clean {clean_type})...")
    try:
        run_command(
            cmd, capture_output=capture_output, check=True,
            print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None, 
            print_fn_error=_p_error,
            logger=log
        )
        if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info(f"DNF cache clean ({clean_type}) completed successfully.")
        log.info(f"DNF cache clean ({clean_type}) completed successfully.")
        return True
    except Exception as e:
        log.error(f"DNF cache clean ({clean_type}) failed. Error: {e}", exc_info=True)
        # _p_error is called by run_command
        return False


# --- Pip Operations ---
def install_pip_packages(
    packages: List[str],
    user_only: bool = False,
    target_user: Optional[str] = None, # Must be provided if user_only is True
    upgrade: bool = True,
    capture_output: bool = True,
    print_fn_info: Optional[Callable[[str], None]] = None, 
    print_fn_error: Optional[Callable[[str], None]] = None, 
    print_fn_sub_step: Optional[Callable[[str], None]] = None, 
    logger: Optional[logging.Logger] = None
) -> bool:
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None)
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or (lambda msg: None)

    if not packages:
        log.info("No pip packages specified for installation.")
        if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info("No pip packages specified for installation.")
        return True

    if user_only and not target_user:
        if _p_error: _p_error("target_user must be specified when user_only is True for pip install.")
        log.error("pip install --user requires target_user.")
        return False

    base_cmd_list_for_user = ["python3", "-m", "pip", "install"]
    if upgrade:
        base_cmd_list_for_user.append("--upgrade")
    if user_only: # This flag is for pip itself
        base_cmd_list_for_user.append("--user")
    
    # Determine actual execution command and context
    run_as_whom = None
    final_base_cmd_list = base_cmd_list_for_user.copy() # Start with the user-context command
    log_context_message = ""

    if user_only:
        run_as_whom = target_user
        log_context_message = f"for user '{target_user}'"
        # Command is `python3 -m pip install --user ...` run as `target_user`
    else: # System-wide pip install generally needs sudo
        final_base_cmd_list.insert(0, "sudo") # Prepend sudo for system-wide execution
        log_context_message = "system-wide"
        # Command is `sudo python3 -m pip install ...`

    packages_str = ', '.join(packages)
    log.info(f"Installing pip packages ({log_context_message}): {packages_str}")
    if _p_sub and _p_sub is not PRINT_FN_SUB_STEP_DEFAULT and _p_sub is not None: _p_sub(f"Installing pip packages ({log_context_message}): {packages_str}")
    
    all_ok = True
    for pkg in packages:
        current_pkg_cmd_list = final_base_cmd_list + [pkg]
        
        try:
            run_command(
                current_pkg_cmd_list, 
                run_as_user=run_as_whom, # This is None for system-wide, target_user for user_only
                                          # run_command handles sudo -u if run_as_whom is set.
                shell=bool(run_as_whom),  # Use shell for user context to find python3 in user's PATH correctly
                                          # For system-wide (sudo python3...), shell=False is generally fine.
                capture_output=capture_output, 
                check=True, 
                print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None,
                print_fn_error=_p_error,
                print_fn_sub_step=_p_sub if (_p_sub and _p_sub is not PRINT_FN_SUB_STEP_DEFAULT and _p_sub is not None) else None,
                logger=log
            )
            if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info(f"Pip package '{pkg}' installed/updated ({log_context_message}).")
            log.info(f"Pip package '{pkg}' installed/updated ({log_context_message}).")
        except subprocess.CalledProcessError as e:
            # _p_error is called by run_command
            log.error(f"Failed pip install of '{pkg}' ({log_context_message}). Exit code: {e.returncode}", exc_info=False) # exc_info=False as run_command already logged details
            all_ok = False
        except Exception as e_unexpected: # Catch other errors like FileNotFoundError for python3
            log.error(f"Unexpected error during pip install of '{pkg}' ({log_context_message}): {e_unexpected}", exc_info=True)
            if _p_error: _p_error(f"Unexpected error installing pip package '{pkg}' ({log_context_message}).")
            all_ok = False
    return all_ok


# --- Flatpak Operations ---
def ensure_flathub_remote_exists(
    print_fn_info: Optional[Callable[[str], None]] = None, 
    print_fn_error: Optional[Callable[[str], None]] = None, 
    print_fn_sub_step: Optional[Callable[[str], None]] = None, # Kept for API consistency
    logger: Optional[logging.Logger] = None
) -> bool:
    """Ensures the Flathub repository is configured for Flatpak system-wide."""
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None)
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT

    log.info("Ensuring Flathub remote is configured for Flatpak (system-wide).")
    if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info("Ensuring Flathub remote is configured for Flatpak (system-wide)...")

    try:
        # Check if flatpak command exists first
        try:
            run_command(["flatpak", "--version"], capture_output=True, check=True, print_fn_info=None, logger=log)
        except FileNotFoundError:
            log.error("'flatpak' command not found. Is Flatpak installed (e.g., via DNF in Phase 1)?")
            if _p_error: _p_error("'flatpak' command not found. Please ensure it is installed.")
            return False
        
        check_cmd = ["flatpak", "remotes", "--system"]
        remotes_process = run_command(
            check_cmd, capture_output=True, check=False, # check=False, as empty output or error can mean no remotes
            print_fn_info=None, # Quiet check
            logger=log
        )
        
        flathub_found = False
        if remotes_process.returncode == 0 and remotes_process.stdout:
            for line in remotes_process.stdout.strip().splitlines():
                # Remote names are typically the first column, tab-separated
                remote_name_candidate = line.strip().split("\t")[0].strip()
                if remote_name_candidate.lower() == "flathub": # Case-insensitive check
                    flathub_found = True
                    break
        
        if flathub_found:
            if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info("Flathub remote 'flathub' already exists (system-wide).")
            log.info("Flathub remote 'flathub' already exists system-wide.")
            return True
        
        if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info("Flathub remote not found. Attempting to add system-wide...")
        log.info("Flathub remote not found. Attempting to add system-wide.")
        cmd_add_flathub = [
            "sudo", "flatpak", "remote-add", "--if-not-exists", 
            "flathub", "https://dl.flathub.org/repo/flathub.flatpakrepo"
        ]
        run_command(
            cmd_add_flathub, capture_output=True, check=True, # Output useful for logging
            print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None, 
            print_fn_error=_p_error,
            logger=log
        )
        if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info("Flathub repository added successfully for Flatpak (system-wide).")
        log.info("Flathub repository added for Flatpak (system-wide).")
        return True
    # FileNotFoundError for flatpak handled above.
    except subprocess.CalledProcessError as e: 
        # run_command already logs and calls _p_error
        log.error(f"Failed to setup Flathub repository. CalledProcessError: {e.stderr or e.stdout or e}", exc_info=False)
        return False
    except Exception as e_unexp: 
        log.error(f"An unexpected error occurred during Flathub setup: {e_unexp}", exc_info=True)
        if _p_error: _p_error(f"An unexpected error occurred during Flathub setup: {e_unexp}")
        return False

def install_flatpak_apps(
    apps_to_install: Dict[str, str], 
    system_wide: bool = True,
    remote_name: str = "flathub",
    print_fn_info: Optional[Callable[[str], None]] = None, 
    print_fn_error: Optional[Callable[[str], None]] = None, 
    print_fn_sub_step: Optional[Callable[[str], None]] = None, 
    logger: Optional[logging.Logger] = None
) -> bool:
    log = logger or default_script_logger
    _p_info = print_fn_info or (lambda msg: None)
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or (lambda msg: None)

    if not apps_to_install:
        log.info("No Flatpak applications specified for installation.")
        if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info("No Flatpak applications specified for installation.")
        return True

    # Ensure Flathub remote exists before trying to install from it
    if remote_name.lower() == "flathub":
        if not ensure_flathub_remote_exists(print_fn_info=_p_info, print_fn_error=_p_error, logger=log):
            log.error("Flathub remote setup failed. Cannot install Flatpak apps from Flathub.")
            # _p_error already called by ensure_flathub_remote_exists
            return False

    overall_success = True
    install_type = "system-wide" if system_wide else "user"
    
    app_names_str = ', '.join(f"{name} ({id})" for id, name in apps_to_install.items()) # More descriptive
    log.info(f"Preparing to install Flatpak applications ({install_type}): {app_names_str}")
    if _p_sub and _p_sub is not PRINT_FN_SUB_STEP_DEFAULT and _p_sub is not None: _p_sub(f"Installing Flatpak applications ({install_type}): {app_names_str}")

    for app_id, app_name in apps_to_install.items():
        log.info(f"Processing Flatpak app '{app_name}' ({app_id})...")

        cmd_list = []
        # Flatpak install --system requires sudo, flatpak install --user does not.
        # run_command does not add sudo if run_as_user is None.
        if system_wide: 
            cmd_list.append("sudo") 
        
        cmd_list.extend(["flatpak", "install"])
        
        if system_wide: 
            cmd_list.append("--system")
        else: 
            cmd_list.append("--user")
            # For --user install, we should run as the target_user if one is implied by context (e.g. non-root script run)
            # This function doesn't take target_user. It assumes system_wide means root, user means current user.
            # If a phase running as root wants to install a user flatpak, it needs a target_user.
            # For now, this structure is simpler: sudo for system, no sudo for user (current user).

        cmd_list.extend(["--noninteractive", "--or-update", remote_name, app_id])

        try:
            run_command(
                cmd_list, 
                capture_output=True, 
                check=True,
                print_fn_info=_p_info if (_p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None) else None, 
                print_fn_error=_p_error, 
                print_fn_sub_step=_p_sub if (_p_sub and _p_sub is not PRINT_FN_SUB_STEP_DEFAULT and _p_sub is not None) else None,
                logger=log
            )
            if _p_info and _p_info is not PRINT_FN_INFO_DEFAULT and _p_info is not None: _p_info(f"Flatpak app '{app_name}' ({app_id}) processed successfully ({install_type}).")
            log.info(f"Flatpak app '{app_name}' ({app_id}) installed/updated successfully ({install_type}).")
        except FileNotFoundError: # Should be caught by ensure_flathub_remote_exists's check
            log.error("'flatpak' command not found. Is Flatpak installed?", exc_info=True)
            if _p_error: _p_error("'flatpak' command not found. Is Flatpak installed?")
            overall_success = False; break 
        except subprocess.CalledProcessError:
            # run_command already logs and calls _p_error
            log.error(f"Failed to install Flatpak app '{app_name}' ({app_id}) ({install_type}).")
            overall_success = False
        except Exception as e:
            log.error(f"An unexpected error occurred while installing Flatpak app '{app_name}' ({app_id}) ({install_type}): {e}", exc_info=True)
            if _p_error: _p_error(f"An unexpected error occurred while installing Flatpak app '{app_name}' ({app_id}).")
            overall_success = False

    if overall_success and apps_to_install:
        log.info(f"All specified Flatpak applications processed successfully ({install_type}).")
    elif not overall_success and apps_to_install: # Only print error if there were apps to install
        log.error(f"Some Flatpak applications ({install_type}) could not be installed.")
        if _p_error : _p_error(f"Some Flatpak applications ({install_type}) could not be installed. Check logs for details.")

    return overall_success