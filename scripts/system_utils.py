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
    _p_info = print_fn_info or (lambda msg: None) # No-op if not provided, to avoid "Executing..." spam for silent checks
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or (lambda msg: None) # No-op for sub_step if not provided

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
    if print_fn_info and print_fn_info is not PRINT_FN_INFO_DEFAULT: # Only call _p_info if it's not the no-op lambda
         _p_info(f"Executing: {display_command_str}")


    try:
        process = subprocess.run(
            command_to_execute,
            check=False, # We check manually after logging
            capture_output=capture_output,
            text=True,
            shell=effective_shell,
            cwd=str(cwd) if cwd else None,
            env=current_env
        )

        if process.stdout and process.stdout.strip():
            log.debug(f"CMD STDOUT for '{display_command_str}':\n{process.stdout.strip()}")
            if capture_output and print_fn_sub_step and print_fn_sub_step is not PRINT_FN_SUB_STEP_DEFAULT:
                stdout_summary = (process.stdout.strip()[:150] + '...') if len(process.stdout.strip()) > 150 else process.stdout.strip()
                _p_sub(f"STDOUT: {stdout_summary}")

        if process.stderr and process.stderr.strip():
            log.warning(f"CMD STDERR for '{display_command_str}':\n{process.stderr.strip()}")
            if capture_output and print_fn_sub_step and print_fn_sub_step is not PRINT_FN_SUB_STEP_DEFAULT:
                stderr_summary = (process.stderr.strip()[:150] + '...') if len(process.stderr.strip()) > 150 else process.stderr.strip()
                _p_sub(f"STDERR: {stderr_summary}")

        if check and process.returncode != 0:
            raise subprocess.CalledProcessError(
                returncode=process.returncode,
                cmd=process.args, # Use process.args as it's the actual command run
                output=process.stdout,
                stderr=process.stderr
            )

        return process

    except subprocess.CalledProcessError as e:
        log.error(f"Command failed: '{e.cmd}' (Exit code: {e.returncode})") # Use e.cmd
        if e.stdout:
             log.error(f"Failed command STDOUT from exception:\n{e.stdout.strip()}")
        if e.stderr:
             log.error(f"Failed command STDERR from exception:\n{e.stderr.strip()}")
        _p_error(f"Command failed: '{subprocess.list2cmdline(e.cmd) if isinstance(e.cmd, list) else e.cmd}' (Exit code: {e.returncode}). Check logs.")
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
            return None
        try:
            # Verify user exists
            run_command(
                ["id", "-u", target_user],
                capture_output=True, check=True,
                logger=log,
                print_fn_info=None, 
                print_fn_error=_p_error 
            )
            log.info(f"Target user determined: {target_user} (from SUDO_USER with root privileges)")
            return target_user
        except (subprocess.CalledProcessError, FileNotFoundError):
            log.error(f"The user '{target_user}' (from SUDO_USER) does not appear to be a valid system user.")
            _p_error(f"The user '{target_user}' (from SUDO_USER) does not appear to be a valid system user.")
            return None
    else:
        try:
            current_user = os.getlogin()
        except OSError: 
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

# --- DNF Operations ---

def install_dnf_packages(
    packages: List[str],
    allow_erasing: bool = False,
    capture_output: bool = True,
    print_fn_info: Optional[Callable[[str], None]] = PRINT_FN_INFO_DEFAULT,
    print_fn_error: Optional[Callable[[str], None]] = PRINT_FN_ERROR_DEFAULT,
    print_fn_sub_step: Optional[Callable[[str], None]] = PRINT_FN_SUB_STEP_DEFAULT,
    logger: Optional[logging.Logger] = None,
    extra_args: Optional[List[str]] = None
) -> bool:
    log = logger or default_script_logger
    _p_info = print_fn_info or PRINT_FN_INFO_DEFAULT
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or PRINT_FN_SUB_STEP_DEFAULT

    if not packages:
        log.info("No DNF packages specified for installation.")
        _p_info("No DNF packages specified for installation.")
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
    
    log.info(f"{action_verb} DNF packages: {', '.join(packages)}")
    _p_sub(f"{action_verb} DNF packages: {', '.join(packages)}") # Use sub_step for this

    try:
        run_command(
            cmd, capture_output=capture_output, check=True,
            print_fn_info=_p_info, print_fn_error=_p_error, print_fn_sub_step=_p_sub,
            logger=log
        )
        _p_info(f"DNF packages processed successfully: {', '.join(packages)}") # Use info for success
        log.info(f"DNF packages processed successfully: {', '.join(packages)}")
        return True
    except Exception as e:
        log.error(f"Failed to process DNF packages: {packages}. Error: {e}", exc_info=True)
        # _p_error is handled by run_command
        return False

def install_dnf_groups(
    groups: List[str],
    allow_erasing: bool = True, # Group install often benefits from this
    capture_output: bool = True,
    print_fn_info: Optional[Callable[[str], None]] = PRINT_FN_INFO_DEFAULT,
    print_fn_error: Optional[Callable[[str], None]] = PRINT_FN_ERROR_DEFAULT,
    print_fn_sub_step: Optional[Callable[[str], None]] = PRINT_FN_SUB_STEP_DEFAULT,
    logger: Optional[logging.Logger] = None
) -> bool:
    log = logger or default_script_logger
    _p_info = print_fn_info or PRINT_FN_INFO_DEFAULT
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or PRINT_FN_SUB_STEP_DEFAULT

    if not groups:
        log.info("No DNF groups specified for installation.")
        _p_info("No DNF groups specified for installation.")
        return True

    all_successful = True
    log.info(f"Installing DNF groups: {', '.join(groups)}")
    _p_sub(f"Installing DNF groups: {', '.join(groups)}")

    for group_id_or_name in groups:
        cmd = ["sudo", "dnf", "group", "install", "-y"]
        if allow_erasing:
            cmd.append("--allowerasing")
        cmd.append(group_id_or_name)
        
        _p_sub(f"Processing DNF group: {group_id_or_name}")
        try:
            run_command(
                cmd, capture_output=capture_output, check=True,
                print_fn_info=_p_info, print_fn_error=_p_error, print_fn_sub_step=_p_sub,
                logger=log
            )
            _p_info(f"DNF group '{group_id_or_name}' processed successfully.")
            log.info(f"DNF group '{group_id_or_name}' processed successfully.")
        except Exception as e:
            log.error(f"Failed to process DNF group '{group_id_or_name}'. Error: {e}", exc_info=True)
            # _p_error is handled by run_command
            all_successful = False
    return all_successful

def swap_dnf_packages(
    from_pkg: str,
    to_pkg: str,
    allow_erasing: bool = True, # Swap usually needs this
    capture_output: bool = True,
    print_fn_info: Optional[Callable[[str], None]] = PRINT_FN_INFO_DEFAULT,
    print_fn_error: Optional[Callable[[str], None]] = PRINT_FN_ERROR_DEFAULT,
    print_fn_sub_step: Optional[Callable[[str], None]] = PRINT_FN_SUB_STEP_DEFAULT,
    logger: Optional[logging.Logger] = None
) -> bool:
    log = logger or default_script_logger
    _p_info = print_fn_info or PRINT_FN_INFO_DEFAULT
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT
    _p_sub = print_fn_sub_step or PRINT_FN_SUB_STEP_DEFAULT

    if not from_pkg or not to_pkg:
        _p_error("Invalid 'from' or 'to' package name for DNF swap.")
        log.error(f"Invalid DNF swap params: from='{from_pkg}', to='{to_pkg}'")
        return False

    log.info(f"Attempting DNF swap: from '{from_pkg}' to '{to_pkg}'")
    _p_sub(f"Attempting DNF swap: from '{from_pkg}' to '{to_pkg}'")

    try:
        # Check if 'from_pkg' is installed. If not, just install 'to_pkg'.
        check_cmd = ["rpm", "-q", from_pkg]
        check_proc = run_command(
            check_cmd, capture_output=True, check=False, # check=False as non-zero means not installed
            print_fn_info=None, print_fn_error=None, # Be quiet for this check
            logger=log
        )

        if check_proc.returncode != 0:
            _p_info(f"Package '{from_pkg}' is not installed. Attempting direct install of '{to_pkg}'.")
            log.info(f"'{from_pkg}' not installed. Directly installing '{to_pkg}'.")
            return install_dnf_packages(
                [to_pkg], allow_erasing=allow_erasing, capture_output=capture_output,
                print_fn_info=_p_info, print_fn_error=_p_error, print_fn_sub_step=_p_sub,
                logger=log
            )

        cmd = ["sudo", "dnf", "swap", "-y"]
        if allow_erasing:
            cmd.append("--allowerasing")
        cmd.extend([from_pkg, to_pkg])
        
        run_command(
            cmd, capture_output=capture_output, check=True,
            print_fn_info=_p_info, print_fn_error=_p_error, print_fn_sub_step=_p_sub,
            logger=log
        )
        _p_info(f"DNF package '{from_pkg}' successfully swapped with '{to_pkg}'.")
        log.info(f"Successfully swapped '{from_pkg}' with '{to_pkg}'.")
        return True
    except Exception as e:
        log.error(f"Failed DNF swap from '{from_pkg}' to '{to_pkg}'. Error: {e}", exc_info=True)
        # _p_error handled by run_command or the install_dnf_packages call
        return False

def upgrade_system_dnf(
    capture_output: bool = False, # System upgrades are long, usually stream output
    print_fn_info: Optional[Callable[[str], None]] = PRINT_FN_INFO_DEFAULT,
    print_fn_error: Optional[Callable[[str], None]] = PRINT_FN_ERROR_DEFAULT,
    logger: Optional[logging.Logger] = None
) -> bool:
    log = logger or default_script_logger
    _p_info = print_fn_info or PRINT_FN_INFO_DEFAULT
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT

    cmd = ["sudo", "dnf", "upgrade", "-y"]
    log.info("Attempting system upgrade using DNF...")
    _p_info("Attempting system upgrade (sudo dnf upgrade -y)...")
    try:
        run_command(
            cmd, capture_output=capture_output, check=True,
            print_fn_info=_p_info, print_fn_error=_p_error,
            logger=log
        )
        _p_info("System DNF upgrade completed successfully.")
        log.info("System DNF upgrade completed successfully.")
        return True
    except Exception as e:
        log.error(f"System DNF upgrade failed. Error: {e}", exc_info=True)
        return False

def clean_dnf_cache(
    clean_type: str = "all", # "all", "metadata", "packages", etc.
    capture_output: bool = True,
    print_fn_info: Optional[Callable[[str], None]] = PRINT_FN_INFO_DEFAULT,
    print_fn_error: Optional[Callable[[str], None]] = PRINT_FN_ERROR_DEFAULT,
    logger: Optional[logging.Logger] = None
) -> bool:
    log = logger or default_script_logger
    _p_info = print_fn_info or PRINT_FN_INFO_DEFAULT
    _p_error = print_fn_error or PRINT_FN_ERROR_DEFAULT

    cmd = ["sudo", "dnf", "clean", clean_type]
    log.info(f"Attempting to clean DNF cache ({clean_type})...")
    _p_info(f"Attempting to clean DNF cache (sudo dnf clean {clean_type})...")
    try:
        run_command(
            cmd, capture_output=capture_output, check=True,
            print_fn_info=_p_info, print_fn_error=_p_error,
            logger=log
        )
        _p_info(f"DNF cache clean ({clean_type}) completed successfully.")
        log.info(f"DNF cache clean ({clean_type}) completed successfully.")
        return True
    except Exception as e:
        log.error(f"DNF cache clean ({clean_type}) failed. Error: {e}", exc_info=True)
        return False

# --- Flatpak Operations ---

def install_flatpak_apps(
    apps_to_install: Dict[str, str], # app_id: friendly_name
    system_wide: bool = True,
    remote_name: str = "flathub",
    print_fn_info: Optional[Callable[[str], None]] = PRINT_FN_INFO_DEFAULT,
    print_fn_error: Optional[Callable[[str], None]] = PRINT_FN_ERROR_DEFAULT,
    print_fn_sub_step: Optional[Callable[[str], None]] = PRINT_FN_SUB_STEP_DEFAULT,
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
    
    app_names_str = ', '.join(apps_to_install.values())
    log.info(f"Preparing to install Flatpak applications ({install_type}): {app_names_str}")
    _p_sub(f"Preparing to install Flatpak applications ({install_type}): {app_names_str}")

    for app_id, app_name in apps_to_install.items():
        log.info(f"Processing Flatpak app '{app_name}' ({app_id})...")
        _p_sub(f"Installing Flatpak app '{app_name}' ({app_id})...") # Changed to sub_step

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
            _p_info(f"Flatpak app '{app_name}' ({app_id}) installed/updated successfully.") # Use _p_info for final success
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
        log.info("All specified Flatpak applications processed successfully.")
        _p_info("All specified Flatpak applications processed successfully.")
    elif not overall_success:
        log.error("Some Flatpak applications could not be installed.")
        _p_error("Some Flatpak applications could not be installed. Check logs for details.")

    return overall_success