from . import shared_state
from . import utils as command_utils 

def perform_post_install_checks(check_gnome_specific_tools: bool = False):
    _, Panel_cls, _, _, _, _, _, _, _ = shared_state.get_rich_components() # Ottieni Panel_cls

    shared_state.log.info("Performing post-installation checks...")
    
    tools_to_verify = [
        "zsh", "git", "curl", "python3", "pip3", 
        "eza", "dust", "btop", "bat", "fzf", 
        "zoxide", "atuin", "nano", "google-chrome-stable"
    ]
    
    if check_gnome_specific_tools and shared_state.IS_FEDORA:
        shared_state.log.info("Including GNOME specific tools in post-install check...")
        for gnome_tool in shared_state.GNOME_MANAGEMENT_DNF_PACKAGES:
            if gnome_tool not in tools_to_verify:
                tools_to_verify.append(gnome_tool)
    
    report_lines, all_tools_ok = [], True

    for tool_name_check in tools_to_verify:
        user_to_run_check_as = None
        if tool_name_check in ["zoxide", "atuin"] or tool_name_check in shared_state.CARGO_TOOLS:
            user_to_run_check_as = shared_state.TARGET_USER
        
        tool_exists = command_utils.check_command_exists([tool_name_check], as_user=user_to_run_check_as)

        actual_cmd_for_version = [tool_name_check]

        if not tool_exists and user_to_run_check_as == shared_state.TARGET_USER:
            possible_paths = []
            if tool_name_check in shared_state.CARGO_TOOLS:
                possible_paths.append(shared_state.TARGET_USER_HOME / ".cargo" / "bin" / tool_name_check)
            if tool_name_check == "zoxide" or tool_name_check == "atuin":
                possible_paths.append(shared_state.TARGET_USER_HOME / ".local" / "bin" / tool_name_check)
                if tool_name_check == "atuin":
                    possible_paths.append(shared_state.TARGET_USER_HOME / ".atuin" / "bin" / tool_name_check)

            for p_path in possible_paths:
                if command_utils.check_command_exists([str(p_path)], as_user=user_to_run_check_as):
                    tool_exists = True
                    actual_cmd_for_version = [str(p_path)]
                    shared_state.log.debug(f"Found '{tool_name_check}' via explicit path: {p_path}")
                    break

        if tool_exists:
            version_str, version_checked_ok = " (version N/A)", False
            try:
                for v_flag_opt in ["--version", "-V", "version"]:
                    cmd_list_ver = actual_cmd_for_version + [v_flag_opt]
                    if tool_name_check == "pip3" and v_flag_opt == "--version":
                        cmd_list_ver = actual_cmd_for_version[:1] + ["show", "pip"]
                    
                    res_ver = command_utils.run_command(cmd_list_ver, capture_output=True, text=True, check=False, as_user=user_to_run_check_as)
                    if res_ver.returncode == 0 and res_ver.stdout.strip():
                        output_first_line = res_ver.stdout.strip().splitlines()[0]
                        if tool_name_check == "pip3" and "Version:" in res_ver.stdout:
                            output_first_line = next((line.split(':',1)[1].strip() for line in res_ver.stdout.splitlines() if "Version:" in line),"")
                        version_str = f" ([italic]{output_first_line}[/])"
                        version_checked_ok = True
                        break 

                if version_checked_ok:
                    report_lines.append(f":heavy_check_mark: [green]Tool '[cyan]{tool_name_check}[/]' is available[/]{version_str}")
                else:
                    report_lines.append(f":heavy_check_mark: [green]Tool '[cyan]{tool_name_check}[/]' is available[/] (version check failed or no output)")
            except Exception as e_ver: 
                report_lines.append(f":heavy_check_mark: [green]Tool '[cyan]{tool_name_check}[/]' is available[/] (unexpected error during version check: {e_ver})")

        else:
            is_expected = False
            if tool_name_check in shared_state.DNF_PACKAGES_BASE and shared_state.IS_FEDORA: is_expected = True
            elif tool_name_check in shared_state.GNOME_MANAGEMENT_DNF_PACKAGES and shared_state.IS_FEDORA and check_gnome_specific_tools: is_expected = True
            elif tool_name_check in shared_state.CARGO_TOOLS: is_expected = True
            elif any(t['name'] == tool_name_check for t in shared_state.SCRIPTED_TOOLS): is_expected = True
            elif tool_name_check in ["zsh", "git", "curl", "nano", "python3", "pip3", "google-chrome-stable"]: is_expected = True
            
            if is_expected:
                report_lines.append(f":x: [bold red]Tool '[cyan]{tool_name_check}[/]' FAILED to be found (was expected).[/]")
                all_tools_ok = False
            else:
                report_lines.append(f":information_source: [dim]Tool '[cyan]{tool_name_check}[/]' not found (not necessarily expected in this step).[/]")
    
    shared_state.console.print(Panel_cls("\n".join(report_lines), title="[bold]Post-Installation Check Summary[/]", border_style="blue", expand=False))
    if all_tools_ok:
        shared_state.log.info("[bold green]All checked tools relevant to this step seem to be available.[/]")
    else:
        shared_state.log.warning("[bold yellow]Some expected tools were NOT found. Please review the summary and logs.[/]")