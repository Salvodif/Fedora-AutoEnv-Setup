import os # Necessario per os.chown
import pwd # Necessario per pwd.getpwnam
import shutil
import subprocess # Per CalledProcessError, FileNotFoundError, TimeoutExpired
import shlex 

from . import shared_state
from . import utils as command_utils 

def _ensure_path_in_shell_rc(rc_path: Path, path_to_add: str, tool_name_for_comment: str):
    """
    Helper function to append a PATH export to a shell rc file if not already present.
    Uses $HOME in path_to_add for portability within the rc file.
    Example path_to_add: "$HOME/.local/bin"
    """
    if not rc_path.is_file():
        shared_state.log.warning(f"Shell rc file [magenta]{rc_path}[/] not found. Cannot add PATH for {tool_name_for_comment}.")
        return

    # La linea esatta da cercare e aggiungere
    # Assicurati che path_to_add usi $HOME e non il valore espanso di TARGET_USER_HOME
    # per renderlo portabile e corretto all'interno del file rc.
    path_export_line = f'export PATH="{path_to_add}:$PATH"'
    comment_line = f"# Added by Nova Setup for {tool_name_for_comment}"
    
    try:
        content = rc_path.read_text(encoding='utf-8')
        # Controlla se una linea simile (ignorando il commento) è già presente
        # per evitare di aggiungere la stessa logica di PATH più volte.
        # Questo è un check semplice; potrebbe essere reso più robusto.
        if path_export_line not in content:
            shared_state.log.info(f"Adding to PATH in [magenta]{rc_path}[/]: '{path_to_add}' for {tool_name_for_comment}")
            with open(rc_path, "a", encoding='utf-8') as f:
                f.write(f"\n{comment_line}\n{path_export_line}\n")
            
            # Lo script è eseguito come root, quindi shutil.copy ha creato il file come root.
            # O se il file rc esisteva, root ha appena appeso ad esso.
            # Dobbiamo ripristinare la proprietà a TARGET_USER.
            pw_info = pwd.getpwnam(shared_state.TARGET_USER)
            os.chown(rc_path, pw_info.pw_uid, pw_info.pw_gid)
            shared_state.log.info(f"PATH entry for {tool_name_for_comment} appended to [magenta]{rc_path}[/] and ownership set to {shared_state.TARGET_USER}.")
        else:
            shared_state.log.info(f"PATH entry for '{path_to_add}' seems to be already present in [magenta]{rc_path}[/].")
    except Exception as e:
        shared_state.log.error(f"[bold red]Error updating [magenta]{rc_path}[/] for {tool_name_for_comment} PATH: {e}[/]")


def install_cargo_tools():
    shared_state.log.info(f"Attempting to install Cargo tools: [cyan]{', '.join(shared_state.CARGO_TOOLS)}[/]...")
    effective_cargo_cmd = None
    cargo_path_user_str = str(shared_state.TARGET_USER_HOME / ".cargo/bin/cargo")

    if command_utils.check_command_exists([cargo_path_user_str], as_user=shared_state.TARGET_USER):
        effective_cargo_cmd = cargo_path_user_str
        shared_state.log.info(f"Found user-specific cargo at: [blue]{effective_cargo_cmd}[/]")
    elif command_utils.check_command_exists(["cargo"], as_user=shared_state.TARGET_USER):
        effective_cargo_cmd = "cargo"
        shared_state.log.info(f"Found 'cargo' in PATH for user {shared_state.TARGET_USER}.")
    else:
        cargo_root_path = shutil.which("cargo")
        if cargo_root_path:
            effective_cargo_cmd = cargo_root_path
            shared_state.log.warning(f"Using system/root cargo at [blue]{effective_cargo_cmd}[/].")
    
    if not effective_cargo_cmd:
        shared_state.log.warning("[yellow]Cargo command not found.[/] Skipping Cargo tools.")
        return
    
    shared_state.log.info(f"Attempting to use cargo executable: [blue]{effective_cargo_cmd}[/]")
    cargo_tools_installed_by_script = False
    for tool_name in shared_state.CARGO_TOOLS:
        # ... (resto della logica di installazione del tool come prima, ma imposta cargo_tools_installed_by_script = True se qualcosa viene installato)
        shared_state.log.info(f"Processing Cargo tool: [cyan]{tool_name}[/]")
        try:
            list_res = command_utils.run_command(
                [effective_cargo_cmd, "install", "--list"],
                as_user=shared_state.TARGET_USER,
                capture_output=True, text=True, check=False, timeout=60
            )
            if list_res.returncode == 0 and f"{tool_name} v" in list_res.stdout:
                shared_state.log.info(f"Cargo tool '[cyan]{tool_name}[/]' already installed for {shared_state.TARGET_USER}. Skipping.")
                cargo_tools_installed_by_script = True # Consideralo come se fosse stato "gestito"
                continue
        except Exception as e_list:
            shared_state.log.debug(f"Cargo list check for '{tool_name}' failed: {e_list}")

        shared_state.log.info(f"Attempting to install '[cyan]{tool_name}[/]' with cargo for {shared_state.TARGET_USER}...")
        with shared_state.console.status(f"[green]Installing {tool_name} for {shared_state.TARGET_USER}...[/]", spinner="bouncingBar"):
            try:
                command_utils.run_command(
                    [effective_cargo_cmd, "install", tool_name],
                    as_user=shared_state.TARGET_USER, check=True, capture_output=True, text=True, timeout=600
                )
                shared_state.log.info(f":crates: Cargo tool '[cyan]{tool_name}[/]' installed for {shared_state.TARGET_USER}.")
                cargo_tools_installed_by_script = True
            except Exception as e_install_cargo:
                shared_state.log.error(f"[bold red]Failed to install Cargo tool '{tool_name}' for {shared_state.TARGET_USER}: {e_install_cargo}[/]")
    
    if cargo_tools_installed_by_script: # Se abbiamo interagito con cargo (installato o verificato tool)
        zshrc_user_path = shared_state.TARGET_USER_HOME / ".zshrc"
        cargo_bin_path_for_rc = f"$HOME/.cargo/bin" # Usa $HOME per il file rc
        _ensure_path_in_shell_rc(zshrc_user_path, cargo_bin_path_for_rc, "Cargo binaries")


def install_scripted_tools():
    from .shell_customization import _ensure_zoxide_in_zshrc 
    
    zshrc_user_path = shared_state.TARGET_USER_HOME / ".zshrc"

    for tool_info in shared_state.SCRIPTED_TOOLS:
        name = tool_info["name"]
        check_cmd_parts = shlex.split(tool_info["check_command"])
        url = tool_info["url"]
        method = tool_info["method"]

        shared_state.log.info(f"Processing scripted tool: '[cyan]{name}[/]'...")
        
        if command_utils.check_command_exists(check_cmd_parts, as_user=shared_state.TARGET_USER):
            try:
                command_utils.run_command(check_cmd_parts, as_user=shared_state.TARGET_USER, capture_output=True, check=True, timeout=15)
                shared_state.log.info(f"'[cyan]{name}[/]' already installed and version check OK for {shared_state.TARGET_USER}. Skipping.")
                # Assicurati che il PATH sia comunque aggiunto se il tool è già installato ma il PATH manca
                if name == "atuin":
                    _ensure_path_in_shell_rc(zshrc_user_path, f"$HOME/.atuin/bin", "Atuin")
                # Zoxide gestisce il suo init in modo diverso (_ensure_zoxide_in_zshrc)
                continue
            except Exception as e_v_check:
                shared_state.log.debug(f"'{name}' found for {shared_state.TARGET_USER}, but version check failed: {e_v_check}. Reinstalling.")
        else:
            shared_state.log.debug(f"'{name}' not found by check_command_exists for {shared_state.TARGET_USER}. Installing.")
        
        shared_state.log.info(f"Downloading and executing install script for '[cyan]{name}[/]' for {shared_state.TARGET_USER}...")
        install_cmd_str = f"curl -fsSL {url} | {method}"
        
        with shared_state.console.status(f"[green]Installing {name} via script for {shared_state.TARGET_USER}...[/]", spinner="arrow3"):
            try:
                command_utils.run_command(install_cmd_str, as_user=shared_state.TARGET_USER, shell=True, check=True, timeout=300)
                if command_utils.check_command_exists(check_cmd_parts, as_user=shared_state.TARGET_USER):
                    shared_state.log.info(f":white_check_mark: '[cyan]{name}[/]' installed/updated for {shared_state.TARGET_USER}.")
                    if name == "zoxide":
                        _ensure_zoxide_in_zshrc()
                    elif name == "atuin":
                        _ensure_path_in_shell_rc(zshrc_user_path, f"$HOME/.atuin/bin", "Atuin")
                else:
                    shared_state.log.error(f"[bold red]Install of '{name}' for {shared_state.TARGET_USER} via script might have failed (cmd not found after install).[/]")
            except Exception as e_script_inst:
                shared_state.log.error(f"[bold red]Scripted install of '{name}' for {shared_state.TARGET_USER} failed: {e_script_inst}[/]")

    # Alla fine, assicurati che $HOME/.local/bin sia nel PATH
    # Questo è un percorso comune per molti installer basati su script.
    local_bin_path_for_rc = f"$HOME/.local/bin"
    _ensure_path_in_shell_rc(zshrc_user_path, local_bin_path_for_rc, "User local binaries")