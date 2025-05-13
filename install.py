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
import importlib # For reloading rich if upgraded

# Standard library logging, RichHandler will be added later if rich is available
import logging as std_logging

# Placeholder for rich components, will be imported after rich is confirmed
Console = None
Panel = None
Text = None
Confirm = None
Prompt = None
IntPrompt = None
RichHandler = None
Table = None
Padding = None

# Global console and log objects, initialized after rich is confirmed
console: Optional[Console] = None
log: Optional[std_logging.Logger] = None


def _ensure_rich_library() -> bool:
    """
    Checks for the 'rich' library. Installs/upgrades it if necessary.
    Returns True if rich is available, False otherwise.
    Uses standard print() for output as rich console is not yet available.
    """
    rich_module = None
    try:
        rich_module = importlib.import_module("rich")
        current_version = getattr(rich_module, "__version__", "unknown")
        print(f"Python 'rich' library found (version {current_version}). Checking for updates...", flush=True)
        try:
            pip_process = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "rich"],
                check=True, capture_output=True, text=True, timeout=60
            )
            if "Requirement already satisfied" not in pip_process.stdout and \
               "up-to-date" not in pip_process.stdout : # Check common phrases indicating no actual upgrade
                 print("Python 'rich' library has been updated. Reloading...", flush=True)
                 rich_module = importlib.reload(rich_module)
                 new_version = getattr(rich_module, "__version__", "unknown")
                 print(f"Python 'rich' library reloaded (new version {new_version}).", flush=True)
            else:
                print("Python 'rich' library is up-to-date.", flush=True)
            return True
        except subprocess.TimeoutExpired:
            print("Warning: Timeout while trying to upgrade 'rich'. Proceeding with installed version.", file=sys.stderr, flush=True)
            return True # Rich was already there, proceed
        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not upgrade 'rich': {e.stderr.strip()}. Proceeding with installed version.", file=sys.stderr, flush=True)
            return True # Still usable if upgrade failed but it was already there
        except Exception as e_upgrade:
            print(f"Warning: An error occurred while trying to upgrade 'rich': {e_upgrade}. Proceeding with installed version.", file=sys.stderr, flush=True)
            return True # Proceed if rich was initially found
    except ImportError:
        print("Python 'rich' library not found. Attempting to install it...", flush=True)
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "rich"],
                check=True, capture_output=True, text=True, timeout=60
            )
            print("Python 'rich' library installed successfully. Attempting to load it...", flush=True)
            rich_module = importlib.import_module("rich") # Try to import it now
            current_version = getattr(rich_module, "__version__", "unknown")
            print(f"Python 'rich' library loaded (version {current_version}).", flush=True)
            return True
        except subprocess.TimeoutExpired:
            print("ERROR: Timeout while trying to install 'rich'.", file=sys.stderr, flush=True)
            print("Please install 'rich' manually (e.g., 'python3 -m pip install rich') and then re-run this script.", file=sys.stderr, flush=True)
            return False
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to install 'rich' library using pip: {e.stderr.strip()}", file=sys.stderr, flush=True)
            print("Please install 'rich' manually (e.g., 'python3 -m pip install rich') and then re-run this script.", file=sys.stderr, flush=True)
            return False
        except ImportError:
            print("ERROR: 'rich' was reportedly installed by pip, but cannot be imported.", file=sys.stderr, flush=True)
            print("Please check your Python environment or try re-running the script.", file=sys.stderr, flush=True)
            return False
        except Exception as e_install:
            print(f"ERROR: An unexpected error occurred while trying to install 'rich': {e_install}", file=sys.stderr, flush=True)
            return False
    return False # Should not be reached if logic is correct

# --- Configuration (does not depend on rich) ---
ZSHRC_SOURCE_FILE_NAME = ".zshrc"
NANORC_SOURCE_FILE_NAME = ".nanorc"
ZSHRC_SUBDIRECTORY = "zsh"
NANORC_SUBDIRECTORY = "nano"
LOG_FILE_NAME = "nova_setup.log" # Changed log file name to match new title theme

DNF_PACKAGES = [
    "zsh", "python3", "python3-pip",
    "git", "curl", "stow", "dnf-plugins-core", "cargo",
    "powerline-fonts", "btop", "bat", "fzf",
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

# --- Global Variables (paths are fine, console/log initialized in main) ---
SCRIPT_DIR = Path(__file__).parent.resolve()
TARGET_USER = ""
TARGET_USER_HOME = Path(".")
LOG_FILE_PATH = Path(".") # Will be updated in initialize_script
IS_FEDORA = False

ZSHRC_SOURCE_PATH = SCRIPT_DIR / ZSHRC_SUBDIRECTORY / ZSHRC_SOURCE_FILE_NAME
NANORC_SOURCE_PATH = SCRIPT_DIR / NANORC_SUBDIRECTORY / NANORC_SOURCE_FILE_NAME

# --- Utility Functions (use global console and log, which are set in main) ---
def run_command(command: List[str] | str,
                check: bool = True,
                capture_output: bool = False,
                text: bool = True,
                as_user: Optional[str] = None,
                shell: bool = False,
                cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    # log will be initialized by the time this is called from main flow
    cmd_for_log = command if isinstance(command, str) else ' '.join(shlex.quote(str(s)) for s in command)
    if log: log.debug(f"Executing: {cmd_for_log}{f' as {as_user}' if as_user else ''}{f' in {cwd}' if cwd else ''}")
    else: print(f"DEBUG: Executing: {cmd_for_log}{f' as {as_user}' if as_user else ''}{f' in {cwd}' if cwd else ''}", flush=True)


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
                res_dbus = subprocess.run(shlex.split(dbus_address_cmd), capture_output=True, text=True, check=False, timeout=5)
                if res_dbus.returncode == 0:
                    for line_env in res_dbus.stdout.splitlines():
                        if line_env.startswith("DBUS_SESSION_BUS_ADDRESS="):
                            process_env['DBUS_SESSION_BUS_ADDRESS'] = line_env.split('=', 1)[1]
                            if log: log.debug(f"Set DBUS_SESSION_BUS_ADDRESS for user {as_user} via systemctl.")
                            break
                elif Path(f"/run/user/{pw_entry.pw_uid}/bus").exists(): 
                     process_env['DBUS_SESSION_BUS_ADDRESS'] = f"unix:path=/run/user/{pw_entry.pw_uid}/bus"
                     if log: log.debug(f"Set DBUS_SESSION_BUS_ADDRESS for user {as_user} via common path.")
            except Exception as e_dbus:
                if log: log.debug(f"Could not robustly determine DBUS_SESSION_BUS_ADDRESS for {as_user}: {e_dbus}.")
        result = subprocess.run(
            actual_command_to_run, check=check, capture_output=capture_output, text=text,
            shell=shell if not as_user else False, cwd=cwd, env=process_env, timeout=300 # 5 min timeout for most commands
        )
        return result
    except subprocess.TimeoutExpired as e:
        cmd_str_err = ' '.join(e.cmd) if isinstance(e.cmd, list) else e.cmd
        if log: log.error(f"Command '[bold cyan]{cmd_str_err}[/]' timed out after {e.timeout} seconds.")
        else: print(f"ERROR: Command '{cmd_str_err}' timed out.", file=sys.stderr, flush=True)
        raise
    except subprocess.CalledProcessError as e:
        cmd_str_err = ' '.join(e.cmd) if isinstance(e.cmd, list) else e.cmd
        if log:
            log.error(f"Command '[bold cyan]{cmd_str_err}[/]' failed with exit code {e.returncode}")
            if capture_output:
                if e.stdout: log.error(f"[stdout]: {e.stdout.strip()}")
                if e.stderr: log.error(f"[stderr]: {e.stderr.strip()}")
        else:
            print(f"ERROR: Command '{cmd_str_err}' failed with exit code {e.returncode}", file=sys.stderr, flush=True)
            if capture_output:
                if e.stdout: print(f"STDOUT: {e.stdout.strip()}", file=sys.stderr, flush=True)
                if e.stderr: print(f"STDERR: {e.stderr.strip()}", file=sys.stderr, flush=True)
        raise
    except FileNotFoundError:
        cmd_failed = final_command_parts[0] if final_command_parts and isinstance(final_command_parts, list) else str(actual_command_to_run)
        if log: log.error(f"Command not found: {cmd_failed.split()[0]}")
        else: print(f"ERROR: Command not found: {cmd_failed.split()[0]}", file=sys.stderr, flush=True)
        raise

def check_command_exists(command_name_parts: List[str] | str, as_user: Optional[str] = None) -> bool:
    try:
        cmd_to_verify = command_name_parts[0] if isinstance(command_name_parts, list) else command_name_parts.split()[0]
        check_cmd_str = f"command -v {shlex.quote(cmd_to_verify)}"
        run_command(check_cmd_str, as_user=as_user, shell=True, capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False

# --- Initialization ---
def initialize_script():
    global TARGET_USER, TARGET_USER_HOME, LOG_FILE_PATH # console and log are already global

    if os.geteuid() != 0:
        if log: log.critical("[bold red]Must be run as root (sudo).[/]")
        else: print("CRITICAL: Must be run as root (sudo).", file=sys.stderr, flush=True)
        sys.exit(1)

    TARGET_USER = os.getenv("SUDO_USER")
    if not TARGET_USER:
        if log: log.warning("No SUDO_USER. Targeting root user.")
        else: print("WARNING: No SUDO_USER. Targeting root user.", flush=True)
        TARGET_USER = pwd.getpwuid(os.geteuid()).pw_name
    
    try:
        pw_entry = pwd.getpwnam(TARGET_USER)
        TARGET_USER_HOME = Path(pw_entry.pw_dir)
    except KeyError:
        if log: log.critical(f"[bold red]User '{TARGET_USER}' not found.[/]")
        else: print(f"CRITICAL: User '{TARGET_USER}' not found.", file=sys.stderr, flush=True)
        sys.exit(1)
    
    if not TARGET_USER_HOME.is_dir():
        if log: log.critical(f"[bold red]Home dir {TARGET_USER_HOME} missing.[/]")
        else: print(f"CRITICAL: Home dir {TARGET_USER_HOME} missing.", file=sys.stderr, flush=True)
        sys.exit(1)
    
    LOG_FILE_PATH = TARGET_USER_HOME / LOG_FILE_NAME # Update global LOG_FILE_PATH

    # Add file handler to the logger (logger should be initialized by now)
    if log:
        file_handler = std_logging.FileHandler(LOG_FILE_PATH)
        # Match RichHandler's default format for consistency if possible, or keep it simple
        file_formatter = std_logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_formatter)
        log.addHandler(file_handler) # Add file handler to the 'rich' logger
        log.info(f"--- Nova System Setup Script Initialized ---")
        log.info(f"Target user: [yellow]{TARGET_USER}[/], home: [yellow]{TARGET_USER_HOME}[/].")
        log.info(f"Detailed logging to: [cyan]{LOG_FILE_PATH}[/]")
    else: # Should not happen if rich setup is correct
        print(f"WARNING: Logger not available for file logging setup. Log path: {LOG_FILE_PATH}", flush=True)


    if not ZSHRC_SOURCE_PATH.is_file() or not NANORC_SOURCE_PATH.is_file():
        if log: log.critical("[bold red]Source .zshrc or .nanorc missing in script directory/subdirectories. Exiting.[/]")
        else: print("CRITICAL: Source .zshrc or .nanorc missing. Exiting.", file=sys.stderr, flush=True)
        sys.exit(1)
    if log: log.info("Source config files (.zshrc, .nanorc) found.")


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
            dnf_conf_file, dnf_parser = Path("/etc/dnf/dnf.conf"), configparser.ConfigParser(allow_no_value=True, comment_prefixes=('#',';'), inline_comment_prefixes=('#',';'), strict=False)
            dnf_parser.optionxform = str # Preserve key case
            needs_write = False
            if dnf_conf_file.is_file(): 
                try: dnf_parser.read(dnf_conf_file, encoding='utf-8')
                except Exception as e: log.warning(f"Parse error {dnf_conf_file}: {e}")
            if not dnf_parser.has_section('main'): dnf_parser.add_section('main'); needs_write=True
            for k,v in {"max_parallel_downloads": "10", "fastestmirror": "true"}.items():
                if dnf_parser.get('main', k, fallback=None) != v: dnf_parser.set('main', k, v); needs_write=True
            if needs_write:
                if dnf_conf_file.is_file(): shutil.copy2(dnf_conf_file, dnf_conf_file.with_suffix(f"{dnf_conf_file.suffix}.bkp_nova_{os.urandom(4).hex()}"))
                with open(dnf_conf_file, 'w', encoding='utf-8') as cf: dnf_parser.write(cf, space_around_delimiters=False)
                log.info(f"Updated DNF config: {dnf_conf_file}")
            else: log.info(f"DNF settings in {dnf_conf_file} already configured as desired.")
            
            try: run_command(["dnf", "install", "-y", "fedora-workstation-repositories"]); log.info("Fedora third-party repos package checked/installed.")
            except Exception as e: log.error(f"Failed `fedora-workstation-repositories` install: {e}")
            
            try:
                ver = run_command("rpm -E %fedora", shell=True, capture_output=True, text=True, check=True).stdout.strip()
                if not ver.isdigit(): raise ValueError(f"Bad Fedora version from rpm: {ver}")
                for rt in ["free", "nonfree"]: run_command(["dnf", "install", "-y", f"https://download1.rpmfusion.org/{rt}/fedora/rpmfusion-{rt}-release-{ver}.noarch.rpm"])
                log.info("RPM Fusion repositories setup/checked.")
            except Exception as e: log.error(f"RPM Fusion setup failed: {e}")

            with console.status("[bold green]Updating/upgrading system (dnf)...[/]", spinner="dots"):
                try: run_command(["dnf", "update", "-y"]); run_command(["dnf", "upgrade", "-y"])
                except subprocess.CalledProcessError: log.error("[bold red]DNF update/upgrade failed.")
                except subprocess.TimeoutExpired: log.error("[bold red]DNF update/upgrade timed out.")
            log.info(":white_check_mark: System update/upgrade attempt complete.")
        else:
            log.warning(f"OS detected: [yellow]{pretty_name}[/]. This script is optimized for Fedora.")
            if not Confirm.ask("Do you want to continue with the script anyway?", default=False, console=console):
                log.info("Exiting script as per user request."); sys.exit(0)
            log.warning("Proceeding on a non-Fedora system. DNF-specific installations will be skipped.")
    except Exception as e: log.error(f"OS check/config error: {e}"); console.print_exception(max_frames=3)


def install_dnf_packages(packages_list: List[str]):
    if not IS_FEDORA:
        if packages_list: log.warning(f"Not a Fedora system. Please ensure equivalents of these DNF packages are installed: {', '.join(packages_list)}")
        return
    if not packages_list: log.info("No DNF packages specified for installation in this step."); return

    log.info(f"Attempting to install/verify {len(packages_list)} DNF packages individually...")
    failed_packages, installed_any_new = [], False
    for i, pkg_name in enumerate(packages_list):
        log.info(f"({i+1}/{len(packages_list)}) Processing DNF package: [bold blue]{pkg_name}[/bold blue]...")
        with console.status(f"[green]Installing/verifying {pkg_name}...[/]", spinner="earth"):
            try:
                res = run_command(["dnf", "install", "-y", pkg_name], capture_output=True, text=True) # check=True is default
                if "Nothing to do" not in res.stdout and "already installed" not in res.stdout:
                    installed_any_new = True
                    log.info(f":heavy_check_mark: DNF package '[cyan]{pkg_name}[/]' installed successfully.")
                else:
                    log.info(f":package: DNF package '[cyan]{pkg_name}[/]' was already installed or verified.")
            except subprocess.CalledProcessError as e:
                log.error(f"[bold red]Failed to install DNF package '{pkg_name}'. DNF exit code: {e.returncode}[/]")
                if e.stderr: log.error(f"[stderr for {pkg_name}]: {e.stderr.strip()}")
                elif e.stdout: log.error(f"[stdout for {pkg_name}]: {e.stdout.strip()}") # DNF errors can be in stdout
                failed_packages.append(pkg_name)
            except subprocess.TimeoutExpired:
                log.error(f"[bold red]Timeout during DNF install of '{pkg_name}'.[/]")
                failed_packages.append(pkg_name)
            except Exception as e_unexpected:
                log.error(f"[bold red]Unexpected error installing DNF package '{pkg_name}': {e_unexpected}[/]"); failed_packages.append(pkg_name)
                console.print_exception(max_frames=3)

    if not failed_packages:
        log.info(f":white_check_mark: All {len(packages_list)} DNF packages processed successfully{' (some were newly installed).' if installed_any_new else ' (all were verified or already present).'}")
    else:
        log.warning(f"[bold yellow]DNF package installation summary: {len(failed_packages)} failed packages: {', '.join(failed_packages)}[/]")
        log.warning("Please check DNF logs (e.g., /var/log/dnf.log or dnf history) and the output above for details.")

# --- Tool Installation Functions ---
def check_critical_deps():
    log.info("Checking critical dependencies (git, curl)...")
    missing_deps = [dep for dep in ["git", "curl"] if not shutil.which(dep)]
    if missing_deps:
        if IS_FEDORA: log.warning(f"Critical dependencies missing: {', '.join(missing_deps)}. Will be attempted via DNF.")
        else: log.critical(f"Critical dependencies missing: {', '.join(missing_deps)}. Please install them and re-run."); sys.exit(1)
    else: log.info(":heavy_check_mark: Critical dependencies (git, curl) are available.")

def install_oh_my_zsh():
    omz_dir = TARGET_USER_HOME / ".oh-my-zsh"
    if omz_dir.is_dir(): log.warning(f"Oh My Zsh already found in [cyan]{omz_dir}[/]. Skipping installation."); return
    log.info("Installing Oh My Zsh for user "+TARGET_USER+"..."); cmd = "curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh | sh -s -- --unattended --keep-zshrc"
    with console.status("[green]Installing Oh My Zsh...[/]", spinner="monkey"):
        try: run_command(cmd, as_user=TARGET_USER, shell=True, check=True); log.info(":rocket: Oh My Zsh installed successfully.")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e: log.error(f"[bold red]Oh My Zsh installation failed: {e}[/]")
        except Exception as e_unexp: log.error(f"[bold red]Unexpected error during Oh My Zsh installation: {e_unexp}[/]")

def install_omz_plugins():
    log.info("Installing Oh My Zsh plugins..."); plugins_dir = TARGET_USER_HOME / ".oh-my-zsh/custom/plugins"
    try: run_command(["mkdir", "-p", str(plugins_dir)], as_user=TARGET_USER)
    except Exception as e_mkdir: log.error(f"Failed to create OMZ plugins dir {plugins_dir}: {e_mkdir}"); return

    for p_info in OMZ_PLUGINS:
        p_name, p_url = p_info["name"], p_info["url"]
        target_plugin_dir = plugins_dir / p_name
        if target_plugin_dir.is_dir(): log.warning(f"OMZ Plugin '[cyan]{p_name}[/]' already present. Skipping."); continue
        log.info(f"Cloning OMZ plugin '[cyan]{p_name}[/]' from {p_url}...")
        with console.status(f"[green]Cloning {p_name}...[/]", spinner="dots"):
            try: run_command(["git", "clone", "--depth", "1", p_url, str(target_plugin_dir)], as_user=TARGET_USER); log.info(f":heavy_check_mark: OMZ Plugin '[cyan]{p_name}[/]' installed.")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e_git: log.error(f"[bold red]Failed to clone OMZ plugin '{p_name}': {e_git}[/]")
            except Exception as e_unexp: log.error(f"[bold red]Unexpected error cloning OMZ plugin '{p_name}': {e_unexp}[/]")


def install_cargo_tools():
    log.info(f"Attempting to install Cargo tools: [cyan]{', '.join(CARGO_TOOLS)}[/]...")
    cargo_cmd_path_user = TARGET_USER_HOME / ".cargo/bin/cargo"
    effective_cargo_cmd = str(cargo_cmd_path_user) if cargo_cmd_path_user.is_file() else shutil.which("cargo")
    
    if not effective_cargo_cmd:
        log.warning("[yellow]Cargo command not found.[/] Cargo is typically installed via rustup (https://rustup.rs). Skipping Cargo tools installation."); return
    
    log.info(f"Using cargo command: [blue]{effective_cargo_cmd}[/]")
    for tool_name in CARGO_TOOLS:
        try: # Check if already installed
            list_res = run_command([effective_cargo_cmd,"install","--list"],as_user=TARGET_USER,capture_output=True,text=True,check=False)
            if list_res.returncode == 0 and f"{tool_name} v" in list_res.stdout: # Simple check
                log.warning(f"Cargo tool '[cyan]{tool_name}[/]' seems to be already installed. Skipping."); continue
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e_list:
            log.debug(f"Could not check if cargo tool '{tool_name}' is installed (or cargo not found for user {TARGET_USER}): {e_list}")
        except Exception as e_unexp_list: log.debug(f"Unexpected error checking cargo tool '{tool_name}': {e_unexp_list}")

        log.info(f"Installing '[cyan]{tool_name}[/]' with cargo...")
        with console.status(f"[green]Installing {tool_name} with cargo...[/]", spinner="bouncingBar"):
            try: run_command([effective_cargo_cmd, "install", tool_name], as_user=TARGET_USER); log.info(f":crates: Cargo tool '[cyan]{tool_name}[/]' installed successfully.")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e_install: log.error(f"[bold red]Failed to install Cargo tool '{tool_name}': {e_install}[/]")
            except Exception as e_unexp_install: log.error(f"[bold red]Unexpected error installing Cargo tool '{tool_name}': {e_unexp_install}[/]")


def install_scripted_tools():
    for tool_info in SCRIPTED_TOOLS:
        name, check_cmd_parts, url, method = tool_info["name"], shlex.split(tool_info["check_command"]), tool_info["url"], tool_info["method"]
        log.info(f"Processing scripted tool: '[cyan]{name}[/]'...")
        try:
            if check_command_exists(check_cmd_parts, as_user=TARGET_USER):
                run_command(check_cmd_parts, as_user=TARGET_USER, capture_output=True, check=True) # Try to run version check
                log.warning(f"'[cyan]{name}[/]' seems to be already installed and version check successful. Skipping."); continue
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            log.debug(f"'{name}' not found, version check failed, or command timed out. Proceeding with install/update.")
        except Exception as e_check: log.debug(f"Unexpected error checking '{name}': {e_check}. Proceeding with install.")
        
        log.info(f"Downloading and executing install script for '[cyan]{name}[/]' from {url} using '{method}'...")
        install_cmd_str = f"curl -fsSL {url} | {method}"
        with console.status(f"[green]Installing {name} via script...[/]", spinner="arrow3"):
            try:
                run_command(install_cmd_str, as_user=TARGET_USER, shell=True, check=True)
                # Verify again after install attempt
                if check_command_exists(check_cmd_parts, as_user=TARGET_USER):
                    log.info(f":white_check_mark: '[cyan]{name}[/]' installed/updated successfully via script.")
                    # --- Zoxide .zshrc fix ---
                    if name == "zoxide":
                        zshrc_file_path = TARGET_USER_HOME / ".zshrc"
                        zoxide_init_cmd_line = 'eval "$(zoxide init zsh)"'
                        try:
                            if zshrc_file_path.is_file():
                                current_zshrc_content = zshrc_file_path.read_text(encoding='utf-8')
                                if zoxide_init_cmd_line not in current_zshrc_content:
                                    log.info(f"Adding '{zoxide_init_cmd_line}' to [magenta]{zshrc_file_path}[/] for user {TARGET_USER}")
                                    with open(zshrc_file_path, "a", encoding='utf-8') as zf:
                                        zf.write(f"\n# Added by Nova System Setup for zoxide\n{zoxide_init_cmd_line}\n")
                                    # Ensure correct ownership as root appended the line
                                    pw_info_user = pwd.getpwnam(TARGET_USER)
                                    os.chown(zshrc_file_path, pw_info_user.pw_uid, pw_info_user.pw_gid)
                                    log.info(f"Appended zoxide initialization to [magenta]{zshrc_file_path}[/].")
                                else:
                                    log.info(f"Zoxide initialization line already present in [magenta]{zshrc_file_path}[/].")
                            else:
                                log.warning(f"[yellow]{zshrc_file_path}[/] not found. User {TARGET_USER} may need to add zoxide init manually: '{zoxide_init_cmd_line}'[/]")
                        except Exception as e_zoxide_rc:
                            log.error(f"[bold red]Error adding zoxide init to .zshrc: {e_zoxide_rc}[/]")
                    # --- End zoxide fix ---
                else: log.error(f"[bold red]Installation of '[cyan]{name}[/]' via script might have failed (command not found after install).[/]")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e_script:
                log.error(f"[bold red]Installation of '{name}' failed via script: {e_script}[/]")
            except Exception as e_unexp_script:
                log.error(f"[bold red]Unexpected error during scripted install of '{name}': {e_unexp_script}[/]")

# --- Configuration File Management ---
def copy_config_files():
    log.info("Copying configuration files...")
    pw_user_info = pwd.getpwnam(TARGET_USER)
    
    # Zshrc
    target_zshrc_path = TARGET_USER_HOME / ".zshrc"
    log.info(f"Copying [magenta]{ZSHRC_SOURCE_FILE_NAME}[/] to [cyan]{target_zshrc_path}[/]")
    if target_zshrc_path.exists():
        backup_zshrc_path = TARGET_USER_HOME / f".zshrc.backup_nova_{os.urandom(4).hex()}"
        log.warning(f"Backing up existing .zshrc to [cyan]{backup_zshrc_path}[/]")
        try: run_command(["cp",str(target_zshrc_path),str(backup_zshrc_path)],as_user=TARGET_USER)
        except Exception: shutil.copy(target_zshrc_path, backup_zshrc_path) # Fallback
    try:
        shutil.copy(ZSHRC_SOURCE_PATH, target_zshrc_path)
        os.chown(target_zshrc_path, pw_user_info.pw_uid, pw_user_info.pw_gid)
        log.info(f":floppy_disk: [magenta]{ZSHRC_SOURCE_FILE_NAME}[/] copied successfully.")
    except Exception as e_zshrc: log.error(f"[bold red]Failed to copy .zshrc: {e_zshrc}[/]")

    # Nanorc
    nanorc_config_dir = TARGET_USER_HOME / ".config/nano"
    target_nanorc_path = nanorc_config_dir / "nanorc"
    try: run_command(["mkdir","-p",str(nanorc_config_dir)],as_user=TARGET_USER)
    except Exception as e_mkdir_nano: log.error(f"Failed to create nano config dir {nanorc_config_dir}: {e_mkdir_nano}"); return

    log.info(f"Copying [magenta]{NANORC_SOURCE_FILE_NAME}[/] to [cyan]{target_nanorc_path}[/]")
    if target_nanorc_path.exists():
        backup_nanorc_path = nanorc_config_dir / f"nanorc.backup_nova_{os.urandom(4).hex()}"
        log.warning(f"Backing up existing nanorc to [cyan]{backup_nanorc_path}[/]")
        try: run_command(["cp",str(target_nanorc_path),str(backup_nanorc_path)],as_user=TARGET_USER)
        except Exception: shutil.copy(target_nanorc_path, backup_nanorc_path)
    try:
        shutil.copy(NANORC_SOURCE_PATH, target_nanorc_path)
        os.chown(target_nanorc_path, pw_user_info.pw_uid, pw_user_info.pw_gid)
        # Ensure parent dirs are owned by user if root created them via shutil.copy before chown
        if nanorc_config_dir.stat().st_uid != pw_user_info.pw_uid: os.chown(nanorc_config_dir, pw_user_info.pw_uid, pw_user_info.pw_gid)
        if nanorc_config_dir.parent.name == ".config" and nanorc_config_dir.parent.stat().st_uid != pw_user_info.pw_uid:
            os.chown(nanorc_config_dir.parent, pw_user_info.pw_uid, pw_user_info.pw_gid)
        log.info(f":floppy_disk: [magenta]{NANORC_SOURCE_FILE_NAME}[/] copied successfully to {nanorc_config_dir}.")
    except Exception as e_nanorc: log.error(f"[bold red]Failed to copy nanorc: {e_nanorc}[/]")


# --- Post-Installation Verification ---
def perform_post_install_checks():
    log.info("Performing post-installation checks...")
    tools_to_verify = ["zsh","git","curl","python3","pip3","eza","dust","btop","bat","fzf","zoxide","atuin","nano"]
    if IS_FEDORA: tools_to_verify.append("gnome-tweaks") # Only check if it was supposed to be installed
    
    report_lines, all_tools_ok = [], True
    for tool_name_check in tools_to_verify:
        abs_path_tool = next((str(user_p / tool_name_check) for user_p in [TARGET_USER_HOME/".local/bin", TARGET_USER_HOME/".cargo/bin"] if (user_p/tool_name_check).is_file()), shutil.which(tool_name_check))
        if abs_path_tool:
            version_str, version_checked_ok = " (version N/A)", False
            user_to_run_as = TARGET_USER if TARGET_USER_HOME.as_posix() in abs_path_tool else None
            try:
                for v_flag_opt in ["--version", "-V", "version"]: # Common version flags
                    cmd_list_ver = [abs_path_tool, "show", "pip"] if tool_name_check == "pip3" and v_flag_opt == "--version" else [abs_path_tool, v_flag_opt]
                    res_ver = run_command(cmd_list_ver, capture_output=True, text=True, check=False, as_user=user_to_run_as)
                    if res_ver.returncode == 0 and res_ver.stdout.strip():
                        output_first_line = res_ver.stdout.strip().splitlines()[0]
                        if tool_name_check == "pip3" and "Version:" in res_ver.stdout: # Specific parsing for pip show pip
                            output_first_line = next((line.split(':',1)[1].strip() for line in res_ver.stdout.splitlines() if "Version:" in line),"")
                        version_str = f" ([italic]{output_first_line}[/])"; version_checked_ok = True; break
                report_lines.append(f":heavy_check_mark: [green]Tool '[cyan]{tool_name_check}[/]' is available[/]{version_str if version_checked_ok else ' (version check failed or no output)'}")
            except Exception as e_ver: report_lines.append(f":heavy_check_mark: [green]Tool '[cyan]{tool_name_check}[/]' is available[/] (unexpected error during version check: {e_ver})")
        else: # Tool not found
            # Determine if this tool was expected to be installed by this script
            is_gnome_tool_for_fedora = tool_name_check == "gnome-tweaks" and IS_FEDORA
            is_base_dnf_pkg = tool_name_check in DNF_PACKAGES and IS_FEDORA
            is_cargo_tool = tool_name_check in CARGO_TOOLS
            is_scripted_tool = any(t['name'] == tool_name_check for t in SCRIPTED_TOOLS)
            is_fundamental_tool = tool_name_check in ["zsh", "git", "curl", "nano", "python3", "pip3"]

            if is_base_dnf_pkg or is_cargo_tool or is_scripted_tool or is_fundamental_tool or is_gnome_tool_for_fedora :
                report_lines.append(f":x: [bold red]Tool '[cyan]{tool_name_check}[/]' FAILED to be found (was expected).[/]"); all_tools_ok = False
            else:
                report_lines.append(f":warning: [yellow]Tool '[cyan]{tool_name_check}[/]' not found (may be expected if not part of core install).[/]")
    
    console.print(Panel("\n".join(report_lines), title="[bold]Post-Installation Check Summary[/]", border_style="blue", expand=False))
    if all_tools_ok: log.info("[bold green]All critical post-installation checks seem to have passed.[/]")
    else: log.warning("[bold yellow]Some post-installation checks failed. Please review the summary and logs.[/]")

# --- Main Setup Functions ---
def perform_initial_setup():
    console.rule("[bold sky_blue2]Starting Initial Environment Setup[/]", style="sky_blue2")
    perform_system_update_check()
    check_critical_deps()
    install_dnf_packages(DNF_PACKAGES) # Installs base DNF packages
    install_oh_my_zsh()
    install_omz_plugins()
    install_cargo_tools()
    install_scripted_tools() # Includes zoxide .zshrc fix
    copy_config_files()
    perform_post_install_checks()
    console.print(Panel(Text("Initial Environment Setup Process Completed!", style="bold green"), expand=False))

GNOME_EXTENSIONS_CONFIG: List[Dict[str, str]] = [
    {"name": "User Themes", "uuid": "user-theme@gnome-shell-extensions.gcampax.github.com", "dnf_package": "gnome-shell-extension-user-themes"}, # Often part of gnome-shell-extensions
    {"name": "Blur My Shell", "uuid": "blur-my-shell@aunetx", "dnf_package": "gnome-shell-extension-blur-my-shell"},
    {"name": "Burn My Windows", "uuid": "burn-my-windows@schneegans.github.com", "dnf_package": "gnome-shell-extension-burn-my-windows"},
    {"name": "Vitals (System Monitor)", "uuid": "Vitals@CoreCoding.com", "dnf_package": "gnome-shell-extension-vitals"},
    {"name": "Caffeine", "uuid": "caffeine@patapon.info", "dnf_package": "gnome-shell-extension-caffeine"},
]
GNOME_MANAGEMENT_DNF_PACKAGES = [ # DNF packages for core GNOME extension management and tweaking
    "gnome-tweaks", "gnome-shell-extensions", "gnome-extensions-app", "gnome-shell-extension-manager"
]

def manage_gnome_extensions():
    console.rule("[bold magenta]GNOME Shell Extension Management[/]", style="magenta")
    if not IS_FEDORA:
        log.warning("GNOME extension management is primarily for GNOME desktops (like Fedora).")
        if not Confirm.ask("Attempt to proceed anyway?", default=False, console=console): return
    
    if not shutil.which("gnome-extensions"): # `gnome-extensions` CLI is part of `gnome-shell`
        log.error("`gnome-extensions` command-line tool not found. This is essential for managing extensions.")
        log.info("Ensure `gnome-shell` is installed. On Fedora, this package is usually standard.")
        return

    # Install core GNOME management tools and base extension packages first
    log.info("Installing/Verifying DNF packages for core GNOME management tools and base extensions...")
    install_dnf_packages(GNOME_MANAGEMENT_DNF_PACKAGES)

    # Install DNF packages for specific extensions listed in GNOME_EXTENSIONS_CONFIG
    # Filter out any packages that might have already been covered by GNOME_MANAGEMENT_DNF_PACKAGES
    # (e.g., gnome-shell-extension-user-themes is often part of the gnome-shell-extensions bundle)
    specific_extension_dnf_pkgs_to_install = [
        ext_cfg["dnf_package"] for ext_cfg in GNOME_EXTENSIONS_CONFIG 
        if "dnf_package" in ext_cfg and ext_cfg["dnf_package"] not in GNOME_MANAGEMENT_DNF_PACKAGES
    ]
    # Explicitly handle gnome-shell-extension-user-themes if it's listed but not covered by a bundle
    if "gnome-shell-extension-user-themes" in specific_extension_dnf_pkgs_to_install and \
       "gnome-shell-extensions" in GNOME_MANAGEMENT_DNF_PACKAGES:
        # if gnome-shell-extensions is installed, user-themes is likely covered, so remove from specific list
        if "gnome-shell-extension-user-themes" in specific_extension_dnf_pkgs_to_install:
             specific_extension_dnf_pkgs_to_install.remove("gnome-shell-extension-user-themes")


    if specific_extension_dnf_pkgs_to_install:
        log.info("Installing/Verifying DNF packages for specific GNOME extensions...")
        install_dnf_packages(specific_extension_dnf_pkgs_to_install)
    
    log.info("Attempting to enable configured GNOME Shell extensions...")
    any_newly_enabled = False
    for ext_config_item in GNOME_EXTENSIONS_CONFIG:
        ext_name, ext_uuid = ext_config_item["name"], ext_config_item["uuid"]
        log.info(f"Processing GNOME extension: [cyan]{ext_name}[/] (UUID: {ext_uuid})")
        try:
            # Check current state of the extension
            info_cmd_res = run_command(["gnome-extensions","info",ext_uuid],as_user=TARGET_USER,capture_output=True,text=True,check=False)
            current_ext_state = "NOT FOUND" # Default if info command fails or extension not listed
            if info_cmd_res.returncode == 0 and info_cmd_res.stdout:
                current_ext_state = next((line.split(":",1)[1].strip() for line in info_cmd_res.stdout.splitlines() if line.startswith("State:")), "UNKNOWN")
            log.debug(f"Extension '{ext_name}' current state reported by `gnome-extensions info`: {current_ext_state}")

            if current_ext_state == "ENABLED":
                log.info(f":heavy_check_mark: Extension '[cyan]{ext_name}[/]' is already enabled.")
            elif current_ext_state in ["DISABLED", "INITIALIZED", "ERROR"]: # ERROR state might occur if installed but schema missing, enable might fix.
                log.info(f"Attempting to enable extension '[cyan]{ext_name}[/]'...")
                with console.status(f"[green]Enabling {ext_name}...[/]"):
                    run_command(["gnome-extensions","enable",ext_uuid],as_user=TARGET_USER,check=True)
                log.info(f":arrow_up_small: Extension '[cyan]{ext_name}[/]' enabled successfully.")
                any_newly_enabled = True
            elif current_ext_state == "NOT FOUND":
                # This case implies DNF install might have failed or package doesn't exist for this shell version / is not discoverable
                log.error(f"[bold red]Extension '[cyan]{ext_name}[/]' (UUID: {ext_uuid}) not found by `gnome-extensions info` command. The DNF package '{ext_config_item.get('dnf_package', 'N/A')}' might be missing, incompatible, or failed to install correctly.[/]")
            else: # UNKNOWN or other states
                 log.warning(f"Extension '[cyan]{ext_name}[/]' is in an unexpected state: {current_ext_state}. Manual check might be needed.")
        except subprocess.CalledProcessError as e_manage_ext:
            log.error(f"[bold red]Failed to manage GNOME extension '[cyan]{ext_name}[/] (UUID: {ext_uuid}). Command: {' '.join(e_manage_ext.cmd)}[/]")
            if e_manage_ext.stderr: log.error(f"[stderr]: {e_manage_ext.stderr.strip()}")
            if e_manage_ext.stdout: log.error(f"[stdout]: {e_manage_ext.stdout.strip()}") # gnome-extensions might put errors in stdout
        except subprocess.TimeoutExpired as e_timeout_ext:
            log.error(f"[bold red]Timeout while managing GNOME extension '[cyan]{ext_name}[/]: {e_timeout_ext}[/]")
        except Exception as e_unexp_ext:
            log.error(f"[bold red]An unexpected error occurred while managing GNOME extension '[cyan]{ext_name}[/]: {e_unexp_ext}[/]")
            console.print_exception(max_frames=3)

    if any_newly_enabled:
        log.info("[bold yellow]Some GNOME extensions were newly enabled. A GNOME Shell restart (Alt+F2, then 'r', then Enter) or a logout/login may be required for all changes to take full effect.[/]")
    else:
        log.info("No new GNOME extensions were enabled in this run, or they were already active.")

    try: # List enabled extensions for confirmation
        log.info("Listing currently enabled GNOME extensions for user "+TARGET_USER+":")
        result_list_enabled = run_command(["gnome-extensions","list","--enabled"],as_user=TARGET_USER,capture_output=True,check=True,text=True)
        if result_list_enabled.stdout.strip():
             console.print("[bold]Currently enabled GNOME extensions:[/]")
             console.print(result_list_enabled.stdout.strip())
        else: log.info("No enabled GNOME extensions found for the user, or the user session might be inactive for `gnome-extensions` command.")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e_list_final:
        log.warning(f"Could not list enabled GNOME extensions post-management: {e_list_final}")
    except Exception as e_unexp_list_final:
        log.warning(f"Unexpected error listing enabled GNOME extensions: {e_unexp_list_final}")

    console.print(Panel(Text("GNOME Extension Management process completed.", style="bold green"), expand=False))


# --- Main Application Logic ---
def display_main_menu():
    # console should be initialized by now
    console.print(Panel(Text("✨ Nova System Setup ✨", justify="center", style="bold white on dark_blue"), expand=False)) # New Title
    
    menu_options: Dict[str, Tuple[str, Callable[[], None]]] = {
        "1": ("Perform Initial Environment Setup", perform_initial_setup),
        "2": ("Manage GNOME Shell Extensions", manage_gnome_extensions),
        "3": ("Exit Nova Setup", lambda: sys.exit(0)) # Updated exit label
    }
    main_menu_exit_flag = False
    while True:
        console.rule("[bold gold1]Main Menu[/]", style="gold1")
        menu_table = Table(show_header=False, box=None, padding=(0,1))
        menu_table.add_column(style="cyan", justify="right"); menu_table.add_column()
        for key_choice, (desc_choice,_) in menu_options.items(): menu_table.add_row(f"[{key_choice}]", desc_choice)
        console.print(Padding(menu_table, (1,2)))
        
        user_choice = Prompt.ask("Your choice", choices=list(menu_options.keys()), show_choices=False, console=console)
        
        main_menu_exit_flag = (user_choice == "3")
        selected_desc, selected_action = menu_options[user_choice]
        log.info(f"User selected menu option: ({user_choice}) {selected_desc}")
        
        if selected_action:
            try: selected_action() # Execute the chosen function
            except SystemExit: # Raised by menu option "3" (Exit) or other explicit sys.exit()
                log.info(f"Exiting '{selected_desc}' due to SystemExit.")
                # Console output saving is handled in main's finally block or if this is the exit option from menu
                if main_menu_exit_flag: # If this was the "Exit" menu option
                    console_output_final_path = TARGET_USER_HOME / "nova_setup_console_output.txt" if TARGET_USER_HOME.is_absolute() else SCRIPT_DIR / "nova_setup_console_output.txt"
                    try: console.save_text(console_output_final_path); log.info(f"Console output saved to {console_output_final_path}")
                    except Exception as e_save_exit: log.error(f"Failed to save console output on exit: {e_save_exit}")
                raise # Re-raise SystemExit to terminate the script
            except Exception as e_action:
                log.exception(f"An error occurred during '{selected_desc}': {e_action}")
                console.print_exception(show_locals=True, max_frames=5)
                console.print(Panel(f"An error occurred in '{selected_desc}'. Please check the logs at {LOG_FILE_PATH} for details.", title="[bold red]Action Failed[/]", border_style="red"))
        
        if main_menu_exit_flag: break # Exit the while loop if "Exit" was chosen
        
        if not Confirm.ask("\nReturn to main menu?", default=True, console=console):
            log.info("User chose not to return to main menu. Exiting.")
            main_menu_exit_flag = True # Treat "No" as an exit condition
            break
            
    return main_menu_exit_flag # Return whether the menu loop was exited via the "Exit" option or "No" to continue


def main():
    global console, log # Allow assignment to global console and log
    global Console, Panel, Text, Confirm, Prompt, IntPrompt, RichHandler, Table, Padding # To assign imported rich components

    # Phase 1: Ensure 'rich' is available. This uses standard print().
    if not _ensure_rich_library():
        sys.exit(1) # _ensure_rich_library prints error details

    # Phase 2: 'rich' is available, import its components and set up global console/logger.
    # These imports are now safe.
    from rich.console import Console as RichConsoleImport
    from rich.panel import Panel as RichPanelImport
    from rich.text import Text as RichTextImport
    from rich.prompt import Confirm as RichConfirmImport, Prompt as RichPromptImport, IntPrompt as RichIntPromptImport
    from rich.logging import RichHandler as RichLoggingHandlerImport
    from rich.table import Table as RichTableImport
    from rich.padding import Padding as RichPaddingImport

    # Assign to global component placeholders for use by other functions
    Console, Panel, Text, Confirm, Prompt, IntPrompt, RichHandler, Table, Padding = \
        RichConsoleImport, RichPanelImport, RichTextImport, RichConfirmImport, RichPromptImport, RichIntPromptImport, RichLoggingHandlerImport, RichTableImport, RichPaddingImport
    
    console = Console(record=True, log_time=False, log_path=False) # Initialize global console

    # Configure standard logging to use RichHandler
    std_logging.basicConfig(
        level="INFO", # Set desired root logger level
        format="%(message)s", # RichHandler will format it nicely
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, markup=True, show_path=False, show_level=True)]
    )
    log = std_logging.getLogger("nova-setup") # Use a specific logger name

    # Phase 3: Run main script logic
    clean_script_exit = False
    try:
        initialize_script() # Sets up file logging, uses global log and console
        clean_script_exit = display_main_menu() # display_main_menu returns True if exited cleanly via menu
    except SystemExit:
        # This catches sys.exit() from menu's Exit option or from initialize_script etc.
        log.info("Nova System Setup exited via SystemExit.")
        # Console saving for menu exit is handled in display_main_menu
        clean_script_exit = True # Treat as a "clean" exit for console saving logic
    except Exception as e_main:
        if log: log.exception(f"[bold red]An unhandled critical error occurred in main: {e_main}[/]")
        else: print(f"CRITICAL ERROR (logger not available): {e_main}", file=sys.stderr, flush=True)
        
        if console: # If console was initialized
            console.print_exception(show_locals=True, max_frames=8)
            console.print(Panel(f"A critical error occurred. Please check the logs (if available) at {LOG_FILE_PATH} and the console output above.",
                                title="[bold red]NOVA SETUP FAILED CRITICALLY[/]", border_style="red"))
        sys.exit(1) # Ensure exit code reflects critical failure
    finally:
        final_log_file_path = LOG_FILE_PATH if LOG_FILE_PATH.is_absolute() else SCRIPT_DIR / LOG_FILE_NAME
        console_output_file_path = TARGET_USER_HOME / "nova_setup_console_output.txt" if TARGET_USER_HOME.is_absolute() else SCRIPT_DIR / "nova_setup_console_output.txt"
        
        # Save console output if not already saved by a clean menu exit path
        # (display_main_menu saves if 'Exit' is chosen)
        if console and not clean_script_exit:
            try:
                # If the script is ending for any reason other than a clean menu exit, try to save.
                # Avoid double-saving if display_main_menu already did.
                if not console_output_file_path.exists() or (console_output_file_path.exists() and (Path.cwd() / console_output_file_path).stat().st_mtime < (Path.cwd() / final_log_file_path).stat().st_mtime if final_log_file_path.exists() else True ): # Heuristic to avoid overwrite if menu exit already saved
                    console.save_text(console_output_file_path)
                    if log: log.info(f"Console output saved (main finally) to {console_output_file_path}")
                    else: print(f"INFO: Console output saved to {console_output_file_path}", flush=True)
            except Exception as e_save_final:
                if log: log.error(f"Error saving console output in main finally block: {e_save_final}")
                else: print(f"ERROR: Failed to save console output: {e_save_final}", file=sys.stderr, flush=True)
        
        if log: log.info(f"--- Nova System Setup execution finished. Full log at [link=file://{final_log_file_path}]{final_log_file_path}[/link] ---")
        else: print(f"INFO: Execution finished. Log expected at {final_log_file_path}", flush=True)

if __name__ == "__main__":
    main()