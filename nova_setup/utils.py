import os
import shlex
import subprocess
import pwd
from pathlib import Path
from typing import List, Optional
import logging as std_logging # Fallback logger

from . import shared_state

def run_command(command: List[str] | str,
                check: bool = True,
                capture_output: bool = False,
                text: bool = True,
                as_user: Optional[str] = None,
                shell: bool = False,
                cwd: Optional[Path] = None,
                timeout: Optional[int] = 300) -> subprocess.CompletedProcess:
    cmd_for_log = command if isinstance(command, str) else ' '.join(shlex.quote(str(s)) for s in command)
    
    logger = shared_state.log if shared_state.log else std_logging.getLogger("utils-fallback")
    logger.debug(f"Executing: {cmd_for_log}{f' as {as_user}' if as_user else ''}{f' in {cwd}' if cwd else ''}")

    final_command_parts: List[str] = []
    actual_command_to_run: List[str] | str

    if as_user:
        final_command_parts.extend(["sudo", "-u", as_user])
        if shell:
            pw_entry = pwd.getpwnam(as_user)
            user_shell = pw_entry.pw_shell or "/bin/bash" 
            cmd_str_to_embed = command if isinstance(command, str) else " ".join(shlex.quote(str(s)) for s in command)
            final_command_parts.extend([user_shell, "-ic", cmd_str_to_embed])
            actual_command_to_run = final_command_parts
            shell = False 
        else:
            final_command_parts.extend(command if isinstance(command, list) else [command])
            actual_command_to_run = final_command_parts
    else: 
        actual_command_to_run = command

    try:
        process_env = os.environ.copy()
        if as_user and not shell: 
            pw_entry = pwd.getpwnam(as_user)
            process_env['HOME'] = pw_entry.pw_dir
            process_env['USER'] = as_user
            process_env['LOGNAME'] = as_user
            try: 
                dbus_address_cmd = f"systemctl --user -M {shlex.quote(as_user)}@.service show-environment"
                res_dbus = subprocess.run(shlex.split(dbus_address_cmd), capture_output=True, text=True, check=False, timeout=5)
                if res_dbus.returncode == 0:
                    for line_env in res_dbus.stdout.splitlines():
                        if line_env.startswith("DBUS_SESSION_BUS_ADDRESS="):
                            process_env['DBUS_SESSION_BUS_ADDRESS'] = line_env.split('=', 1)[1]
                            logger.debug(f"Set DBUS_SESSION_BUS_ADDRESS for {as_user} via systemctl.")
                            break
                elif Path(f"/run/user/{pw_entry.pw_uid}/bus").exists(): 
                     process_env['DBUS_SESSION_BUS_ADDRESS'] = f"unix:path=/run/user/{pw_entry.pw_uid}/bus"
                     logger.debug(f"Set DBUS_SESSION_BUS_ADDRESS for {as_user} via common path.")
            except Exception as e_dbus: logger.debug(f"DBUS address for {as_user} not set: {e_dbus}.")

        result = subprocess.run(
            actual_command_to_run, check=check, capture_output=capture_output, text=text,
            shell=shell, cwd=cwd, env=process_env, timeout=timeout
        )
        return result
    except subprocess.TimeoutExpired as e_timeout:
        cmd_str_err_timeout = ' '.join(e_timeout.cmd) if isinstance(e_timeout.cmd, list) else e_timeout.cmd
        logger.error(f"Command '[bold cyan]{cmd_str_err_timeout}[/]' timed out after {e_timeout.timeout}s.")
        raise
    except subprocess.CalledProcessError as e_call:
        cmd_str_err_call = ' '.join(e_call.cmd) if isinstance(e_call.cmd, list) else e_call.cmd
        logger.error(f"Command '[bold cyan]{cmd_str_err_call}[/]' failed (code {e_call.returncode}).")
        if capture_output: 
            if e_call.stdout: logger.error(f"[stdout]: {e_call.stdout.strip()}")
            if e_call.stderr: logger.error(f"[stderr]: {e_call.stderr.strip()}")
        raise
    except FileNotFoundError:
        cmd_failed_fnf = "UnknownCmd"
        if isinstance(actual_command_to_run, str):
            cmd_failed_fnf = actual_command_to_run.split()[0]
        elif isinstance(actual_command_to_run, list) and actual_command_to_run:
            cmd_failed_fnf = actual_command_to_run[0]
        logger.error(f"Command not found: {cmd_failed_fnf}")
        raise

def check_command_exists(command_name_parts: List[str] | str, as_user: Optional[str] = None) -> bool:
    cmd_to_verify = command_name_parts[0] if isinstance(command_name_parts, list) else command_name_parts.split()[0]
    if as_user:
        check_cmd_str_inner = f"command -v {shlex.quote(cmd_to_verify)}"
        try:
            run_command(check_cmd_str_inner, as_user=as_user, shell=True, capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
    else: 
        try:
            check_cmd_str_root = f"command -v {shlex.quote(cmd_to_verify)}"
            run_command(check_cmd_str_root, shell=True, capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
