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
    (Existing run_command function - keep as is)
    """
    _p_info = print_fn_info or PRINT_FN_INFO_DEFAULT
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or PRINT_FN_SUB_STEP_DEFAULT

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
            _p_error("Invalid command type for 'run_as_user'. Must be string or list.")
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
            _p_error("Invalid command type. Must be string or list.")
            raise TypeError("Command must be a string or list of strings.")
    
    _p_info(f"Executing: {display_command_str}")

    try:
        process = subprocess.run(
            command_to_execute,
            check=check,
            capture_output=capture_output,
            text=True,
            shell=effective_shell,
            cwd=str(cwd) if cwd else None,
            env=current_env
        )
        if capture_output:
            if process.stdout and process.stdout.strip():
                stdout_summary = (process.stdout.strip()[:150] + '...') if len(process.stdout.strip()) > 150 else process.stdout.strip()
                _p_sub(f"STDOUT: {stdout_summary}")
            if process.stderr and process.stderr.strip():
                stderr_summary = (process.stderr.strip()[:150] + '...') if len(process.stderr.strip()) > 150 else process.stderr.strip()
                _p_sub(f"STDERR: {stderr_summary}")
        return process
    except subprocess.CalledProcessError as e:
        _p_error(f"Command failed: '{display_command_str}' (Exit code: {e.returncode})")
        if e.stdout:
             _p_error(f"Failed command STDOUT: {e.stdout.strip()}")
        if e.stderr:
             _p_error(f"Failed command STDERR: {e.stderr.strip()}")
        raise
    except FileNotFoundError:
        cmd_part_not_found = ""
        if isinstance(command_to_execute, list) and command_to_execute:
            cmd_part_not_found = command_to_execute[0]
        elif isinstance(command_to_execute, str):
            cmd_part_not_found = command_to_execute.split()[0]
        _p_error(f"Command executable not found: '{cmd_part_not_found}' (Full command attempted: '{display_command_str}')")
        raise
    except Exception as e:
        _p_error(f"An unexpected error occurred while executing command '{display_command_str}': {e}")
        raise

def install_flatpak_apps(
    apps_to_install: Dict[str, str], # {app_id: friendly_name}
    system_wide: bool = True,
    remote_name: str = "flathub",
    print_fn_info: Optional[Callable[[str], None]] = None,
    print_fn_error: Optional[Callable[[str], None]] = None,
    print_fn_sub_step: Optional[Callable[[str], None]] = None
) -> bool:
    """
    Installs a list of Flatpak applications.

    Args:
        apps_to_install: Dictionary of Flatpak applications {app_id: friendly_name}.
        system_wide: If True, install system-wide (requires sudo). Default True.
        remote_name: The Flatpak remote to install from (e.g., "flathub"). Default "flathub".
        print_fn_info: Function for informational messages.
        print_fn_error: Function for error messages.
        print_fn_sub_step: Function for sub-step messages.

    Returns:
        bool: True if all specified apps were installed/updated successfully, False otherwise.
    """
    _p_info = print_fn_info or PRINT_FN_INFO_DEFAULT
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or PRINT_FN_SUB_STEP_DEFAULT

    if not apps_to_install:
        _p_info("No Flatpak applications specified for installation.")
        return True

    overall_success = True
    install_type = "system-wide" if system_wide else "user"
    _p_sub(f"Preparing to install Flatpak applications ({install_type}): {', '.join(apps_to_install.keys())}")

    for app_id, app_name in apps_to_install.items():
        _p_info(f"Installing '{app_name}' ({app_id})...")
        
        cmd_list = []
        if system_wide:
            cmd_list.append("sudo")
        
        cmd_list.extend(["flatpak", "install"])
        
        if system_wide:
            cmd_list.append("--system")
        else:
            cmd_list.append("--user") # For user install
            
        cmd_list.extend(["--noninteractive", "--or-update", remote_name, app_id])
        
        try:
            run_command(
                cmd_list,
                capture_output=True, # Keep output clean unless error
                check=True,          # Raise error on failure
                print_fn_info=_p_info,
                print_fn_error=_p_error,
                print_fn_sub_step=_p_sub
            )
            _p_info(f"Flatpak app '{app_name}' ({app_id}) installed/updated successfully.") # Success per app
        except FileNotFoundError:
            _p_error("'flatpak' command not found. Is Flatpak installed and Flathub remote added (e.g., in Phase 1)?")
            overall_success = False
            break  # Stop if flatpak command is missing
        except subprocess.CalledProcessError: # Error already logged by run_command
            _p_error(f"Failed to install Flatpak app '{app_name}' ({app_id}). Check output above for details.")
            overall_success = False
        except Exception as e: # Catch any other unexpected error during this app's install
            _p_error(f"An unexpected error occurred while installing Flatpak app '{app_name}' ({app_id}): {e}")
            overall_success = False
            
    if overall_success and apps_to_install:
        # This message might be too verbose if printed for each phase.
        # Consider if a summary at the end of the phase is better.
        # For now, let's keep it to confirm the utility function did its job.
        pass # _p_info("All specified Flatpak applications processed.")
    elif not apps_to_install:
        pass # Already handled by the initial check
    else:
        _p_error("Some Flatpak applications could not be installed.")
        
    return overall_success