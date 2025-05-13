import shutil
import subprocess # For CalledProcessError, FileNotFoundError, TimeoutExpired

from . import shared_state
from . import utils as command_utils


def install_cargo_tools():
    shared_state.log.info(f"Installing Cargo tools: [cyan]{', '.join(shared_state.CARGO_TOOLS)}[/]...")
    cargo_cmd_path_user = shared_state.TARGET_USER_HOME / ".cargo/bin/cargo"
    effective_cargo_cmd = str(cargo_cmd_path_user) if cargo_cmd_path_user.is_file() else shutil.which("cargo")
    
    if not effective_cargo_cmd:
        shared_state.log.warning("[yellow]Cargo command not found.[/] Cargo is typically installed via rustup (https://rustup.rs). Skipping Cargo tools.")
        return
    
    shared_state.log.info(f"Using cargo: [blue]{effective_cargo_cmd}[/]")
    for tool_name in shared_state.CARGO_TOOLS:
        try:
            list_res = command_utils.run_command([effective_cargo_cmd,"install","--list"],as_user=shared_state.TARGET_USER,capture_output=True,text=True,check=False)
            if list_res.returncode == 0 and f"{tool_name} v" in list_res.stdout:
                shared_state.log.warning(f"Cargo tool '[cyan]{tool_name}[/]' already installed. Skipping."); continue
        except Exception: shared_state.log.debug(f"Cargo list check failed for {tool_name}")
        
        shared_state.log.info(f"Installing '[cyan]{tool_name}[/]' with cargo...")
        with shared_state.console.status(f"[green]Installing {tool_name} with cargo...[/]"):
            try:
                command_utils.run_command([effective_cargo_cmd, "install", tool_name], as_user=shared_state.TARGET_USER)
                shared_state.log.info(f":crates: Cargo tool '[cyan]{tool_name}[/]' installed.")
            except Exception as e_cargo:
                shared_state.log.error(f"[bold red]Failed Cargo tool install '{tool_name}': {e_cargo}[/]")

def install_scripted_tools():
    from .shell_customization import _ensure_zoxide_in_zshrc # Import here to avoid circular dep at module level
    
    for tool_info in shared_state.SCRIPTED_TOOLS:
        name, check_cmd_parts, url, method = tool_info["name"], tool_info["check_command"].split(), tool_info["url"], tool_info["method"]
        shared_state.log.info(f"Scripted tool: '[cyan]{name}[/]'...")

        if command_utils.check_command_exists(check_cmd_parts, as_user=shared_state.TARGET_USER):
            try:
                command_utils.run_command(check_cmd_parts, as_user=shared_state.TARGET_USER, capture_output=True, check=True) # Version check
                shared_state.log.info(f"'[cyan]{name}[/]' already installed & version OK. Skipping."); continue
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                shared_state.log.debug(f"'{name}' found, but version check failed/timed out. Reinstalling.")
            except Exception as e_v_check: shared_state.log.debug(f"Unexpected error in version check for '{name}': {e_v_check}. Reinstalling.")
        else:
            shared_state.log.debug(f"'{name}' not found by check_command_exists. Installing.")

        shared_state.log.info(f"Downloading & running install script for '[cyan]{name}[/]'...")
        cmd_str = f"curl -fsSL {url} | {method}"
        with shared_state.console.status(f"[green]Installing {name}...[/]", spinner="arrow3"):
            try:
                command_utils.run_command(cmd_str, as_user=shared_state.TARGET_USER, shell=True, check=True)
                if command_utils.check_command_exists(check_cmd_parts, as_user=shared_state.TARGET_USER):
                    shared_state.log.info(f":white_check_mark: '[cyan]{name}[/]' installed/updated.")
                    if name == "zoxide":
                        _ensure_zoxide_in_zshrc()
                else:
                    shared_state.log.error(f"[bold red]Install of '{name}' via script might have failed (cmd not found post-install).[/]")
            except Exception as e_script_inst:
                shared_state.log.error(f"[bold red]Scripted install of '{name}' failed: {e_script_inst}[/]")