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
    "zsh", "python3", "python3-pip",
    "git", "curl", "stow", "dnf-plugins-core", "cargo",
    "powerline-fonts", "btop", "bat", "fzf",
    # gnome-tweaks, gnome-shell-extensions, gnome-extensions-app, gnome-shell-extension-manager
    # are now installed conditionally in manage_gnome_extensions()
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
            try:
                dbus_address_cmd = f"systemctl --user -M {shlex.quote(as_user)}@.service show-environment"
                res_dbus = subprocess.run(shlex.split(dbus_address_cmd), capture_output=True, text=True, check=False)
                if res_dbus.returncode == 0:
                    for line in res_dbus.stdout.splitlines():
                        if line.startswith("DBUS_SESSION_BUS_ADDRESS="):
                            process_env['DBUS_SESSION_BUS_ADDRESS'] = line.split('=', 1)[1]
                            log.debug(f"Set DBUS_SESSION_BUS_ADDRESS for user {as_user} via systemctl.")
                            break
                elif Path(f"/run/user/{pw_entry.pw_uid}/bus").exists(): 
                     process_env['DBUS_SESSION_BUS_ADDRESS'] = f"unix:path=/run/user/{pw_entry.pw_uid}/bus"
                     log.debug(f"Set DBUS_SESSION_BUS_ADDRESS for user {as_user} via common path.")
            except Exception as e_dbus:
                log.debug(f"Could not robustly determine DBUS_SESSION_BUS_ADDRESS for {as_user}: {e_dbus}.")
        result = subprocess.run(
            actual_command_to_run, check=check, capture_output=capture_output, text=text,
            shell=shell if not as_user else False, cwd=cwd, env=process_env
        )
        return result
    except subprocess.CalledProcessError as e:
        cmd_str_err = ' '.join(e.cmd) if isinstance(e.cmd, list) else e.cmd
        log.error(f"Command '[bold cyan]{cmd_str_err}[/]' failed with exit code {e.returncode}")
        if capture_output:
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
    if os.geteuid() != 0: log.critical("[bold red]Must be run as root (sudo).[/]"); sys.exit(1)
    TARGET_USER = os.getenv("SUDO_USER")
    if not TARGET_USER:
        log.warning("No SUDO_USER. Targeting root user."); TARGET_USER = pwd.getpwuid(os.geteuid()).pw_name
    try:
        pw_entry = pwd.getpwnam(TARGET_USER); TARGET_USER_HOME = Path(pw_entry.pw_dir)
    except KeyError: log.critical(f"[bold red]User '{TARGET_USER}' not found.[/]"); sys.exit(1)
    if not TARGET_USER_HOME.is_dir(): log.critical(f"[bold red]Home dir {TARGET_USER_HOME} missing.[/]"); sys.exit(1)
    
    LOG_FILE_PATH = TARGET_USER_HOME / LOG_FILE_NAME
    file_handler = logging.FileHandler(LOG_FILE_PATH)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logging.getLogger().addHandler(file_handler)
    log.info(f"Initialized. Target user: [yellow]{TARGET_USER}[/], home: [yellow]{TARGET_USER_HOME}[/]. Log: [cyan]{LOG_FILE_PATH}[/]")
    if not ZSHRC_SOURCE_PATH.is_file() or not NANORC_SOURCE_PATH.is_file():
        log.critical("[bold red]Source .zshrc or .nanorc missing. Exiting.[/]"); sys.exit(1)
    log.info("Source config files found.")

def perform_system_update_check():
    global IS_FEDORA
    log.info("Checking OS...")
    os_release_path = Path("/etc/os-release")
    if not os_release_path.is_file():
        log.warning("No /etc/os-release. Assuming non-Fedora."); return
    try:
        content = os_release_path.read_text()
        os_vars = dict(l.split('=', 1) for l in content.splitlines() if '=' in l)
        os_id, os_id_like = os_vars.get('ID','').strip('"'), os_vars.get('ID_LIKE','').strip('"')
        pretty_name = os_vars.get('PRETTY_NAME', 'Unknown OS').strip('"')

        if os_id == "fedora" or "fedora" in os_id_like.split():
            IS_FEDORA = True
            log.info(f":package: Fedora detected ([italic green]{pretty_name}[/]). Pre-configuring DNF...")
            dnf_conf, dnf_conf_path = Path("/etc/dnf/dnf.conf"), configparser.ConfigParser(allow_no_value=True, comment_prefixes=('#',';'), inline_comment_prefixes=('#',';'), strict=False)
            dnf_conf_path.optionxform = str
            needs_write = False
            if dnf_conf.is_file(): 
                try: dnf_conf_path.read(dnf_conf, encoding='utf-8')
                except Exception as e: log.warning(f"Parse error {dnf_conf}: {e}")
            if not dnf_conf_path.has_section('main'): dnf_conf_path.add_section('main'); needs_write=True
            for k,v in {"max_parallel_downloads": "10", "fastestmirror": "true"}.items():
                if dnf_conf_path.get('main', k, fallback=None) != v: dnf_conf_path.set('main', k, v); needs_write=True
            if needs_write:
                if dnf_conf.is_file(): shutil.copy2(dnf_conf, dnf_conf.with_suffix(f"{dnf_conf.suffix}.bkp_{os.urandom(4).hex()}"))
                with open(dnf_conf, 'w', encoding='utf-8') as cf: dnf_conf_path.write(cf, space_around_delimiters=False)
                log.info(f"Updated DNF config: {dnf_conf}")
            else: log.info(f"DNF settings in {dnf_conf} already good.")
            
            try: run_command(["dnf", "install", "-y", "fedora-workstation-repositories"]); log.info("Fedora third-party repos checked/installed.")
            except Exception as e: log.error(f"Failed `fedora-workstation-repositories` install: {e}")
            
            try:
                ver = run_command("rpm -E %fedora", shell=True, capture_output=True, text=True, check=True).stdout.strip()
                if not ver.isdigit(): raise ValueError(f"Bad Fedora version: {ver}")
                for rt in ["free", "nonfree"]: run_command(["dnf", "install", "-y", f"https://download1.rpmfusion.org/{rt}/fedora/rpmfusion-{rt}-release-{ver}.noarch.rpm"])
                log.info("RPM Fusion repos setup.")
            except Exception as e: log.error(f"RPM Fusion setup failed: {e}")

            with console.status("[bold green]Updating/upgrading system (dnf)...[/]", spinner="dots"):
                try: run_command(["dnf", "update", "-y"]); run_command(["dnf", "upgrade", "-y"])
                except subprocess.CalledProcessError: log.error("[bold red]DNF update/upgrade failed.")
            log.info(":white_check_mark: System update/upgrade complete.")
        else:
            log.warning(f"OS: [yellow]{pretty_name}[/]. Optimized for Fedora.")
            if not Confirm.ask("Continue anyway?", default=False): sys.exit(0)
    except Exception as e: log.error(f"OS check error: {e}"); console.print_exception()

def install_dnf_packages(packages_list: List[str]):
    if not IS_FEDORA:
        if packages_list: log.warning(f"Not Fedora. Ensure equivalents of: {', '.join(packages_list)} are installed.")
        return
    if not packages_list: log.info("No DNF packages to install."); return

    log.info(f"Installing {len(packages_list)} DNF packages individually...")
    failed, installed_new = [], False
    for i, pkg_name in enumerate(packages_list):
        log.info(f"({i+1}/{len(packages_list)}) DNF install: [bold blue]{pkg_name}[/bold blue]...")
        with console.status(f"[green]Installing {pkg_name}...[/]", spinner="earth"):
            try:
                res = run_command(["dnf", "install", "-y", pkg_name], capture_output=True, text=True)
                if "Nothing to do" not in res.stdout and "already installed" not in res.stdout:
                    installed_new = True; log.info(f":heavy_check_mark: '[cyan]{pkg_name}[/]' installed.")
                else: log.info(f":package: '[cyan]{pkg_name}[/]' verified/already installed.")
            except subprocess.CalledProcessError as e:
                log.error(f"[bold red]Failed DNF install '{pkg_name}'. Code: {e.returncode}[/]")
                if e.stderr: log.error(f"[stderr {pkg_name}]: {e.stderr.strip()}")
                elif e.stdout: log.error(f"[stdout {pkg_name}]: {e.stdout.strip()}")
                failed.append(pkg_name)
            except Exception as e:
                log.error(f"[bold red]Unexpected error installing '{pkg_name}': {e}[/]"); failed.append(pkg_name)
    if not failed:
        log.info(f":white_check_mark: All DNF packages {'installed/verified' if installed_new else 'verified'}.")
    else:
        log.warning(f"[bold yellow]DNF install summary: Failed packages: {', '.join(failed)}[/]. Check logs.")

# --- Tool Installation Functions ---
def check_critical_deps():
    log.info("Checking critical deps (git, curl)...")
    missing = [d for d in ["git", "curl"] if not shutil.which(d)]
    if missing:
        if IS_FEDORA: log.warning(f"Missing: {', '.join(missing)}. Will be DNF installed.")
        else: log.critical(f"Missing: {', '.join(missing)}. Install and re-run."); sys.exit(1)
    else: log.info(":heavy_check_mark: Critical deps available.")

def install_oh_my_zsh():
    omz_dir = TARGET_USER_HOME / ".oh-my-zsh"
    if omz_dir.is_dir(): log.warning(f"OMZ in [cyan]{omz_dir}[/]. Skipping."); return
    log.info("Installing Oh My Zsh..."); cmd = "curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh | sh -s -- --unattended --keep-zshrc"
    with console.status("[green]Installing OMZ...[/]", spinner="monkey"):
        try: run_command(cmd, as_user=TARGET_USER, shell=True, check=True); log.info(":rocket: OMZ installed.")
        except: log.error("[bold red]OMZ install failed.[/]")

def install_omz_plugins():
    log.info("Installing OMZ plugins..."); plugins_dir = TARGET_USER_HOME / ".oh-my-zsh/custom/plugins"
    run_command(["mkdir", "-p", str(plugins_dir)], as_user=TARGET_USER)
    for p in OMZ_PLUGINS:
        target = plugins_dir / p["name"]
        if target.is_dir(): log.warning(f"OMZ Plugin '[cyan]{p['name']}[/]' exists. Skipping."); continue
        log.info(f"Cloning OMZ plugin '[cyan]{p['name']}[/]'...")
        with console.status(f"[green]Cloning {p['name']}...[/]"):
            try: run_command(["git", "clone", "--depth", "1", p["url"], str(target)], as_user=TARGET_USER); log.info(f":heavy_check_mark: OMZ Plugin '{p['name']}' installed.")
            except: log.error(f"[bold red]Failed OMZ plugin clone '{p['name']}'.[/]")

def install_cargo_tools():
    log.info(f"Installing Cargo tools: [cyan]{', '.join(CARGO_TOOLS)}[/]...")
    cargo_cmd = str(TARGET_USER_HOME / ".cargo/bin/cargo") if (TARGET_USER_HOME / ".cargo/bin/cargo").is_file() else shutil.which("cargo")
    if not cargo_cmd: log.warning("[yellow]Cargo not found.[/] Skipping Cargo tools."); return
    log.info(f"Using cargo: [blue]{cargo_cmd}[/]")
    for tool in CARGO_TOOLS:
        try:
            if f"{tool} v" in run_command([cargo_cmd,"install","--list"],as_user=TARGET_USER,capture_output=True,text=True,check=False).stdout:
                log.warning(f"Cargo tool '[cyan]{tool}[/]' already installed. Skipping."); continue
        except: log.debug(f"Cargo list check failed for {tool}")
        log.info(f"Installing '[cyan]{tool}[/]' with cargo...")
        with console.status(f"[green]Installing {tool} with cargo...[/]"):
            try: run_command([cargo_cmd, "install", tool], as_user=TARGET_USER); log.info(f":crates: Cargo tool '[cyan]{tool}[/]' installed.")
            except: log.error(f"[bold red]Failed Cargo tool install '{tool}'.[/]")

def install_scripted_tools():
    for tool_info in SCRIPTED_TOOLS:
        name, check_cmd_parts, url, method = tool_info["name"], shlex.split(tool_info["check_command"]), tool_info["url"], tool_info["method"]
        log.info(f"Installing '[cyan]{name}[/]'...")
        try:
            if check_command_exists(check_cmd_parts, as_user=TARGET_USER):
                run_command(check_cmd_parts, as_user=TARGET_USER, capture_output=True, check=True)
                log.warning(f"'[cyan]{name}[/]' already installed & version OK. Skipping."); continue
        except (subprocess.CalledProcessError, FileNotFoundError): log.debug(f"'{name}' not found or version check failed. Installing.")
        
        log.info(f"Downloading & executing install script for '[cyan]{name}[/]'...")
        cmd_str = f"curl -fsSL {url} | {method}"
        with console.status(f"[green]Installing {name}...[/]", spinner="arrow3"):
            try:
                run_command(cmd_str, as_user=TARGET_USER, shell=True, check=True)
                if check_command_exists(check_cmd_parts, as_user=TARGET_USER):
                    log.info(f":white_check_mark: '[cyan]{name}[/]' installed.")
                    # --- ZOoxide .zshrc fix ---
                    if name == "zoxide":
                        zshrc_path = TARGET_USER_HOME / ".zshrc"
                        zoxide_init_line = 'eval "$(zoxide init zsh)"'
                        try:
                            if zshrc_path.is_file():
                                content = zshrc_path.read_text(encoding='utf-8')
                                if zoxide_init_line not in content:
                                    log.info(f"Adding '{zoxide_init_line}' to {zshrc_path} for user {TARGET_USER}")
                                    with open(zshrc_path, "a", encoding='utf-8') as f:
                                        f.write(f"\n# Added by setup script for zoxide\n{zoxide_init_line}\n")
                                    # Chown again as root appended
                                    pw_info = pwd.getpwnam(TARGET_USER)
                                    os.chown(zshrc_path, pw_info.pw_uid, pw_info.pw_gid)
                                    log.info(f"Appended zoxide init to {zshrc_path}.")
                                else:
                                    log.info(f"Zoxide init line already present in {zshrc_path}.")
                            else:
                                log.warning(f"{zshrc_path} not found for zoxide init. User may need to add manually.")
                        except Exception as e_zoxide_init:
                            log.error(f"Error adding zoxide init to .zshrc: {e_zoxide_init}")
                    # --- End zoxide fix ---
                else: log.error(f"[bold red]Install of '[cyan]{name}[/]' might have failed (cmd not found post-install).[/]")
            except: log.error(f"[bold red]Scripted install of '{name}' failed.[/]")

# --- Configuration File Management ---
def copy_config_files():
    log.info("Copying config files...")
    pw = pwd.getpwnam(TARGET_USER)
    
    # Zshrc
    target_zshrc = TARGET_USER_HOME / ".zshrc"
    log.info(f"Copying [magenta]{ZSHRC_SOURCE_FILE_NAME}[/] to [cyan]{target_zshrc}[/]")
    if target_zshrc.exists():
        backup = TARGET_USER_HOME / f".zshrc.backup.{os.urandom(4).hex()}"
        log.warning(f"Backing up existing .zshrc to [cyan]{backup}[/]")
        try: run_command(["cp",str(target_zshrc),str(backup)],as_user=TARGET_USER)
        except: shutil.copy(target_zshrc, backup)
    shutil.copy(ZSHRC_SOURCE_PATH, target_zshrc); os.chown(target_zshrc, pw.pw_uid, pw.pw_gid)
    log.info(f":floppy_disk: [magenta]{ZSHRC_SOURCE_FILE_NAME}[/] copied.")

    # Nanorc
    nanorc_dir, nanorc_file = TARGET_USER_HOME / ".config/nano", TARGET_USER_HOME / ".config/nano/nanorc"
    run_command(["mkdir","-p",str(nanorc_dir)],as_user=TARGET_USER)
    log.info(f"Copying [magenta]{NANORC_SOURCE_FILE_NAME}[/] to [cyan]{nanorc_file}[/]")
    if nanorc_file.exists():
        backup = nanorc_dir / f"nanorc.backup.{os.urandom(4).hex()}"
        log.warning(f"Backing up existing nanorc to [cyan]{backup}[/]")
        try: run_command(["cp",str(nanorc_file),str(backup)],as_user=TARGET_USER)
        except: shutil.copy(nanorc_file, backup)
    shutil.copy(NANORC_SOURCE_PATH, nanorc_file); os.chown(nanorc_file, pw.pw_uid, pw.pw_gid)
    try: # Ensure parent dirs are owned by user if created by root
        if nanorc_dir.stat().st_uid != pw.pw_uid: os.chown(nanorc_dir, pw.pw_uid, pw.pw_gid)
        if nanorc_dir.parent.name == ".config" and nanorc_dir.parent.stat().st_uid != pw.pw_uid:
            os.chown(nanorc_dir.parent, pw.pw_uid, pw.pw_gid)
    except Exception as e: log.debug(f"Nanorc dir chown issue (usually OK): {e}")
    log.info(f":floppy_disk: [magenta]{NANORC_SOURCE_FILE_NAME}[/] copied to {nanorc_dir}.")

# --- Post-Installation Verification ---
def perform_post_install_checks():
    log.info("Performing post-install checks...")
    tools = ["zsh","git","curl","python3","pip3","eza","dust","btop","bat","fzf","zoxide","atuin","nano"]
    # gnome-tweaks only checked if IS_FEDORA as it's installed conditionally
    if IS_FEDORA: tools.append("gnome-tweaks")
    
    report, all_ok = [], True
    for tool in tools:
        found_path = next((str(p/tool) for p in [TARGET_USER_HOME/".local/bin", TARGET_USER_HOME/".cargo/bin"] if (p/tool).is_file()), shutil.which(tool))
        if found_path:
            ver, ver_ok = " (version N/A)", False
            run_as = TARGET_USER if TARGET_USER_HOME.as_posix() in found_path else None
            try:
                for flag in ["--version", "-V", "version"]:
                    cmd = [found_path, "show", "pip"] if tool == "pip3" and flag == "--version" else [found_path, flag]
                    res = run_command(cmd, capture_output=True, text=True, check=False, as_user=run_as)
                    if res.returncode == 0 and res.stdout.strip():
                        out_line = res.stdout.strip().splitlines()[0]
                        if tool == "pip3" and "Version:" in res.stdout: # pip show pip parsing
                            out_line = next((l.split(':',1)[1].strip() for l in res.stdout.splitlines() if "Version:" in l),"")
                        ver = f" ([italic]{out_line}[/])"; ver_ok = True; break
                report.append(f":heavy_check_mark: [green]'{tool}' available[/]{ver if ver_ok else ' (version check failed)'}")
            except: report.append(f":heavy_check_mark: [green]'{tool}' available[/] (version check error)")
        else:
            is_base_tool = tool in ["zsh", "git", "curl", "nano", "python3", "pip3"]
            expected = (tool in DNF_PACKAGES and IS_FEDORA and tool != "gnome-tweaks") or \
                       (tool == "gnome-tweaks" and IS_FEDORA) or \
                       (tool in CARGO_TOOLS) or \
                       any(t['name'] == tool for t in SCRIPTED_TOOLS) or \
                       is_base_tool
            if expected: report.append(f":x: [bold red]'{tool}' FAILED to be found.[/]"); all_ok = False
            else: report.append(f":warning: [yellow]'{tool}' not found (may be expected).[/]")
    
    console.print(Panel("\n".join(report), title="[bold]Post-Installation Check Summary[/]", border_style="blue"))
    if all_ok: log.info("[bold green]Critical post-install checks passed.[/]")
    else: log.warning("[bold yellow]Some post-install checks failed. Review summary/logs.[/]")

# --- Main Setup Functions ---
def perform_initial_setup():
    console.rule("[bold sky_blue2]Initial Environment Setup[/]", style="sky_blue2")
    perform_system_update_check()
    check_critical_deps()
    install_dnf_packages(DNF_PACKAGES) # Base DNF packages
    install_oh_my_zsh()
    install_omz_plugins()
    install_cargo_tools()
    install_scripted_tools() # This will now handle zoxide .zshrc addition
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
# DNF packages specific to GNOME Extension Management
GNOME_MANAGEMENT_DNF_PACKAGES = [
    "gnome-tweaks",
    "gnome-shell-extensions", # Bundle that includes User Themes, etc.
    "gnome-extensions-app",
    "gnome-shell-extension-manager"
]

def manage_gnome_extensions():
    console.rule("[bold magenta]GNOME Shell Extension Management[/]", style="magenta")
    if not IS_FEDORA:
        log.warning("GNOME features best on GNOME desktops (e.g., Fedora).")
        if not Confirm.ask("Attempt anyway?", default=False): return
    
    if not shutil.which("gnome-extensions"): # gnome-extensions CLI is part of gnome-shell
        log.error("`gnome-extensions` CLI not found. Cannot manage extensions.")
        log.info("Ensure `gnome-shell` is installed. On Fedora, this is usually standard.")
        # Optionally install gnome-shell here if IS_FEDORA, but it's a core component.
        # install_dnf_packages(["gnome-shell"]) # if we want to be very aggressive
        return

    # Install GNOME management tools and base extension packages
    log.info("Installing/Verifying core GNOME management tools and base extension packages...")
    install_dnf_packages(GNOME_MANAGEMENT_DNF_PACKAGES)

    # Install DNF packages for specific extensions from GNOME_EXTENSIONS_CONFIG
    extension_dnf_packages = [ext["dnf_package"] for ext in GNOME_EXTENSIONS_CONFIG if "dnf_package" in ext]
    # Filter out packages already in GNOME_MANAGEMENT_DNF_PACKAGES if they overlap (e.g., user-themes from gnome-shell-extensions)
    unique_extension_dnf_pkgs = [pkg for pkg in extension_dnf_packages if pkg not in GNOME_MANAGEMENT_DNF_PACKAGES and pkg != "gnome-shell-extension-user-themes"] # user-themes is often in gnome-shell-extensions
    if unique_extension_dnf_pkgs:
        log.info("Installing/Verifying DNF packages for specific GNOME extensions...")
        install_dnf_packages(unique_extension_dnf_pkgs)
    
    log.info("Enabling configured GNOME Shell extensions...")
    enabled_new = False
    for ext_cfg in GNOME_EXTENSIONS_CONFIG:
        name, uuid = ext_cfg["name"], ext_cfg["uuid"]
        log.info(f"Processing: [cyan]{name}[/] (UUID: {uuid})")
        try:
            info_res = run_command(["gnome-extensions","info",uuid],as_user=TARGET_USER,capture_output=True,text=True,check=False)
            state = "NOT FOUND"
            if info_res.returncode == 0 and info_res.stdout:
                state = next((l.split(":",1)[1].strip() for l in info_res.stdout.splitlines() if l.startswith("State:")), "UNKNOWN")
            log.debug(f"Extension '{name}' state: {state}")

            if state == "ENABLED": log.info(f":heavy_check_mark: '[cyan]{name}[/]' already enabled.")
            elif state in ["DISABLED", "INITIALIZED", "ERROR"]:
                log.info(f"Enabling '[cyan]{name}[/]'...")
                with console.status(f"[green]Enabling {name}...[/]"):
                    run_command(["gnome-extensions","enable",uuid],as_user=TARGET_USER,check=True)
                log.info(f":arrow_up_small: '[cyan]{name}[/]' enabled."); enabled_new = True
            elif state == "NOT FOUND":
                log.error(f"[bold red]Ext '{name}' (UUID: {uuid}) not found via `gnome-extensions info`. DNF pkg '{ext_cfg.get('dnf_package','N/A')}' might be missing/incompatible.[/]")
            else: log.warning(f"Ext '{name}' in unexpected state: {state}. Manual check needed.")
        except subprocess.CalledProcessError as e:
            log.error(f"[bold red]Failed manage ext '{name}'. Cmd: {' '.join(e.cmd)}[/]")
            if e.stderr: log.error(f"[stderr]: {e.stderr.strip()}")
            if e.stdout: log.error(f"[stdout]: {e.stdout.strip()}")
        except Exception as e: log.error(f"[bold red]Unexpected error managing ext '{name}': {e}[/]"); console.print_exception(max_frames=3)

    if enabled_new: log.info("[yellow]GNOME Shell restart (Alt+F2, 'r', Enter) or logout/login may be needed.[/]")
    else: log.info("No new GNOME extensions enabled, or they were already active.")

    try: # List enabled extensions
        log.info("Currently enabled GNOME extensions:"); res = run_command(["gnome-extensions","list","--enabled"],as_user=TARGET_USER,capture_output=True,check=True,text=True)
        if res.stdout.strip(): console.print(res.stdout.strip())
        else: log.info("No enabled extensions found or session inactive.")
    except: log.warning("Could not list enabled GNOME extensions post-management.")
    console.print(Panel(Text("GNOME Extension Management Completed.", style="bold green"), expand=False))

# --- Main Application Logic ---
def display_main_menu():
    console.print(Panel(Text("Enhanced System Setup Utility", justify="center", style="bold white on dark_blue")))
    menu = {"1": ("Initial Environment Setup", perform_initial_setup),
            "2": ("Manage GNOME Shell Extensions", manage_gnome_extensions),
            "3": ("Exit", lambda: sys.exit(0))}
    exit_flag = False
    while True:
        console.rule("[bold gold1]Main Menu[/]", style="gold1")
        tbl = Table(show_header=False, box=None, padding=(0,1)); tbl.add_column(style="cyan",justify="right"); tbl.add_column()
        for k, (d,_) in menu.items(): tbl.add_row(f"[{k}]", d)
        console.print(Padding(tbl, (1,2)))
        choice = Prompt.ask("Choice", choices=list(menu.keys()), show_choices=False)
        
        exit_flag = (choice == "3")
        desc, action = menu[choice]
        log.info(f"Selected: ({choice}) {desc}")
        if action:
            try: action()
            except SystemExit: # Raised by menu option 3 or other sys.exit()
                console_output_path = TARGET_USER_HOME / "setup_script_console_output.txt" if TARGET_USER_HOME.is_absolute() else SCRIPT_DIR / "setup_script_console_output.txt"
                console.save_text(console_output_path); log.info(f"Console output saved to {console_output_path}")
                raise # Propagate SystemExit
            except Exception as e:
                log.exception(f"Error '{desc}': {e}"); console.print_exception(show_locals=True)
                console.print(Panel(f"Error in '{desc}'. Check logs.", title="[red]Action Failed[/]",style="red"))
        if exit_flag: break
        if not Confirm.ask("\nReturn to main menu?", default=True): exit_flag = True; break
    return exit_flag

def main():
    clean_exit_via_menu = False
    try:
        initialize_script()
        clean_exit_via_menu = display_main_menu()
    except SystemExit: log.info("Script exited via sys.exit().")
    except Exception as e:
        log.exception(f"[bold red]Unhandled critical error: {e}[/]"); console.print_exception(show_locals=True)
        console.print(Panel(f"Critical error. Logs: {LOG_FILE_PATH}", title="[red]SCRIPT FAILED[/]", style="red"))
        sys.exit(1)
    finally:
        log_path = LOG_FILE_PATH if LOG_FILE_PATH.is_absolute() else SCRIPT_DIR / LOG_FILE_NAME
        console_out_path = TARGET_USER_HOME / "setup_script_console_output.txt" if TARGET_USER_HOME.is_absolute() else SCRIPT_DIR / "setup_script_console_output.txt"
        # Save console if not already saved by a clean menu exit that called sys.exit()
        if not clean_exit_via_menu:
            try:
                if not console_out_path.exists(): # Simplified: save if it doesn't exist yet
                    console.save_text(console_out_path)
                    log.info(f"Console output saved (main finally) to {console_out_path}")
            except Exception as e_save: print(f"Error saving console (main finally): {e_save}", file=sys.stderr)
        log.info(f"Execution finished. Full log: [link=file://{log_path}]{log_path}[/link]")

if __name__ == "__main__":
    main()