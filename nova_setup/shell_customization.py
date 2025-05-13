import os
import pwd
from . import shared_state
from . import utils as command_utils


def install_oh_my_zsh():
    omz_dir = shared_state.TARGET_USER_HOME / ".oh-my-zsh"
    if omz_dir.is_dir():
        shared_state.log.warning(f"OMZ in [cyan]{omz_dir}[/]. Skipping.")
        return
    shared_state.log.info(f"Installing Oh My Zsh for {shared_state.TARGET_USER}...")
    cmd = "curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh | sh -s -- --unattended --keep-zshrc"
    with shared_state.console.status("[green]Installing OMZ...[/]", spinner="monkey"):
        try:
            command_utils.run_command(cmd, as_user=shared_state.TARGET_USER, shell=True, check=True)
            shared_state.log.info(":rocket: OMZ installed.")
        except Exception as e:
            shared_state.log.error(f"[bold red]OMZ install failed: {e}[/]")

def install_omz_plugins():
    shared_state.log.info("Installing OMZ plugins...")
    plugins_dir = shared_state.TARGET_USER_HOME / ".oh-my-zsh/custom/plugins"
    try:
        command_utils.run_command(["mkdir", "-p", str(plugins_dir)], as_user=shared_state.TARGET_USER)
    except Exception as e:
        shared_state.log.error(f"Failed to create OMZ plugins dir: {e}")
        return

    for p_info in shared_state.OMZ_PLUGINS:
        p_name, p_url = p_info["name"], p_info["url"]
        target = plugins_dir / p_name
        if target.is_dir():
            shared_state.log.warning(f"OMZ Plugin '[cyan]{p_name}[/]' exists. Skipping.")
            continue
        shared_state.log.info(f"Cloning OMZ plugin '[cyan]{p_name}[/]'...")
        with shared_state.console.status(f"[green]Cloning {p_name}...[/]"):
            try:
                command_utils.run_command(["git", "clone", "--depth", "1", p_url, str(target)], as_user=shared_state.TARGET_USER)
                shared_state.log.info(f":heavy_check_mark: OMZ Plugin '{p_name}' installed.")
            except Exception as e_git:
                shared_state.log.error(f"[bold red]Failed OMZ plugin clone '{p_name}': {e_git}[/]")

def _ensure_zoxide_in_zshrc():
    """Appends zoxide init to .zshrc if not present."""
    if not shared_state.TARGET_USER: return # Should not happen
    
    zshrc_path = shared_state.TARGET_USER_HOME / ".zshrc"
    zoxide_init_line = 'eval "$(zoxide init zsh)"'
    zoxide_comment = "# Added by Nova Setup for zoxide"
    
    try:
        if zshrc_path.is_file():
            content = zshrc_path.read_text(encoding='utf-8')
            if zoxide_init_line not in content:
                shared_state.log.info(f"Adding zoxide init to [magenta]{zshrc_path}[/] for user {shared_state.TARGET_USER}")
                with open(zshrc_path, "a", encoding='utf-8') as f:
                    f.write(f"\n{zoxide_comment}\n{zoxide_init_line}\n")
                # Ensure correct ownership as root (via script) appended the line
                pw_info = pwd.getpwnam(shared_state.TARGET_USER)
                os.chown(zshrc_path, pw_info.pw_uid, pw_info.pw_gid)
                shared_state.log.info(f"Appended zoxide initialization to [magenta]{zshrc_path}[/].")
            else:
                shared_state.log.info(f"Zoxide init line already present in [magenta]{zshrc_path}[/].")
        else:
            shared_state.log.warning(f"[yellow]{zshrc_path}[/] not found. User {shared_state.TARGET_USER} may need to add zoxide init manually: '{zoxide_init_line}'[/]")
    except Exception as e_zoxide_init:
        shared_state.log.error(f"[bold red]Error updating .zshrc for zoxide: {e_zoxide_init}[/]")