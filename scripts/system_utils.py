# Fedora-AutoEnv-Setup/scripts/system_utils.py

import subprocess
import os
import shlex
import sys
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
    _p_info = print_fn_info or (lambda msg: None)
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or (lambda msg: None)

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
            log.error("Invalid command type. Must be string or list.")
            _p_error("Invalid command type. Must be string or list.")
            raise TypeError("Command must be a string or list of strings.")

    log.info(f"Executing: {display_command_str}")
    if print_fn_info: # Only call _p_info if it's not the no-op lambda
        _p_info(f"Executing: {display_command_str}")


    try:
        process = subprocess.run(
            command_to_execute,
            check=False,
            capture_output=capture_output,
            text=True,
            shell=effective_shell,
            cwd=str(cwd) if cwd else None,
            env=current_env
        )

        if process.stdout and process.stdout.strip():
            log.debug(f"CMD STDOUT for '{display_command_str}':\n{process.stdout.strip()}")
            if capture_output and print_fn_sub_step:
                stdout_summary = (process.stdout.strip()[:150] + '...') if len(process.stdout.strip()) > 150 else process.stdout.strip()
                _p_sub(f"STDOUT: {stdout_summary}")

        if process.stderr and process.stderr.strip():
            log.warning(f"CMD STDERR for '{display_command_str}':\n{process.stderr.strip()}")
            if capture_output and print_fn_sub_step:
                stderr_summary = (process.stderr.strip()[:150] + '...') if len(process.stderr.strip()) > 150 else process.stderr.strip()
                _p_sub(f"STDERR: {stderr_summary}")

        if check and process.returncode != 0:
            raise subprocess.CalledProcessError(
                returncode=process.returncode,
                cmd=process.args,
                output=process.stdout,
                stderr=process.stderr
            )

        return process

    except subprocess.CalledProcessError as e:
        log.error(f"Command failed: '{display_command_str}' (Exit code: {e.returncode})")
        if e.stdout:
             log.error(f"Failed command STDOUT from exception:\n{e.stdout.strip()}")
        if e.stderr:
             log.error(f"Failed command STDERR from exception:\n{e.stderr.strip()}")
        _p_error(f"Command failed: '{display_command_str}' (Exit code: {e.returncode}). Check logs.")
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

def get_target_user(
    logger: Optional[logging.Logger] = None,
    print_fn_info: Optional[Callable[[str], None]] = None,
    print_fn_error: Optional[Callable[[str], None]] = None,
    print_fn_warning: Optional[Callable[[str], None]] = None
) -> Optional[str]:
    """
    Determines the target user, typically from SUDO_USER when script is run as root.
    If not root, returns the current login user.
    """
    log = logger or default_script_logger
    # Use default print functions from system_utils if specific ones aren't provided
    _p_info = print_fn_info or (lambda msg: None) # No-op if not provided for info
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_warning = print_fn_warning or PRINT_FN_WARNING_DEFAULT

    if os.geteuid() == 0: # Script is running as root
        target_user = os.environ.get("SUDO_USER")
        if not target_user:
            log.error("Script is running as root, but SUDO_USER environment variable is not set.")
            _p_error(
                "Script is running as root, but SUDO_USER environment variable is not set. "
                "Cannot determine the target user."
            )
            # Optional: _p_info("Tip: Run 'sudo ./install.py' from a regular user account.")
            return None
        try:
            # Verify user exists
            run_command(
                ["id", "-u", target_user],
                capture_output=True, check=True,
                logger=log,
                print_fn_info=None, # Suppress "Executing..." for this internal check
                print_fn_error=_p_error # Pass error func for run_command's own error reporting
            )
            log.info(f"Target user determined: {target_user} (from SUDO_USER with root privileges)")
            return target_user
        except (subprocess.CalledProcessError, FileNotFoundError):
            log.error(f"The user '{target_user}' (from SUDO_USER) does not appear to be a valid system user.")
            _p_error(f"The user '{target_user}' (from SUDO_USER) does not appear to be a valid system user.")
            return None
    else:
        # If not root, assume current user is the target.
        try:
            current_user = os.getlogin()
        except OSError: # os.getlogin() can fail if not connected to a tty (e.g. cron)
            import pwd
            try:
                current_user = pwd.getpwuid(os.getuid())[0]
                log.info(f"os.getlogin() failed, using UID's username: {current_user}")
            except Exception as e_pwd:
                log.error(f"Could not determine current user: os.getlogin() failed and pwd.getpwuid() failed: {e_pwd}")
                _p_error("Could not determine current user.")
                return None

        log.warning(
            f"Script is not running as root. Operations will target the current user ({current_user})."
        )
        _p_warning(
             f"Script is not running as root. Operations will target the current user ({current_user})."
        )
        return current_user

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
                logger=log
            )
            _p_info(f"Flatpak app '{app_name}' ({app_id}) installed/updated successfully.")
            log.info(f"Flatpak app '{app_name}' ({app_id}) installed/updated successfully.")
        except FileNotFoundError:
            log.error("'flatpak' command not found. Is Flatpak installed and Flathub remote added?", exc_info=True)
            _p_error("'flatpak' command not found. Is Flatpak installed and Flathub remote added (e.g., in Phase 1)?")
            overall_success = False; break
        except subprocess.CalledProcessError:
            log.error(f"Failed to install Flatpak app '{app_name}' ({app_id}). See previous errors from run_command.")
            # _p_error already called by run_command
            overall_success = False
        except Exception as e:
            log.error(f"An unexpected error occurred while installing Flatpak app '{app_name}' ({app_id}): {e}", exc_info=True)
            _p_error(f"An unexpected error occurred while installing Flatpak app '{app_name}' ({app_id}).")
            overall_success = False

    if overall_success and apps_to_install:
        log.info("All specified Flatpak applications processed.")
    elif not overall_success:
        log.error("Some Flatpak applications could not be installed.")
        # _p_error already called for specific failures

    return overall_success