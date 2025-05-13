from . import shared_state
from . import utils
from . import utils as command_utils

import subprocess # For CalledProcessError, TimeoutExpired

def install_dnf_packages(packages_list: list[str]):
    if not shared_state.IS_FEDORA:
        if packages_list: shared_state.log.warning(f"Not Fedora. Ensure equivalents of: {', '.join(packages_list)} are installed.")
        return
    if not packages_list: shared_state.log.info("No DNF packages to install in this step."); return

    shared_state.log.info(f"Installing/verifying {len(packages_list)} DNF packages individually...")
    failed, installed_new = [], False
    for i, pkg_name in enumerate(packages_list):
        shared_state.log.info(f"({i+1}/{len(packages_list)}) DNF: [bold blue]{pkg_name}[/bold blue]...")
        with shared_state.console.status(f"[green]Processing {pkg_name}...[/]", spinner="earth"):
            try:
                res = command_utils.run_command(["dnf", "install", "-y", pkg_name], capture_output=True, text=True)
                if "Nothing to do" not in res.stdout and "already installed" not in res.stdout:
                    installed_new = True; shared_state.log.info(f":heavy_check_mark: '[cyan]{pkg_name}[/]' installed.")
                else: shared_state.log.info(f":package: '[cyan]{pkg_name}[/]' verified/already installed.")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                shared_state.log.warning(f"Failed DNF for '{pkg_name}'. See debug logs for details.") # run_command already logged ERROR
                failed.append(pkg_name)
            except Exception as e_unexp:
                shared_state.log.error(f"[bold red]Unexpected error DNF installing '{pkg_name}': {e_unexp}[/]"); failed.append(pkg_name)
                if shared_state.console: shared_state.console.print_exception(max_frames=3)
    if not failed:
        shared_state.log.info(f":white_check_mark: All DNF packages {'installed/verified' if installed_new else 'verified'}.")
    else:
        shared_state.log.warning(f"DNF summary: {len(failed)} failed packages: {', '.join(failed)}. Check logs.")