# Fedora-AutoEnv-Setup/scripts/system_utils.py

import subprocess
import os
import shlex # For shlex.quote and subprocess.list2cmdline
import sys # For PRINT_FN_ERROR_DEFAULT
from pathlib import Path
from typing import List, Optional, Union, Dict, Callable

# Default print functions if no specific logging functions are passed
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
    print_fn_info: Optional[Callable[[str], None]] = None,
    print_fn_error: Optional[Callable[[str], None]] = None,
    print_fn_sub_step: Optional[Callable[[str], None]] = None
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
                     '-H' sets HOME to the target user's home directory.
                     '-n' for non-interactive sudo.
        cwd: Current working directory for the command.
        env_vars: Dictionary of environment variables to set for the command.
        print_fn_info: Function to call for informational messages.
        print_fn_error: Function to call for error messages.
        print_fn_sub_step: Function to call for sub-step messages.

    Returns:
        subprocess.CompletedProcess: The result of the command execution.

    Raises:
        subprocess.CalledProcessError: If 'check' is True and command returns non-zero.
        FileNotFoundError: If the command executable is not found.
        TypeError: If 'command' is not a string or list when 'run_as_user' is specified.
    """
    _p_info = print_fn_info or PRINT_FN_INFO_DEFAULT
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or PRINT_FN_SUB_STEP_DEFAULT

    command_to_execute: Union[str, List[str]]
    effective_shell = shell
    display_command_str: str

    # Prepare environment: start with current environment and update with provided vars
    current_env = os.environ.copy()
    if env_vars:
        current_env.update(env_vars)

    if run_as_user:
        if isinstance(command, list):
            cmd_str_for_bash_c = subprocess.list2cmdline(command)
        elif isinstance(command, str):
            cmd_str_for_bash_c = command
        else:
            # This case should not happen if type hints are respected, but good to guard.
            _p_error("Invalid command type for 'run_as_user'. Must be string or list.")
            raise TypeError("Command must be a string or list of strings for run_as_user execution via bash -c.")

        # Use 'sudo -Hn -u <user> bash -c "<command_string>"'
        # -H sets the HOME environment variable to the target user's home directory.
        # -n (non-interactive) prevents sudo from prompting for a password on the terminal.
        command_to_execute = ["sudo", "-Hn", "-u", run_as_user, "bash", "-c", cmd_str_for_bash_c]
        effective_shell = False  # The user's command string is run by 'bash -c'
        display_command_str = f"(as {run_as_user}) {cmd_str_for_bash_c}"
    else:
        command_to_execute = command
        if isinstance(command, list):
            display_command_str = subprocess.list2cmdline(command) # For display
        elif isinstance(command, str):
            display_command_str = command
        else:
            _p_error("Invalid command type. Must be string or list.")
            raise TypeError("Command must be a string or list of strings.")
    
    _p_info(f"Executing: {display_command_str}")

    try:
        process = subprocess.run(
            command_to_execute,
            check=check, # If True, this will raise CalledProcessError on non-zero exit
            capture_output=capture_output,
            text=True,    # Decodes stdout/stderr as text
            shell=effective_shell,
            cwd=str(cwd) if cwd else None,
            env=current_env # Pass the prepared environment
        )

        if capture_output: # Only print if captured, otherwise it's live on terminal
            if process.stdout and process.stdout.strip():
                stdout_summary = (process.stdout.strip()[:150] + '...') if len(process.stdout.strip()) > 150 else process.stdout.strip()
                _p_sub(f"STDOUT: {stdout_summary}")
            if process.stderr and process.stderr.strip():
                stderr_summary = (process.stderr.strip()[:150] + '...') if len(process.stderr.strip()) > 150 else process.stderr.strip()
                _p_sub(f"STDERR: {stderr_summary}") # Often includes errors or warnings
        return process
    except subprocess.CalledProcessError as e:
        _p_error(f"Command failed: '{display_command_str}' (Exit code: {e.returncode})")
        # Output is in e.stdout / e.stderr if capture_output=True
        if e.stdout:
             _p_error(f"Failed command STDOUT: {e.stdout.strip()}")
        if e.stderr:
             _p_error(f"Failed command STDERR: {e.stderr.strip()}")
        raise # Re-raise the exception so the caller can handle it if needed
    except FileNotFoundError:
        # Determine which part of the command was not found
        cmd_part_not_found = ""
        if isinstance(command_to_execute, list) and command_to_execute:
            cmd_part_not_found = command_to_execute[0]
        elif isinstance(command_to_execute, str):
            cmd_part_not_found = command_to_execute.split()[0]
        _p_error(f"Command executable not found: '{cmd_part_not_found}' (Full command attempted: '{display_command_str}')")
        raise
    except Exception as e: # Catch-all for other unexpected errors
        _p_error(f"An unexpected error occurred while executing command '{display_command_str}': {e}")
        raise