# Fedora-AutoEnv-Setup/scripts/system_utils.py

import subprocess
import os
import shlex 
import sys 
from pathlib import Path
from typing import List, Optional, Union, Dict, Callable
import logging # Import logging

# Attempt to import app_logger from logger_utils.
# If it's not there (e.g. logger_utils not created yet or run_command used standalone),
# fall back to basic print or a default logger.
try:
    from scripts.logger_utils import app_logger as default_script_logger
except ImportError:
    # Fallback if logger_utils or app_logger is not available
    # This allows system_utils to be potentially used even if the full logger setup isn't present.
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    default_script_logger = logging.getLogger("system_utils_fallback")
    default_script_logger.info("Default fallback logger initialized for system_utils.")


# Default print functions if no specific logging functions are passed (for console output)
PRINT_FN_INFO_DEFAULT: Callable[[str], None] = lambda msg: print(f"INFO: {msg}")
PRINT_FN_ERROR_DEFAULT: Callable[[str], None] = lambda msg: print(f"ERROR: {msg}", file=sys.stderr)
PRINT_FN_SUB_STEP_DEFAULT: Callable[[str], None] = lambda msg: print(f"  SUB: {msg}")


def run_command(
    command: Union[str, List[str]],
    capture_output: bool = False,
    check: bool = True,
    shell: bool = False,
    run_as_user: Optional[str] = None,
    cwd: Optional[Union[str, Path]] = None,
    env_vars: Optional[Dict[str, str]] = None,
    print_fn_info: Optional[Callable[[str], None]] = None, # For user-facing console info
    print_fn_error: Optional[Callable[[str], None]] = None,  # For user-facing console errors
    print_fn_sub_step: Optional[Callable[[str], None]] = None, # For user-facing sub-steps
    logger: Optional[logging.Logger] = None # <<<<< NEW LOGGER ARGUMENT
) -> subprocess.CompletedProcess:
    """
    Runs a shell command, optionally as a different user via sudo -Hn -u.

    Args:
        command: The command to run, as a string (if shell=True) or list of strings.
        capture_output: If True, stdout and stderr will be captured.
        check: If True, raise CalledProcessError on non-zero exit codes.
        shell: If True, the command is executed through the shell.
               BE CAREFUL with shell=True and unsanitized input.
        run_as_user: If set, run the command as this user via 'sudo -Hn -u'.
        cwd: Current working directory for the command.
        env_vars: Dictionary of environment variables to set for the command.
        print_fn_info: Function to call for user-facing informational messages on console.
        print_fn_error: Function to call for user-facing error messages on console.
        print_fn_sub_step: Function to call for user-facing sub-step messages on console.
        logger: A logging.Logger instance for detailed file/debug logging.
                If None, defaults to a basic logger or internal app_logger.

    Returns:
        subprocess.CompletedProcess: The result of the command execution.

    Raises:
        subprocess.CalledProcessError: If 'check' is True and command returns non-zero.
        FileNotFoundError: If the command executable is not found.
        TypeError: If 'command' is not a string or list when 'run_as_user' is specified.
    """
    # Use provided logger or the default logger from this module (which tries to get app_logger)
    log = logger or default_script_logger 
    
    # User-facing console print functions (can be None if caller doesn't want console output for this command)
    _p_info = print_fn_info or (lambda msg: None) # No-op if not provided
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT # Fallback to print for critical errors
    _p_sub = print_fn_sub_step or (lambda msg: None) # No-op if not provided

    command_to_execute: Union[str, List[str]]
    effective_shell = shell
    display_command_str: str

    current_env = os.environ.copy()
    if env_vars:
        current_env.update(env_vars)

    if run_as_user:
        if isinstance(command, list):
            cmd_str_for_bash_c = subprocess.list2cmdline(command)
        elif isinstance(command, str):
            cmd_str_for_bash_c = command
        else:
            log.error("Invalid command type for 'run_as_user'. Must be string or list.")
            _p_error("Invalid command type for 'run_as_user'. Must be string or list.") # Also inform user
            raise TypeError("Command must be a string or list of strings for run_as_user execution via bash -c.")
        
        command_to_execute = ["sudo", "-Hn", "-u", run_as_user, "bash", "-c", cmd_str_for_bash_c]
        effective_shell = False  
        display_command_str = f"(as {run_as_user}) {cmd_str_for_bash_c}"
    else:
        command_to_execute = command
        if isinstance(command, list):
            display_command_str = subprocess.list2cmdline(command) 
        elif isinstance(command, str):
            display_command_str = command
        else:
            log.error("Invalid command type. Must be string or list.")
            _p_error("Invalid command type. Must be string or list.")
            raise TypeError("Command must be a string or list of strings.")
    
    log.info(f"Executing: {display_command_str}") # Log the command being executed
    _p_info(f"Executing: {display_command_str}") # Show user (if print_fn_info is provided)

    try:
        process = subprocess.run(
            command_to_execute,
            check=False, # We will check manually after logging output
            capture_output=capture_output,
            text=True,    
            shell=effective_shell,
            cwd=str(cwd) if cwd else None,
            env=current_env 
        )

        # Log STDOUT and STDERR regardless of capture_output for the file log (at DEBUG level)
        # The console output (_p_sub) is still conditional on capture_output for brevity.
        if process.stdout and process.stdout.strip():
            log.debug(f"CMD STDOUT for '{display_command_str}':\n{process.stdout.strip()}")
            if capture_output: # Only show summary on console if captured
                stdout_summary = (process.stdout.strip()[:150] + '...') if len(process.stdout.strip()) > 150 else process.stdout.strip()
                _p_sub(f"STDOUT: {stdout_summary}")
        
        if process.stderr and process.stderr.strip():
            # Log all stderr as warning to file log, as it often contains important info even on success.
            log.warning(f"CMD STDERR for '{display_command_str}':\n{process.stderr.strip()}")
            if capture_output: # Only show summary on console if captured
                stderr_summary = (process.stderr.strip()[:150] + '...') if len(process.stderr.strip()) > 150 else process.stderr.strip()
                # Decide if all stderr summaries go to console _p_sub or _p_error based on context
                # For now, using _p_sub for captured stderr as well.
                _p_sub(f"STDERR: {stderr_summary}") 

        if check and process.returncode != 0:
            # Error details already logged above. Now raise the exception.
            # Note: The original CalledProcessError won't have stdout/stderr if we didn't capture them initially,
            # but we've logged them. We can re-create a similar error or just raise.
            # For simplicity, let subprocess.run create the error object based on its call.
            # To do this, we call it again with check=True if it failed.
            # This is a bit inefficient but ensures the correct exception type and attributes.
            # A cleaner way: manually raise a CalledProcessError.
            
            # Manually raise CalledProcessError to include output even if initial check was False
            raise subprocess.CalledProcessError(
                returncode=process.returncode,
                cmd=process.args, # command_to_execute might be better here for consistency
                output=process.stdout,
                stderr=process.stderr
            )
            
        return process
        
    except subprocess.CalledProcessError as e:
        # This block will now catch the manually raised error or if subprocess.run itself raised it (if check=True was used initially)
        log.error(f"Command failed: '{display_command_str}' (Exit code: {e.returncode})")
        # STDOUT/STDERR from the exception object 'e' are logged if they exist
        if e.stdout:
             log.error(f"Failed command STDOUT from exception:\n{e.stdout.strip()}")
        if e.stderr:
             log.error(f"Failed command STDERR from exception:\n{e.stderr.strip()}")
        _p_error(f"Command failed: '{display_command_str}' (Exit code: {e.returncode}). Check logs.") # User-facing
        raise 
    except FileNotFoundError:
        cmd_part_not_found = ""
        if isinstance(command_to_execute, list) and command_to_execute:
            cmd_part_not_found = command_to_execute[0]
        elif isinstance(command_to_execute, str):
            cmd_part_not_found = command_to_execute.split(' ', 1)[0]
        log.error(f"Command executable not found: '{cmd_part_not_found}' (Full command attempted: '{display_command_str}')", exc_info=True)
        _p_error(f"Command executable not found: '{cmd_part_not_found}'.")
        raise
    except Exception as e: 
        log.error(f"An unexpected error occurred while executing command '{display_command_str}': {e}", exc_info=True)
        _p_error(f"An unexpected error occurred while executing '{display_command_str}'. Check logs.")
        raise

# ... (keep install_flatpak_apps if it's here) ...
def install_flatpak_apps(
    apps_to_install: Dict[str, str], 
    system_wide: bool = True,
    remote_name: str = "flathub",
    print_fn_info: Optional[Callable[[str], None]] = None,
    print_fn_error: Optional[Callable[[str], None]] = None,
    print_fn_sub_step: Optional[Callable[[str], None]] = None,
    logger: Optional[logging.Logger] = None # Added logger here too
) -> bool:
    log = logger or default_script_logger
    _p_info = print_fn_info or PRINT_FN_INFO_DEFAULT
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or PRINT_FN_SUB_STEP_DEFAULT

    if not apps_to_install:
        log.info("No Flatpak applications specified for installation.")
        _p_info("No Flatpak applications specified for installation.")
        return True

    overall_success = True
    install_type = "system-wide" if system_wide else "user"
    log.info(f"Preparing to install Flatpak applications ({install_type}): {', '.join(apps_to_install.keys())}")
    _p_sub(f"Preparing to install Flatpak applications ({install_type}): {', '.join(apps_to_install.keys())}")

    for app_id, app_name in apps_to_install.items():
        log.info(f"Processing Flatpak app '{app_name}' ({app_id})...")
        _p_info(f"Installing '{app_name}' ({app_id})...")
        
        cmd_list = []
        if system_wide: cmd_list.append("sudo")
        cmd_list.extend(["flatpak", "install"])
        if system_wide: cmd_list.append("--system")
        else: cmd_list.append("--user")
        cmd_list.extend(["--noninteractive", "--or-update", remote_name, app_id])
        
        try:
            run_command(
                cmd_list, capture_output=True, check=True,          
                print_fn_info=_p_info, print_fn_error=_p_error, print_fn_sub_step=_p_sub,
                logger=log # Pass the logger through
            )
            _p_info(f"Flatpak app '{app_name}' ({app_id}) installed/updated successfully.")
            log.info(f"Flatpak app '{app_name}' ({app_id}) installed/updated successfully.")
        except FileNotFoundError:
            log.error("'flatpak' command not found. Is Flatpak installed and Flathub remote added?", exc_info=True)
            _p_error("'flatpak' command not found. Is Flatpak installed and Flathub remote added (e.g., in Phase 1)?")
            overall_success = False; break 
        except subprocess.CalledProcessError: 
            log.error(f"Failed to install Flatpak app '{app_name}' ({app_id}). See previous errors from run_command.")
            _p_error(f"Failed to install Flatpak app '{app_name}' ({app_id}). Check output above for details.")
            overall_success = False
        except Exception as e: 
            log.error(f"An unexpected error occurred while installing Flatpak app '{app_name}' ({app_id}): {e}", exc_info=True)
            _p_error(f"An unexpected error occurred while installing Flatpak app '{app_name}' ({app_id}).")
            overall_success = False
            
    if overall_success and apps_to_install:
        log.info("All specified Flatpak applications processed.")
    elif not overall_success:
        log.error("Some Flatpak applications could not be installed.")
        _p_error("Some Flatpak applications could not be installed.")
        
    return overall_success