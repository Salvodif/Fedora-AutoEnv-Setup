import shutil
import subprocess # For CalledProcessError, FileNotFoundError, TimeoutExpired

from . import shared_state
from .utils import run_command, check_command_exists

def perform_post_install_checks():
    Console, Panel, Text, _, _, _, _, _, _ = shared_state.get_rich_components()

    shared_state.log.info("Performing post-install checks...")
    tools = ["zsh","git","curl","python3","pip3","eza","dust","btop","bat","fzf","zoxide","atuin","nano", "google-chrome-stable"]
    if shared_state.IS_FEDORA: tools.append("gnome-tweaks") 
    
    report, all_ok = [], True
    for tool in tools:
        run_check_as_user = shared_state.TARGET_USER if tool in ["zoxide", "atuin"] else None
        
        if check_command_exists([tool], as_user=run_check_as_user):
            ver, ver_ok = " (version N/A)", False
            try:
                cmd_for_ver = [tool]
                run_ver_as = run_check_as_user

                for flag in ["--version", "-V", "version"]:
                    cmd_list = cmd_for_ver + ([flag] if flag else [])
                    if tool == "pip3" and flag == "--version": cmd_list = [tool, "show", "pip"]
                    
                    res = run_command(cmd_list, capture_output=True, text=True, check=False, as_user=run_ver_as)
                    if res.returncode == 0 and res.stdout.strip():
                        out_line = res.stdout.strip().splitlines()[0]
                        if tool == "pip3" and "Version:" in res.stdout:
                            out_line = next((l.split(':',1)[1].strip() for l in res.stdout.splitlines() if "Version:" in l),"")
                        ver = f" ([italic]{out_line}[/])"; ver_ok = True; break
                report.append(f":heavy_check_mark: [green]'{tool}' available[/]{ver if ver_ok else ' (version N/A or check failed)'}")
            except Exception: report.append(f":heavy_check_mark: [green]'{tool}' available[/] (version check error)")
        else:
            expected_by_base_dnf = tool in shared_state.DNF_PACKAGES_BASE and shared_state.IS_FEDORA
            expected_by_gnome_mgmt_dnf = tool in shared_state.GNOME_MANAGEMENT_DNF_PACKAGES and shared_state.IS_FEDORA
            expected_by_cargo = tool in shared_state.CARGO_TOOLS
            expected_by_script = any(t['name'] == tool for t in shared_state.SCRIPTED_TOOLS)
            is_fundamental = tool in ["zsh", "git", "curl", "nano", "python3", "pip3", "google-chrome-stable"]
            
            is_expected = expected_by_base_dnf or expected_by_gnome_mgmt_dnf or expected_by_cargo or expected_by_script or is_fundamental
            
            if is_expected:
                report.append(f":x: [bold red]'{tool}' FAILED to be found (expected).[/]"); all_ok = False
            else:
                report.append(f":warning: [yellow]'{tool}' not found (may not be expected by this script).[/]")
    
    shared_state.console.print(Panel("\n".join(report), title="[bold]Post-Installation Check Summary[/]", border_style="blue", expand=False))
    if all_ok: shared_state.log.info("[bold green]Critical post-install checks passed.[/]")
    else: shared_state.log.warning("Some post-install checks failed. Review summary/logs.")