#!/usr/bin/env python3

import os
import shlex
import shutil
import subprocess
import sys
import pwd # To get user's home directory by name
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Callable
import configparser # Added for dnf.conf editing

# Rich for beautiful terminal output
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm, Prompt, IntPrompt
from rich.logging import RichHandler
from rich.table import Table
from rich.padding import Padding
import logging

# --- Configuration ---
ZSHRC_SOURCE_FILE_NAME = ".zshrc"
NANORC_SOURCE_FILE_NAME = ".nanorc"


# Nomi delle sottodirectory relative alla posizione dello script
ZSHRC_SUBDIRECTORY = "zsh"
NANORC_SUBDIRECTORY = "nano"

LOG_FILE_NAME = "enhanced_setup_python.log" # Updated log file name

DNF_PACKAGES = [
    "zsh", "python3", "python3-pip", # Added python
    "git", "curl", "stow", "dnf-plugins-core", "cargo",
    "powerline-fonts", "btop", "bat", "fzf",
    "gnome-tweaks", "gnome-shell-extensions", # Added gnome-tweaks and core extensions
    "gnome-extensions-app", "gnome-shell-extension-manager" # For managing extensions
]

OMZ_PLUGINS: List[Dict[str, str]] = [
    {"name": "zsh-autosuggestions", "url": "https://github.com/zsh-users/zsh-autosuggestions"},
    {"name": "zsh-syntax-highlighting", "url": "https://github.com/zsh-users/zsh-syntax-highlighting.git"},
    {"name": "you-should-use", "url": "https://github.com/MichaelAquilina/zsh-you-should-use.git"},
    {"name": "zsh-eza", "url": "https://github.com/z-shell/zsh-eza"},
    {"name": "fzf-tab", "url": "https://github.com/Aloxaf/fzf-tab"}
]

CARGO_TOOLS = ["eza", "du-dust"]

SCRIPTED_TOOLS: List[Dict[str, str]] = [
    {"name": "zoxide", "check_command": "zoxide --version", "url": "https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh", "method": "sh"},
    {"name": "atuin", "check_command": "atuin --version", "url": "https://setup.atuin.sh", "method": "bash"},
]

# --- Global Variables & Rich Console ---
console = Console(record=True)
SCRIPT_DIR = Path(__file__).parent.resolve()
TARGET_USER = ""
TARGET_USER_HOME = Path(".")
LOG_FILE_PATH = Path(".")
IS_FEDORA = False

# Percorsi corretti ai file sorgente
ZSHRC_SOURCE_PATH = SCRIPT_DIR / ZSHRC_SUBDIRECTORY / ZSHRC_SOURCE_FILE_NAME
NANORC_SOURCE_PATH = SCRIPT_DIR / NANORC_SUBDIRECTORY / NANORC_SOURCE_FILE_NAME

logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, markup=True, show_path=False)]
)
log = logging.getLogger("rich")

# --- Utility Functions ---
def run_command(command: List[str] | str,
                check: bool = True,
                capture_output: bool = False,
                text: bool = True,
                as_user: Optional[str] = None,
                shell: bool = False,
                cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    cmd_for_log = command if isinstance(command, str) else ' '.join(shlex.quote(str(s)) for s in command)
    log.debug(f"Executing: {cmd_for_log}{f' as {as_user}' if as_user else ''}{f' in {cwd}' if cwd else ''}")

    final_command_parts: List[str] = []
    actual_command_to_run: List[str] | str

    if as_user:
        final_command_parts.extend(["sudo", "-u", as_user])
        if shell:
            final_command_parts.extend(["sh", "-c", command if isinstance(command, str) else " ".join(command)])
            actual_command_to_run = final_command_parts
        else:
            final_command_parts.extend(command if isinstance(command, list) else [command])
            actual_command_to_run = final_command_parts
    else: # Running as root
        if shell:
            actual_command_to_run = command if isinstance(command, str) else " ".join(command)
        else:
            actual_command_to_run = command if isinstance(command, list) else [command]

    try:
        process_env = os.environ.copy()
        if as_user:
            pw_entry = pwd.getpwnam(as_user)
            process_env['HOME'] = pw_entry.pw_dir
            process_env['USER'] = as_user
            process_env['LOGNAME'] = as_user
            # Attempt to find DBUS_SESSION_BUS_ADDRESS for the target user if running GUI commands
            # This is a best-effort and might not always work in all environments (e.g. from cron, ssh without X forwarding)
            try:
                # Find processes for the user, get their environments, look for DBUS_SESSION_BUS_ADDRESS
                # Using `systemctl --user show-environment` is more robust if available and systemd user session is active
                dbus_address_cmd = f"systemctl --user -M {shlex.quote(as_user)}@.service show-environment"
                res_dbus = subprocess.run(shlex.split(dbus_address_cmd), capture_output=True, text=True, check=False)
                if res_dbus.returncode == 0:
                    for line in res_dbus.stdout.splitlines():
                        if line.startswith("DBUS_SESSION_BUS_ADDRESS="):
                            process_env['DBUS_SESSION_BUS_ADDRESS'] = line.split('=', 1)[1]
                            log.debug(f"Set DBUS_SESSION_BUS_ADDRESS for user {as_user} via systemctl.")
                            break
                elif Path(f"/run/user/{pw_entry.pw_uid}/bus").exists(): # Fallback common path
                     process_env['DBUS_SESSION_BUS_ADDRESS'] = f"unix:path=/run/user/{pw_entry.pw_uid}/bus"
                     log.debug(f"Set DBUS_SESSION_BUS_ADDRESS for user {as_user} via common path.")

            except Exception as e_dbus:
                log.debug(f"Could not robustly determine DBUS_SESSION_BUS_ADDRESS for {as_user}: {e_dbus}. Commands might still work.")


        result = subprocess.run(
            actual_command_to_run,
            check=check,
            capture_output=capture_output,
            text=text,
            shell=shell if not as_user else False,
            cwd=cwd,
            env=process_env # Pass modified env (either original or with user specifics)
        )
        return result
    except subprocess.CalledProcessError as e:
        cmd_str_err = ' '.join(e.cmd) if isinstance(e.cmd, list) else e.cmd
        log.error(f"Command '[bold cyan]{cmd_str_err}[/]' failed with exit code {e.returncode}")
        if capture_output: # Only log if captured, otherwise it's already on console
            if e.stdout: log.error(f"[stdout]: {e.stdout.strip()}")
            if e.stderr: log.error(f"[stderr]: {e.stderr.strip()}")
        raise
    except FileNotFoundError:
        cmd_failed = final_command_parts[0] if final_command_parts and isinstance(final_command_parts, list) else str(actual_command_to_run)
        log.error(f"Command not found: {cmd_failed.split()[0]}")
        raise

def check_command_exists(command_name_parts: List[str] | str, as_user: Optional[str] = None) -> bool:
    try:
        cmd_to_verify = command_name_parts[0] if isinstance(command_name_parts, list) else command_name_parts.split()[0]
        check_cmd_str = f"command -v {shlex.quote(cmd_to_verify)}"
        run_command(check_cmd_str, as_user=as_user, shell=True, capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

# --- Initialization ---
def initialize_script():
    global TARGET_USER, TARGET_USER_HOME, LOG_FILE_PATH
    if os.geteuid() != 0:
        log.critical("[bold red]This script must be run as root (or with sudo).[/]")
        sys.exit(1)
    TARGET_USER = os.getenv("SUDO_USER")
    if not TARGET_USER:
        log.warning("No SUDO_USER detected. User-specific configurations will target the root user.")
        TARGET_USER = pwd.getpwuid(os.geteuid()).pw_name
    try:
        pw_entry = pwd.getpwnam(TARGET_USER)
        TARGET_USER_HOME = Path(pw_entry.pw_dir)
    except KeyError:
        log.critical(f"[bold red]User '{TARGET_USER}' not found. Cannot determine home directory.[/]")
        sys.exit(1)
    if not TARGET_USER_HOME.is_dir():
        log.critical(f"[bold red]Home directory for target user '{TARGET_USER_HOME}' does not exist.[/]")
        sys.exit(1)
    LOG_FILE_PATH = TARGET_USER_HOME / LOG_FILE_NAME
    file_handler = logging.FileHandler(LOG_FILE_PATH)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logging.getLogger().addHandler(file_handler)
    log.info(f"Script initialized. Running as root, targeting user: [bold yellow]{TARGET_USER}[/]")
    log.info(f"Target user home: [bold yellow]{TARGET_USER_HOME}[/]")
    log.info(f"Logging detailed output to: [bold cyan]{LOG_FILE_PATH}[/]")
    if not ZSHRC_SOURCE_PATH.is_file() or not NANORC_SOURCE_PATH.is_file():
        log.critical("[bold red]Source configuration files (.zshrc or .nanorc) not found in expected subdirectories. Exiting.[/]")
        sys.exit(1)
    log.info("Source configuration files found.")

def perform_system_update_check():
    global IS_FEDORA
    log.info("Checking operating system...")
    os_release_path = Path("/etc/os-release")
    if os_release_path.is_file():
        try:
            content = os_release_path.read_text()
            os_vars = dict(line.split('=', 1) for line in content.splitlines() if '=' in line)
            os_id = os_vars.get('ID', '').strip('"')
            os_id_like = os_vars.get('ID_LIKE', '').strip('"')
            pretty_name = os_vars.get('PRETTY_NAME', 'Unknown OS').strip('"')

            if os_id == "fedora" or "fedora" in os_id_like.split():
                IS_FEDORA = True
                log.info(f":package: Fedora detected ([italic green]{pretty_name}[/]).")
                log.info("Performing Fedora specific pre-update configurations...")
                dnf_conf_path = Path("/etc/dnf/dnf.conf")
                log.info(f"Configuring DNF settings in {dnf_conf_path} for speed.")
                config = configparser.ConfigParser(allow_no_value=True, comment_prefixes=('#', ';'), inline_comment_prefixes=('#', ';'), strict=False)
                config.optionxform = str
                needs_dnf_conf_write = False
                if dnf_conf_path.is_file():
                    try: config.read(dnf_conf_path, encoding='utf-8')
                    except configparser.Error as e: log.warning(f"Could not parse existing {dnf_conf_path}: {e}.")
                if not config.has_section('main'):
                    config.add_section('main'); needs_dnf_conf_write = True
                settings_to_ensure = {"max_parallel_downloads": "10", "fastestmirror": "true"}
                for key, val in settings_to_ensure.items():
                    if config.get('main', key, fallback=None) != val:
                        config.set('main', key, val); needs_dnf_conf_write = True
                if needs_dnf_conf_write:
                    if dnf_conf_path.is_file():
                        backup_path = dnf_conf_path.with_suffix(dnf_conf_path.suffix + f".backup_setup_{os.urandom(4).hex()}")
                        try: shutil.copy2(dnf_conf_path, backup_path); log.info(f"Backed up {dnf_conf_path} to {backup_path}")
                        except Exception as e_backup: log.error(f"Failed to backup {dnf_conf_path}: {e_backup}")
                    try:
                        with open(dnf_conf_path, 'w', encoding='utf-8') as cf: config.write(cf, space_around_delimiters=False)
                        log.info(f"Updated DNF config: {dnf_conf_path}")
                    except Exception as e_write: log.error(f"Failed to write DNF config {dnf_conf_path}: {e_write}")
                else: log.info(f"DNF settings in {dnf_conf_path} already configured.")

                log.info("Ensuring Fedora third-party repositories package is installed...")
                try:
                    run_command(["dnf", "install", "-y", "fedora-workstation-repositories"])
                    log.info("`fedora-workstation-repositories` package checked/installed.")
                except Exception as e: log.error(f"Failed to install `fedora-workstation-repositories`: {e}")

                log.info("Enabling RPM Fusion free and non-free repositories...")
                try:
                    fedora_version = run_command("rpm -E %fedora", shell=True, capture_output=True, text=True, check=True).stdout.strip()
                    if not fedora_version.isdigit(): raise ValueError(f"Invalid Fedora version: {fedora_version}")
                    for repo_type in ["free", "nonfree"]:
                        url = f"https://download1.rpmfusion.org/{repo_type}/fedora/rpmfusion-{repo_type}-release-{fedora_version}.noarch.rpm"
                        log.info(f"Installing RPM Fusion {repo_type} from {url}")
                        run_command(["dnf", "install", "-y", url])
                    log.info("RPM Fusion repositories setup/checked.")
                except Exception as e: log.error(f"Failed to setup RPM Fusion: {e}")

                with console.status("[bold green]Updating and upgrading system (dnf)...[/]", spinner="dots"):
                    try: run_command(["dnf", "update", "-y"]); run_command(["dnf", "upgrade", "-y"])
                    except subprocess.CalledProcessError: log.error("[bold red]Failed to update/upgrade system via DNF.")
                log.info(":white_check_mark: System update and upgrade complete.")
            else: # Non-Fedora
                log.warning(f"This script is optimized for Fedora. You are running: [yellow]{pretty_name}[/]")
                if not Confirm.ask("Continue anyway?", default=False, console=console): sys.exit(0)
                log.warning("Proceeding on non-Fedora. DNF-specifics will be skipped.")
        except Exception as e: log.error(f"Could not parse /etc/os-release: {e}"); console.print_exception()
    else: # No /etc/os-release
        log.warning("Could not determine OS from /etc/os-release.")
        if not Confirm.ask("Continue assuming non-Fedora?", default=False, console=console): sys.exit(0)

def install_dnf_packages(packages_list: List[str]):
    if IS_FEDORA:
        if not packages_list:
            log.info("No DNF packages specified for installation.")
            return

        log.info(f"Installing DNF packages individually: [cyan]{len(packages_list)} packages total[/]...")
        all_successful = True
        failed_packages: List[str] = []
        installed_some_new = False # Track if any package was newly installed vs already present

        for i, package_name in enumerate(packages_list):
            log.info(f"({i+1}/{len(packages_list)}) Attempting to install DNF package: [bold blue]{package_name}[/bold blue]...")
            
            with console.status(f"[bold green]Installing {package_name} via DNF...[/]", spinner="earth"):
                try:
                    result = run_command(
                        ["dnf", "install", "-y", package_name],
                        capture_output=True, 
                        text=True
                        # check=True is default, will raise CalledProcessError on failure
                    )
                    
                    # Check dnf output to see if it actually installed something new
                    if "Nothing to do" not in result.stdout and "already installed" not in result.stdout:
                        installed_some_new = True
                        # More specific "installed" message if it wasn't just a verification
                        log.info(f":heavy_check_mark: DNF package '[cyan]{package_name}[/]' installed successfully.")
                    else:
                        log.info(f":package: DNF package '[cyan]{package_name}[/]' was already installed or verified.")

                except subprocess.CalledProcessError as e:
                    log.error(f"[bold red]Failed to install DNF package '{package_name}'. DNF exit code: {e.returncode}[/]")
                    # Log DNF's output if captured (run_command was set to capture_output=True)
                    if e.stderr:
                        log.error(f"[stderr for {package_name}]: {e.stderr.strip()}")
                    elif e.stdout : # DNF sometimes puts critical errors in stdout
                         log.error(f"[stdout for {package_name}]: {e.stdout.strip()}")
                    all_successful = False
                    failed_packages.append(package_name)
                except Exception as e: 
                    log.error(f"[bold red]An unexpected error occurred while trying to install DNF package '{package_name}': {e}[/]")
                    console.print_exception(max_frames=3)
                    all_successful = False
                    failed_packages.append(package_name)
        
        if all_successful:
            if installed_some_new:
                log.info(":white_check_mark: All specified DNF packages were processed successfully (some were newly installed).")
            else:
                log.info(":white_check_mark: All specified DNF packages were already installed or verified.")
        else:
            log.warning(f"[bold yellow]DNF package installation summary: Some packages failed to install: {', '.join(failed_packages)}[/]")
            log.warning("Please check DNF logs (e.g., /var/log/dnf.log) and the output above for details.")
    else:
        log.warning("Skipping DNF package installation (not Fedora).")
        if packages_list:
            log.info(f"On a non-Fedora system, please ensure equivalents of these are installed: {', '.join(packages_list)}")


# --- Tool Installation Functions ---
def check_critical_deps():
    log.info("Checking critical dependencies (git, curl)...")
    missing = [dep for dep in ["git", "curl"] if not shutil.which(dep)]
    if missing:
        if IS_FEDORA: log.warning(f"Missing critical dependencies: {', '.join(missing)}. Will be installed via DNF.")
        else: log.critical(f"Missing: {', '.join(missing)}. Install them and re-run."); sys.exit(1)
    else: log.info(":heavy_check_mark: Critical dependencies available.")

def install_oh_my_zsh():
    omz_dir = TARGET_USER_HOME / ".oh-my-zsh"
    if omz_dir.is_dir(): log.warning(f"Oh My Zsh already in [cyan]{omz_dir}[/]. Skipping."); return
    log.info("Installing Oh My Zsh...")
    cmd = "curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh | sh -s -- --unattended --keep-zshrc"
    with console.status("[bold green]Installing Oh My Zsh...[/]", spinner="monkey"):
        try: run_command(cmd, as_user=TARGET_USER, shell=True, check=True); log.info(":rocket: Oh My Zsh installed.")
        except subprocess.CalledProcessError: log.error("[bold red]Oh My Zsh installation failed.[/]")

def install_omz_plugins():
    log.info("Installing Oh My Zsh plugins...")
    plugins_dir = TARGET_USER_HOME / ".oh-my-zsh/custom/plugins"
    run_command(["mkdir", "-p", str(plugins_dir)], as_user=TARGET_USER)
    for plugin in OMZ_PLUGINS:
        target_dir = plugins_dir / plugin["name"]
        if target_dir.is_dir(): log.warning(f"OMZ Plugin '[cyan]{plugin['name']}[/]' exists. Skipping."); continue
        log.info(f"Cloning OMZ plugin '[cyan]{plugin['name']}[/]'...")
        with console.status(f"[bold green]Cloning {plugin['name']}...[/]", spinner="dots"):
            try:
                run_command(["git", "clone", "--depth", "1", plugin["url"], str(target_dir)], as_user=TARGET_USER)
                log.info(f":heavy_check_mark: OMZ Plugin '[cyan]{plugin['name']}[/]' installed.")
            except subprocess.CalledProcessError: log.error(f"[bold red]Failed to clone OMZ plugin '{plugin['name']}'.[/]")

def install_cargo_tools():
    log.info(f"Installing Cargo tools: [cyan]{', '.join(CARGO_TOOLS)}[/]...")
    cargo_cmd = str(TARGET_USER_HOME / ".cargo/bin/cargo") if (TARGET_USER_HOME / ".cargo/bin/cargo").is_file() else shutil.which("cargo")
    if not cargo_cmd: log.warning("[bold yellow]Cargo not found.[/] Skipping Cargo tools."); return
    log.info(f"Using cargo: [blue]{cargo_cmd}[/]")
    for tool in CARGO_TOOLS:
        try: 
            list_res = run_command([cargo_cmd, "install", "--list"], as_user=TARGET_USER, capture_output=True, text=True, check=False)
            if list_res.returncode == 0 and f"{tool} v" in list_res.stdout:
                log.warning(f"Cargo tool '[cyan]{tool}[/]' already installed. Skipping."); continue
        except Exception as e: log.debug(f"Cargo list check failed for {tool}: {e}")
        log.info(f"Installing '[cyan]{tool}[/]' with cargo...")
        with console.status(f"[bold green]Installing {tool} with cargo...[/]", spinner="bouncingBar"):
            try: run_command([cargo_cmd, "install", tool], as_user=TARGET_USER); log.info(f":crates: Cargo tool '[cyan]{tool}[/]' installed.")
            except subprocess.CalledProcessError: log.error(f"[bold red]Failed to install Cargo tool '{tool}'.[/]")

def install_scripted_tools():
    for tool in SCRIPTED_TOOLS:
        name, check_cmd_parts, url, method = tool["name"], shlex.split(tool["check_command"]), tool["url"], tool["method"]
        log.info(f"Installing '[cyan]{name}[/]'...")
        try:
            if check_command_exists(check_cmd_parts, as_user=TARGET_USER):
                 run_command(check_cmd_parts, as_user=TARGET_USER, capture_output=True, check=True) 
                 log.warning(f"'[cyan]{name}[/]' already installed (version check OK). Skipping."); continue
        except subprocess.CalledProcessError: log.debug(f"'{name}' found, but version check failed or command error. Reinstalling.")
        except FileNotFoundError: log.debug(f"'{name}' not found. Installing.")
        
        log.info(f"Downloading and executing install script for '[cyan]{name}[/]'...")
        cmd = f"curl -fsSL {url} | {method}"
        with console.status(f"[bold green]Installing {name}...[/]", spinner="arrow3"):
            try:
                run_command(cmd, as_user=TARGET_USER, shell=True, check=True)
                if check_command_exists(check_cmd_parts, as_user=TARGET_USER):
                    log.info(f":white_check_mark: '[cyan]{name}[/]' installed successfully.")
                else: log.error(f"[bold red]Install of '[cyan]{name}[/]' might have failed (cmd not found post-install).[/]")
            except subprocess.CalledProcessError: log.error(f"[bold red]Installation of '{name}' failed via script.[/]")

# --- Configuration File Management ---
def copy_config_files():
    log.info("Copying configuration files...")
    pw_info = pwd.getpwnam(TARGET_USER)
    
    target_zshrc = TARGET_USER_HOME / ".zshrc"
    log.info(f"Copying [magenta]{ZSHRC_SOURCE_FILE_NAME}[/] to [cyan]{target_zshrc}[/]")
    if target_zshrc.exists():
        backup_zshrc = TARGET_USER_HOME / f".zshrc.backup.{os.urandom(4).hex()}"
        log.warning(f"Backing up existing .zshrc to [cyan]{backup_zshrc}[/]")
        try: run_command(["cp", str(target_zshrc), str(backup_zshrc)], as_user=TARGET_USER)
        except Exception: shutil.copy(target_zshrc, backup_zshrc) 
    shutil.copy(ZSHRC_SOURCE_PATH, target_zshrc)
    os.chown(target_zshrc, pw_info.pw_uid, pw_info.pw_gid)
    log.info(f":floppy_disk: [magenta]{ZSHRC_SOURCE_FILE_NAME}[/] copied.")

    nanorc_dir = TARGET_USER_HOME / ".config/nano"
    nanorc_file = nanorc_dir / "nanorc"
    run_command(["mkdir", "-p", str(nanorc_dir)], as_user=TARGET_USER) 
    log.info(f"Copying [magenta]{NANORC_SOURCE_FILE_NAME}[/] to [cyan]{nanorc_file}[/]")
    if nanorc_file.exists():
        backup_nanorc = nanorc_dir / f"nanorc.backup.{os.urandom(4).hex()}"
        log.warning(f"Backing up existing nanorc to [cyan]{backup_nanorc}[/]")
        try: run_command(["cp", str(nanorc_file), str(backup_nanorc)], as_user=TARGET_USER)
        except Exception: shutil.copy(nanorc_file, backup_nanorc)
    shutil.copy(NANORC_SOURCE_PATH, nanorc_file)
    os.chown(nanorc_file, pw_info.pw_uid, pw_info.pw_gid)
    try:
        if nanorc_dir.stat().st_uid != pw_info.pw_uid: # More accurate owner check
             os.chown(nanorc_dir, pw_info.pw_uid, pw_info.pw_gid)
             if nanorc_dir.parent.name == ".config" and nanorc_dir.parent.stat().st_uid != pw_info.pw_uid :
                 os.chown(nanorc_dir.parent, pw_info.pw_uid, pw_info.pw_gid)
    except Exception as e: 
        log.debug(f"Could not chown nanorc dirs, usually okay if mkdir as_user worked: {e}")
    log.info(f":floppy_disk: [magenta]{NANORC_SOURCE_FILE_NAME}[/] copied to {nanorc_dir}.")

# --- Post-Installation Verification ---
def perform_post_install_checks():
    log.info("Performing post-installation checks...")
    tools = ["zsh", "git", "curl", "python3", "pip3", "eza", "dust", "btop", "bat", "fzf", "zoxide", "atuin", "nano", "gnome-tweaks"]
    report = []
    all_ok = True
    for tool in tools:
        found_path = None
        for user_path in [TARGET_USER_HOME / ".local/bin", TARGET_USER_HOME / ".cargo/bin"]:
            if (user_path / tool).is_file(): found_path = str(user_path / tool); break
        if not found_path: found_path = shutil.which(tool)

        if found_path:
            version = " (version N/A)"
            version_found_flag = False
            try:
                # Try common version flags. Run as user if path is in user's home.
                run_as = TARGET_USER if TARGET_USER_HOME.as_posix() in found_path else None
                cmd_prefix = [found_path]

                for v_flag in ["--version", "-V", "version"]:
                    cmd_to_run = cmd_prefix + [v_flag]
                    if tool == "pip3" and v_flag == "--version": # pip3 --version is different, use 'show pip'
                        cmd_to_run = [found_path, "show", "pip"]
                    
                    try:
                        res = run_command(cmd_to_run, capture_output=True, text=True, check=False, as_user=run_as)
                        if res.returncode == 0 and res.stdout.strip():
                            output_line = res.stdout.strip().splitlines()[0]
                            if tool == "pip3" and "Version:" in res.stdout: # Specific parsing for pip show pip
                                version_line = next((line for line in res.stdout.splitlines() if "Version:" in line), "")
                                if version_line: output_line = version_line.split(':',1)[1].strip()
                            version = f" ([italic]{output_line}[/])"
                            version_found_flag = True
                            break 
                    except Exception: continue 
                
                if version_found_flag:
                    report.append(f":heavy_check_mark: [green]'{tool}' available[/]{version}")
                else:
                    report.append(f":heavy_check_mark: [green]'{tool}' available[/] (version check command failed or no output)")
            except Exception as e: 
                report.append(f":heavy_check_mark: [green]'{tool}' available[/] (unexpected error during version check: {e})")
        else: # Tool not found
            expected = (tool in DNF_PACKAGES and IS_FEDORA) or \
                       (tool in CARGO_TOOLS) or \
                       any(t['name'] == tool for t in SCRIPTED_TOOLS) or \
                       (tool in ["zsh", "git", "curl", "nano", "python3", "pip3"])
            if expected: report.append(f":x: [bold red]'{tool}' FAILED to be found.[/]"); all_ok = False
            else: report.append(f":warning: [yellow]'{tool}' not found (may be expected).[/]")
    
    console.print(Panel("\n".join(report), title="[bold]Post-Installation Check Summary[/]", border_style="blue"))
    if all_ok: log.info("[bold green]All critical post-installation checks passed.[/]")
    else: log.warning("[bold yellow]Some post-installation checks failed. Review summary and logs.[/]")

# --- Main Setup Functions ---
def perform_initial_setup():
    console.rule("[bold sky_blue2]Initial Environment Setup[/]", style="sky_blue2")
    perform_system_update_check()
    check_critical_deps()
    install_dnf_packages(DNF_PACKAGES)
    install_oh_my_zsh()
    install_omz_plugins()
    install_cargo_tools()
    install_scripted_tools()
    copy_config_files()
    perform_post_install_checks()
    console.print(Panel(Text("Initial Setup Process Completed!", style="bold green"), expand=False))

GNOME_EXTENSIONS_CONFIG: List[Dict[str, str]] = [
    {"name": "User Themes", "uuid": "user-theme@gnome-shell-extensions.gcampax.github.com", "dnf_package": "gnome-shell-extension-user-themes"},
    {"name": "Blur My Shell", "uuid": "blur-my-shell@aunetx", "dnf_package": "gnome-shell-extension-blur-my-shell"},
    {"name": "Burn My Windows", "uuid": "burn-my-windows@schneegans.github.com", "dnf_package": "gnome-shell-extension-burn-my-windows"},
    {"name": "Vitals (System Monitor)", "uuid": "Vitals@CoreCoding.com", "dnf_package": "gnome-shell-extension-vitals"},
    {"name": "Caffeine", "uuid": "caffeine@patapon.info", "dnf_package": "gnome-shell-extension-caffeine"},
]

def manage_gnome_extensions():
    console.rule("[bold magenta]GNOME Shell Extension Management[/]", style="magenta")
    if not IS_FEDORA:
        log.warning("GNOME extension management is for GNOME desktops (e.g., Fedora).")
        if not Confirm.ask("Attempt anyway?", default=False): return
    
    if not shutil.which("gnome-extensions"):
        log.error("`gnome-extensions` command-line tool not found. Cannot manage extensions.")
        log.info("This tool is usually part of the `gnome-shell` package. Ensure it's installed.")
        return

    extension_dnf_packages = [ext["dnf_package"] for ext in GNOME_EXTENSIONS_CONFIG if "dnf_package" in ext]
    if extension_dnf_packages:
        log.info("Installing/Verifying DNF packages for GNOME extensions...")
        install_dnf_packages(extension_dnf_packages) # Uses the modified individual installer
    
    log.info("Enabling configured GNOME Shell extensions...")
    enabled_any_new = False
    for ext_config in GNOME_EXTENSIONS_CONFIG:
        name, uuid = ext_config["name"], ext_config["uuid"]
        log.info(f"Processing extension: [cyan]{name}[/] (UUID: {uuid})")
        try:
            info_result = run_command(["gnome-extensions", "info", uuid], as_user=TARGET_USER, capture_output=True, text=True, check=False)
            current_state = "NOT FOUND"
            if info_result.returncode == 0 and info_result.stdout:
                for line in info_result.stdout.splitlines():
                    if line.startswith("State:"): current_state = line.split(":", 1)[1].strip(); break
            log.debug(f"Extension '{name}' current state: {current_state}")

            if current_state == "ENABLED":
                log.info(f":heavy_check_mark: Extension '[cyan]{name}[/]' is already enabled.")
            elif current_state in ["DISABLED", "INITIALIZED", "ERROR"]: 
                log.info(f"Attempting to enable extension '[cyan]{name}[/]'...")
                with console.status(f"[bold green]Enabling {name}...[/]"):
                    run_command(["gnome-extensions", "enable", uuid], as_user=TARGET_USER, check=True)
                log.info(f":arrow_up_small: Extension '[cyan]{name}[/]' enabled successfully.")
                enabled_any_new = True
            elif current_state == "NOT FOUND":
                log.error(f"[bold red]Extension '[cyan]{name}[/]' (UUID: {uuid}) not found by `gnome-extensions info` command. Package '{ext_config.get('dnf_package', 'N/A')}' might be missing, incompatible, or failed to install correctly.[/]")
            else: 
                 log.warning(f"Extension '[cyan]{name}[/]' is in an unexpected state: {current_state}. Manual check might be needed.")
        except subprocess.CalledProcessError as e:
            log.error(f"[bold red]Failed to manage extension '[cyan]{name}[/] (UUID: {uuid}). Command: {' '.join(e.cmd)}[/]")
            if e.stderr: log.error(f"[stderr]: {e.stderr.strip()}")
            if e.stdout: log.error(f"[stdout]: {e.stdout.strip()}") # gnome-extensions might put errors in stdout
        except Exception as e:
            log.error(f"[bold red]An unexpected error occurred while managing extension '[cyan]{name}[/]: {e}[/]")
            console.print_exception(max_frames=4)

    if enabled_any_new:
        log.info("[bold yellow]Some GNOME extensions were newly enabled. A GNOME Shell restart (Alt+F2, 'r', Enter) or logout/login may be required for changes to take full effect.[/]")
    else:
        log.info("No new GNOME extensions were enabled in this run, or they were already active.")

    try:
        log.info("Listing currently enabled GNOME extensions for user:")
        result = run_command(["gnome-extensions", "list", "--enabled"], as_user=TARGET_USER, capture_output=True, check=True, text=True)
        if result.stdout.strip():
             console.print("[bold]Currently enabled GNOME extensions:[/]")
             console.print(result.stdout.strip())
        else: log.info("No enabled GNOME extensions found for the user or session inactive.")
    except Exception as e: log.warning(f"Could not list GNOME extensions post-management: {e}")
    console.print(Panel(Text("GNOME Extension Management Completed.", style="bold green"), expand=False))

# --- Main Application Logic ---
def display_main_menu():
    console.print(Panel(Text("Enhanced System Setup Utility", justify="center", style="bold white on dark_blue")))
    menu_options: Dict[str, Tuple[str, Callable[[], None]]] = {
        "1": ("Perform Initial Environment Setup", perform_initial_setup),
        "2": ("Manage GNOME Shell Extensions", manage_gnome_extensions),
        "3": ("Exit", lambda: sys.exit(0))
    }
    last_choice_was_exit = False
    while True:
        console.rule("[bold gold1]Main Menu[/]", style="gold1")
        table = Table(show_header=False, box=None, padding=(0,1))
        table.add_column(style="cyan", justify="right"); table.add_column()
        for k, (desc, _) in menu_options.items(): table.add_row(f"[{k}]", desc)
        console.print(Padding(table, (1,2)))
        choice = Prompt.ask("Enter choice", choices=list(menu_options.keys()), show_choices=False, console=console)
        
        last_choice_was_exit = (choice == "3")
        desc, action = menu_options[choice]
        log.info(f"User selected: ({choice}) {desc}")
        if action:
            try: action()
            except SystemExit: 
                # Save console output before actually exiting if sys.exit() was called from an action (like option "3")
                console_output_path = TARGET_USER_HOME / "setup_script_console_output.txt" if TARGET_USER_HOME.name != "." else SCRIPT_DIR / "setup_script_console_output.txt"
                console.save_text(console_output_path)
                log.info(f"Console output saved to {console_output_path}")
                raise # Re-raise SystemExit to terminate
            except Exception as e:
                log.exception(f"Error during '{desc}': {e}"); console.print_exception(show_locals=True)
                console.print(Panel(f"Error in '{desc}'. Check logs.", title="[bold red]Action Failed[/]",style="red"))
        if last_choice_was_exit: break
        if not Confirm.ask("\nReturn to main menu?", default=True, console=console):
            last_choice_was_exit = True # Treat "No" to return to menu as an exit condition for console saving
            break
    return last_choice_was_exit


def main():
    exit_via_menu = False
    try:
        initialize_script()
        exit_via_menu = display_main_menu()
    except SystemExit: 
        log.info("Script exited via sys.exit().") # Console log should have been saved by display_main_menu
    except Exception as e:
        log.exception(f"[bold red]Unhandled critical error in main: {e}[/]")
        console.print_exception(show_locals=True)
        console.print(Panel(f"Critical error. Logs at {LOG_FILE_PATH}", title="[bold red]SCRIPT FAILED[/]", style="red"))
        sys.exit(1) # Ensure exit code reflects failure
    finally:
        final_log_path = LOG_FILE_PATH if LOG_FILE_PATH.is_absolute() else SCRIPT_DIR / LOG_FILE_NAME
        console_output_path = TARGET_USER_HOME / "setup_script_console_output.txt" if TARGET_USER_HOME.is_absolute() else SCRIPT_DIR / "setup_script_console_output.txt"
        
        # Save console output if not already saved by a clean menu exit
        if not exit_via_menu: # If exited abruptly or not through menu's "Exit" path
            try:
                # Check if file already exists and was recently written to avoid overwriting if menu exit handled it
                # This logic can be complex; for now, ensure it's saved if `exit_via_menu` is False.
                if not console_output_path.exists(): # Simplified: save if it doesn't exist
                     console.save_text(console_output_path)
                     log.info(f"Console output saved to {console_output_path} in main finally block.")
            except Exception as e_save: 
                print(f"Error saving console output in main finally: {e_save}", file=sys.stderr)
        
        log.info(f"Execution finished. Full log at [link=file://{final_log_path}]{final_log_path}[/link]")

if __name__ == "__main__":
    main()