import shutil
import subprocess # For CalledProcessError, FileNotFoundError, TimeoutExpired

from . import shared_state
from . import utils as command_utils # Usa l'alias per coerenza

def perform_post_install_checks(check_gnome_specific_tools: bool = False):
    # Ottieni le CLASSI dei componenti Rich da shared_state
    # Useremo Panel_cls per creare un'istanza di Panel
    _, Panel_cls, _, _, _, _, _, _, _ = shared_state.get_rich_components()

    shared_state.log.info("Performing post-installation checks...")
    
    # Lista base di strumenti da controllare sempre
    tools_to_verify = [
        "zsh", "git", "curl", "python3", "pip3", 
        "eza", "dust", "btop", "bat", "fzf", 
        "zoxide", "atuin", "nano", "google-chrome-stable"
    ]
    
    # Se richiesto e se siamo su Fedora, aggiungi gli strumenti specifici di GNOME
    if check_gnome_specific_tools and shared_state.IS_FEDORA:
        shared_state.log.info("Including GNOME specific tools in post-install check...")
        # Aggiungi solo quelli non già presenti per evitare duplicati
        for gnome_tool in shared_state.GNOME_MANAGEMENT_DNF_PACKAGES:
            if gnome_tool not in tools_to_verify:
                tools_to_verify.append(gnome_tool)
    
    report_lines, all_tools_ok = [], True

    for tool_name_check in tools_to_verify:
        # Determina se il check per questo tool deve essere eseguito come TARGET_USER
        # Questo è importante per i tool installati in user-space (es. zoxide, atuin)
        run_check_as_user = shared_state.TARGET_USER if tool_name_check in ["zoxide", "atuin"] else None
        
        tool_exists = command_utils.check_command_exists([tool_name_check], as_user=run_check_as_user)
        
        if tool_exists:
            version_str, version_checked_ok = " (version N/A)", False
            # Per il version check, se il comando esiste, proviamo ad eseguirlo.
            # L'utente per l'esecuzione del version check dovrebbe essere lo stesso usato per check_command_exists
            # o None se è un comando di sistema.
            user_for_version_check = run_check_as_user 

            try:
                cmd_for_ver = [tool_name_check] # Il comando è il nome del tool stesso
                for v_flag_opt in ["--version", "-V", "version"]:
                    cmd_list_ver = cmd_for_ver + [v_flag_opt] # Crea la lista di comando completa
                    # Gestione speciale per pip3
                    if tool_name_check == "pip3" and v_flag_opt == "--version":
                        cmd_list_ver = [tool_name_check, "show", "pip"]
                    
                    res_ver = command_utils.run_command(cmd_list_ver, capture_output=True, text=True, check=False, as_user=user_for_version_check)
                    if res_ver.returncode == 0 and res_ver.stdout.strip():
                        output_first_line = res_ver.stdout.strip().splitlines()[0]
                        if tool_name_check == "pip3" and "Version:" in res_ver.stdout:
                            output_first_line = next((line.split(':',1)[1].strip() for line in res_ver.stdout.splitlines() if "Version:" in line),"")
                        version_str = f" ([italic]{output_first_line}[/])"
                        version_checked_ok = True
                        break # Trovata versione, esci dal loop dei flag
                
                if version_checked_ok:
                    report_lines.append(f":heavy_check_mark: [green]Tool '[cyan]{tool_name_check}[/]' is available[/]{version_str}")
                else:
                    report_lines.append(f":heavy_check_mark: [green]Tool '[cyan]{tool_name_check}[/]' is available[/] (version check failed or no output)")
            except Exception as e_ver: 
                report_lines.append(f":heavy_check_mark: [green]Tool '[cyan]{tool_name_check}[/]' is available[/] (unexpected error during version check: {e_ver})")
        
        else: # Tool not found by check_command_exists
            # Determina se questo tool era atteso
            is_expected = False
            if tool_name_check in shared_state.DNF_PACKAGES_BASE and shared_state.IS_FEDORA:
                is_expected = True
            elif tool_name_check in shared_state.GNOME_MANAGEMENT_DNF_PACKAGES and shared_state.IS_FEDORA and check_gnome_specific_tools:
                # Expected solo se stiamo controllando specificamente gli strumenti GNOME
                is_expected = True
            elif tool_name_check in shared_state.CARGO_TOOLS:
                is_expected = True
            elif any(t['name'] == tool_name_check for t in shared_state.SCRIPTED_TOOLS):
                is_expected = True
            elif tool_name_check in ["zsh", "git", "curl", "nano", "python3", "pip3", "google-chrome-stable"]: # Fondamentali
                is_expected = True
            
            if is_expected:
                report_lines.append(f":x: [bold red]Tool '[cyan]{tool_name_check}[/]' FAILED to be found (was expected).[/]")
                all_tools_ok = False
            else:
                # Se non era atteso in questo specifico scenario (es. gnome-tweaks durante l'opzione 1)
                report_lines.append(f":information_source: [dim]Tool '[cyan]{tool_name_check}[/]' not found (not necessarily expected in this step).[/]")
    
    shared_state.console.print(Panel_cls("\n".join(report_lines), title="[bold]Post-Installation Check Summary[/]", border_style="blue", expand=False))
    if all_tools_ok:
        shared_state.log.info("[bold green]All checked tools relevant to this step seem to be available.[/]")
    else:
        shared_state.log.warning("[bold yellow]Some expected tools were NOT found. Please review the summary and logs.[/]")