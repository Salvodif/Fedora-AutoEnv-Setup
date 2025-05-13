import shutil
import subprocess # For CalledProcessError, TimeoutExpired

from . import shared_state
from .utils import run_command
from .package_manager import install_dnf_packages # Specific import

def manage_gnome_extensions():
    Console, Panel, Text, Confirm, _, _, _, _, _ = shared_state.get_rich_components()

    shared_state.console.rule("[bold magenta]GNOME Shell Extension Management[/]", style="magenta")
    if not shared_state.IS_FEDORA:
        shared_state.log.warning("GNOME features best on GNOME desktops (e.g., Fedora).")
        if not Confirm.ask("Attempt anyway?", default=False, console=shared_state.console): return
    
    if not shutil.which("gnome-extensions"):
        shared_state.log.error("`gnome-extensions` CLI not found. Cannot manage. Ensure `gnome-shell` is installed.")
        return

    shared_state.log.info("Installing/Verifying core GNOME management tools and base extension packages...")
    install_dnf_packages(shared_state.GNOME_MANAGEMENT_DNF_PACKAGES)

    dnf_pkgs_for_specific_exts = [
        ext_cfg["dnf_package"] for ext_cfg in shared_state.GNOME_EXTENSIONS_CONFIG 
        if "dnf_package" in ext_cfg and ext_cfg["dnf_package"] not in shared_state.GNOME_MANAGEMENT_DNF_PACKAGES
    ]
    if "gnome-shell-extension-user-themes" in dnf_pkgs_for_specific_exts and \
       "gnome-shell-extension-user-themes" in shared_state.GNOME_MANAGEMENT_DNF_PACKAGES: # Avoid double install
        dnf_pkgs_for_specific_exts.remove("gnome-shell-extension-user-themes")

    if dnf_pkgs_for_specific_exts:
        shared_state.log.info("Installing/Verifying DNF packages for specific GNOME extensions...")
        install_dnf_packages(dnf_pkgs_for_specific_exts)
    
    shared_state.log.info("Attempting to enable configured GNOME Shell extensions...")
    enabled_new = False
    for ext_cfg in shared_state.GNOME_EXTENSIONS_CONFIG:
        name, uuid, dnf_pkg = ext_cfg["name"], ext_cfg["uuid"], ext_cfg.get("dnf_package")
        shared_state.log.info(f"Processing: [cyan]{name}[/] (UUID: {uuid})")
        try:
            info_res = run_command(["gnome-extensions","info",uuid],as_user=shared_state.TARGET_USER,capture_output=True,text=True,check=False)
            state = "NOT FOUND"
            if info_res.returncode == 0 and info_res.stdout:
                state = next((l.split(":",1)[1].strip() for l in info_res.stdout.splitlines() if l.startswith("State:")), "UNKNOWN")
            shared_state.log.debug(f"Ext '{name}' state: {state}")

            if state == "ENABLED": shared_state.log.info(f":heavy_check_mark: '[cyan]{name}[/]' already enabled.")
            elif state in ["DISABLED", "INITIALIZED", "ERROR", "DOWNLOAD_NEEDED", "OUTDATED"]:
                shared_state.log.info(f"Attempting to enable '[cyan]{name}[/]' (state: {state})...")
                with shared_state.console.status(f"[green]Enabling {name}...[/]"):
                    run_command(["gnome-extensions","enable",uuid],as_user=shared_state.TARGET_USER,check=True)
                shared_state.log.info(f":arrow_up_small: '[cyan]{name}[/]' enabled."); enabled_new = True
            elif state == "NOT FOUND":
                shared_state.log.warning(f"[yellow]Ext '{name}' (UUID: {uuid}) not found via `gnome-extensions info`. DNF pkg '{dnf_pkg or 'N/A'}' might be missing/incompatible/failed.[/]")
            else: shared_state.log.warning(f"Ext '{name}' in unexpected state: {state}. Manual check needed.")
        except subprocess.CalledProcessError as e:
            shared_state.log.warning(f"Failed to manage ext '{name}'. Cmd: {' '.join(e.cmd)}. Pkg: {dnf_pkg or 'N/A'}.")
            if e.stderr: shared_state.log.debug(f"[stderr {name}]: {e.stderr.strip()}")
            if e.stdout: shared_state.log.debug(f"[stdout {name}]: {e.stdout.strip()}")
        except Exception as e_unexp:
            shared_state.log.error(f"[bold red]Unexpected error managing ext '{name}': {e_unexp}[/]")
            if shared_state.console: shared_state.console.print_exception(max_frames=3)

    if enabled_new: shared_state.log.info("[yellow]GNOME Shell restart (Alt+F2, 'r', Enter) or logout/login may be needed.[/]")
    else: shared_state.log.info("No new GNOME extensions enabled, or they were already active/could not be enabled.")

    try:
        shared_state.log.info("Currently enabled GNOME extensions for "+shared_state.TARGET_USER+":")
        res = run_command(["gnome-extensions","list","--enabled"],as_user=shared_state.TARGET_USER,capture_output=True,check=True,text=True)
        if res.stdout.strip(): shared_state.console.print(res.stdout.strip())
        else: shared_state.log.info("No enabled extensions found or session inactive for command.")
    except Exception as e_list: shared_state.log.warning(f"Could not list enabled GNOME extensions: {e_list}")
    
    shared_state.console.print(Panel(Text("GNOME Extension Management Completed.", style="bold green"), expand=False))