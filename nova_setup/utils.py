import os
import shlex
import subprocess
import pwd
from pathlib import Path
from typing import List, Optional
import logging as std_logging # Fallback logger, se shared_state.log non è ancora pronto

from . import shared_state

def run_command(command: List[str] | str,
                check: bool = True,
                capture_output: bool = False,
                text: bool = True,
                as_user: Optional[str] = None,
                shell: bool = False,
                cwd: Optional[Path] = None,
                timeout: Optional[int] = 300) -> subprocess.CompletedProcess: # Default 5 min timeout
    """
    Runs a command, optionally as a different user, with logging and error handling.
    """
    cmd_for_log = command if isinstance(command, str) else ' '.join(shlex.quote(str(s)) for s in command)
    
    # Utilizza il logger globale da shared_state se inizializzato, altrimenti un fallback.
    # Questo è per la robustezza durante le fasi iniziali di importazione, sebbene
    # idealmente shared_state.log dovrebbe essere sempre disponibile quando questa funzione viene chiamata.
    logger = shared_state.log if shared_state.log else std_logging.getLogger("utils-fallback")
    logger.debug(f"Executing: {cmd_for_log}{f' as {as_user}' if as_user else ''}{f' in {cwd}' if cwd else ''}")

    final_command_parts: List[str] = []
    actual_command_to_run: List[str] | str

    if as_user:
        final_command_parts.extend(["sudo", "-u", as_user])
        if shell:
            # Se shell=True e as_user, eseguiamo il comando all'interno della shell interattiva (-i) dell'utente.
            # Questo aiuta a caricare il profilo dell'utente (es. .bashrc, .zshrc) e quindi il suo PATH.
            pw_entry = pwd.getpwnam(as_user)
            user_shell = pw_entry.pw_shell
            if not user_shell or not Path(user_shell).is_file(): # Fallback se la shell non è valida
                user_shell = "/bin/bash" 
            
            cmd_str_to_embed = command if isinstance(command, str) else " ".join(shlex.quote(str(s)) for s in command)
            
            # Costruisci il comando da passare a `sudo -u user <shell> -ic "..."`
            final_command_parts.extend([user_shell, "-ic", cmd_str_to_embed])
            actual_command_to_run = final_command_parts
            shell = False # La shell dell'utente interpreterà il comando, non la shell esterna di subprocess.
        else:
            # Per comandi non-shell eseguiti come utente
            final_command_parts.extend(command if isinstance(command, list) else [command])
            actual_command_to_run = final_command_parts
    else: # Esecuzione come root
        actual_command_to_run = command

    try:
        process_env = os.environ.copy()
        if as_user and not shell: # Per comandi non-shell as_user, imposta comunque l'ambiente D-Bus
            pw_entry = pwd.getpwnam(as_user)
            process_env['HOME'] = pw_entry.pw_dir
            process_env['USER'] = as_user
            process_env['LOGNAME'] = as_user
            try:
                # Tenta di ottenere DBUS_SESSION_BUS_ADDRESS per comandi GUI/sessione
                dbus_address_cmd = f"systemctl --user -M {shlex.quote(as_user)}@.service show-environment"
                res_dbus = subprocess.run(shlex.split(dbus_address_cmd), capture_output=True, text=True, check=False, timeout=5)
                if res_dbus.returncode == 0:
                    for line_env in res_dbus.stdout.splitlines():
                        if line_env.startswith("DBUS_SESSION_BUS_ADDRESS="):
                            process_env['DBUS_SESSION_BUS_ADDRESS'] = line_env.split('=', 1)[1]
                            logger.debug(f"Set DBUS_SESSION_BUS_ADDRESS for {as_user} via systemctl.")
                            break
                elif Path(f"/run/user/{pw_entry.pw_uid}/bus").exists(): # Fallback a un percorso comune
                     process_env['DBUS_SESSION_BUS_ADDRESS'] = f"unix:path=/run/user/{pw_entry.pw_uid}/bus"
                     logger.debug(f"Set DBUS_SESSION_BUS_ADDRESS for {as_user} via common path.")
            except Exception as e_dbus:
                logger.debug(f"DBUS address for {as_user} could not be set: {e_dbus}. GUI commands might fail.")

        result = subprocess.run(
            actual_command_to_run, check=check, capture_output=capture_output, text=text,
            shell=shell, cwd=cwd, env=process_env, timeout=timeout
        )
        return result
    except subprocess.TimeoutExpired as e_timeout:
        # Componi il comando per il log in modo più sicuro
        cmd_str_err_timeout = ' '.join(map(str, e_timeout.cmd)) if isinstance(e_timeout.cmd, list) else str(e_timeout.cmd)
        logger.error(f"Command '[bold cyan]{cmd_str_err_timeout}[/]' timed out after {e_timeout.timeout}s.")
        raise
    except subprocess.CalledProcessError as e_call:
        cmd_str_err_call = ' '.join(map(str, e_call.cmd)) if isinstance(e_call.cmd, list) else str(e_call.cmd)
        logger.error(f"Command '[bold cyan]{cmd_str_err_call}[/]' failed (code {e_call.returncode}).")
        if capture_output: # Logga stdout/stderr solo se sono stati catturati
            if e_call.stdout: logger.error(f"[stdout]: {e_call.stdout.strip()}")
            if e_call.stderr: logger.error(f"[stderr]: {e_call.stderr.strip()}")
        raise
    except FileNotFoundError:
        # Determina il nome del comando che non è stato trovato
        cmd_failed_fnf = "UnknownCmd"
        if isinstance(actual_command_to_run, str):
            cmd_failed_fnf = actual_command_to_run.split()[0]
        elif isinstance(actual_command_to_run, list) and actual_command_to_run:
            cmd_failed_fnf = actual_command_to_run[0]
        logger.error(f"Command not found: {cmd_failed_fnf}")
        raise
    except Exception as e_general: # Cattura altre eccezioni impreviste
        logger.error(f"An unexpected error occurred in run_command: {e_general}")
        raise


def check_command_exists(command_name_parts: List[str] | str, as_user: Optional[str] = None) -> bool:
    """
    Checks if a command exists, optionally for a specific user, using their interactive shell.
    """
    cmd_to_verify = command_name_parts[0] if isinstance(command_name_parts, list) else command_name_parts.split()[0]
    
    # Il comando interno da eseguire per verificare l'esistenza del tool
    check_cmd_str_inner = f"command -v {shlex.quote(cmd_to_verify)}"
    
    try:
        # Se `as_user` è specificato, `run_command` con `shell=True` eseguirà:
        # `sudo -u <user> <user_shell> -ic "command -v <tool_to_verify>"`
        # che usa la PATH e l'ambiente della shell interattiva dell'utente.
        # Se `as_user` è None, `run_command` con `shell=True` eseguirà:
        # `/bin/sh -c "command -v <tool_to_verify>"` (come root)
        run_command(check_cmd_str_inner, as_user=as_user, shell=True, capture_output=True, check=True, timeout=10) # Timeout breve per un check
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        # Questi errori indicano che il comando non è stato trovato o il check è fallito/timeout
        return False
    except Exception as e_unexp_check:
        # Logga errori imprevisti durante il check, ma considera il comando come non esistente
        logger = shared_state.log if shared_state.log else std_logging.getLogger("utils-fallback")
        logger.debug(f"Unexpected error in check_command_exists for '{cmd_to_verify}': {e_unexp_check}")
        return False