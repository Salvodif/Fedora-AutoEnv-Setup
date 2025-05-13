#!/usr/bin/env python3

import os
import shlex
import shutil
import subprocess
import sys
import pwd # To get user's home directory by name
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Callable

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
    "zsh",
    "git", "curl", "stow", "dnf-plugins-core", "cargo",
    "powerline-fonts", "btop", "bat", "fzf",
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

# --- Utility Functions (run_command, check_command_exists - unchanged from previous version) ---
def run_command(command: List[str] | str, # Allow str for shell=True commands
                check: bool = True,
                capture_output: bool = False,
                text: bool = True,
                as_user: Optional[str] = None,
                shell: bool = False,
                cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Runs a command, optionally as a different user."""
    cmd_for_log = command if isinstance(command, str) else ' '.join(shlex.quote(str(s)) for s in command)
    log.debug(f"Executing: {cmd_for_log}{f' as {as_user}' if as_user else ''}{f' in {cwd}' if cwd else ''}")

    final_command_parts: List[str] = []
    actual_command_to_run: List[str] | str

    if as_user:
        final_command_parts.extend(["sudo", "-u", as_user])
        if shell: # Command is a string to be passed to user's shell
            final_command_parts.extend(["sh", "-c", command if isinstance(command, str) else " ".join(command)])
            actual_command_to_run = final_command_parts # sudo will execute sh -c "..."
        else: # Command is a list of args
            final_command_parts.extend(command if isinstance(command, list) else [command])
            actual_command_to_run = final_command_parts
    else: # Running as root
        if shell:
            actual_command_to_run = command if isinstance(command, str) else " ".join(command)
        else:
            actual_command_to_run = command if isinstance(command, list) else [command]

    try:
        result = subprocess.run(
            actual_command_to_run,
            check=check,
            capture_output=capture_output,
            text=text,
            shell=shell if not as_user else False, # Let `sh -c` handle the shell if running as_user
            cwd=cwd
        )
        return result
    except subprocess.CalledProcessError as e:
        cmd_str_err = ' '.join(e.cmd) if isinstance(e.cmd, list) else e.cmd
        log.error(f"Command '[bold cyan]{cmd_str_err}[/]' failed with exit code {e.returncode}")
        if e.stdout: log.error(f"[stdout]: {e.stdout.strip()}")
        if e.stderr: log.error(f"[stderr]: {e.stderr.strip()}")
        raise
    except FileNotFoundError:
        cmd_failed = final_command_parts[0] if final_command_parts and isinstance(final_command_parts, list) else str(actual_command_to_run)
        log.error(f"Command not found: {cmd_failed.split()[0]}")
        raise

def check_command_exists(command_name_parts: List[str] | str, as_user: Optional[str] = None) -> bool:
    """Checks if a command exists, optionally for a specific user."""
    try:
        # 'command -v' is generally reliable for checking existence
        # If command_name_parts is a list, use the first element as the command to check
        cmd_to_verify = command_name_parts[0] if isinstance(command_name_parts, list) else command_name_parts.split()[0]

        check_cmd_str = f"command -v {shlex.quote(cmd_to_verify)}"
        run_command(check_cmd_str, as_user=as_user, shell=True, capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

# --- Initialization (unchanged) ---
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

    if not ZSHRC_SOURCE_PATH.is_file():
        log.critical(
            f"[bold red]Source file '{ZSHRC_SOURCE_FILE_NAME}' not found in expected path: "
            f"'{ZSHRC_SOURCE_PATH}'. Please ensure it exists and is readable.[/]"
        )
        sys.exit(1)
    if not NANORC_SOURCE_PATH.is_file():
        log.critical(
            f"[bold red]Source file '{NANORC_SOURCE_FILE_NAME}' not found in expected path: "
            f"'{NANORC_SOURCE_PATH}'. Please ensure it exists and is readable.[/]"
        )
        sys.exit(1)
    log.info("Source configuration files found in their respective subdirectories and are readable.")

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
                with console.status("[bold green]Updating and upgrading system (dnf)...[/]", spinner="dots"):
                    try:
                        run_command(["dnf", "update", "-y"])
                        run_command(["dnf", "upgrade", "-y"])
                    except subprocess.CalledProcessError:
                        log.error("[bold red]Failed to update/upgrade system via DNF. Please check DNF logs.[/]")
                log.info(":white_check_mark: System update and upgrade complete.")
            else:
                log.warning(f"This script is optimized for Fedora. You are running: [yellow]{pretty_name}[/]")
                log.info("Please ensure your system is up-to-date using your distribution's package manager.")
                if not Confirm.ask("Do you want to continue with the script anyway?", default=False, console=console):
                    log.info("Exiting script as per user request.")
                    sys.exit(0)
                log.warning("Proceeding on a non-Fedora system. DNF-specific installations will be skipped.")
        except Exception as e:
            log.error(f"Could not parse /etc/os-release: {e}")
    else:
        log.warning("Could not determine OS from /etc/os-release.")
        if not Confirm.ask("Do you want to continue assuming a non-Fedora system?", default=False, console=console):
            sys.exit(0)

def install_dnf_packages(packages_list: List[str]):
    if IS_FEDORA:
        if not packages_list:
            log.info("No DNF packages specified for installation.")
            return
        log.info(f"Installing DNF packages: [cyan]{', '.join(packages_list)}[/]...")
        with console.status("[bold green]Running dnf install...[/]", spinner="earth"):
            try:
                run_command(["dnf", "install", "-y"] + packages_list)
            except subprocess.CalledProcessError:
                log.error("[bold red]Failed to install one or more DNF packages. Please check DNF logs.[/]")
        log.info(":package: DNF packages installation attempt complete.")
    else:
        log.warning("Skipping DNF package installation (not Fedora).")
        if packages_list:
            log.info(f"Please ensure equivalents of these are installed: {', '.join(packages_list)}")

# --- Tool Installation Functions (install_oh_my_zsh, etc. - unchanged) ---
def check_critical_deps(): # (Unchanged from previous)
    log.info("Checking for critical dependencies (git, curl)...")
    missing_deps = []
    for dep in ["git", "curl"]:
        if not shutil.which(dep): # shutil.which checks current PATH (root's PATH)
            if IS_FEDORA:
                log.warning(f"Critical dependency '{dep}' not found, but will be installed as this is Fedora.")
            else:
                log.error(f"Critical dependency '[bold red]{dep}[/]' not found.")
                missing_deps.append(dep)
        else:
            log.info(f":heavy_check_mark: Dependency '{dep}' is available.")
    
    if missing_deps and not IS_FEDORA:
        log.critical(f"Please install missing dependencies ({', '.join(missing_deps)}) and re-run.")
        sys.exit(1)

def install_oh_my_zsh(): # (Unchanged)
    omz_dir = TARGET_USER_HOME / ".oh-my-zsh"
    if omz_dir.is_dir():
        log.warning(f"Oh My Zsh already installed in [cyan]{omz_dir}[/]. Skipping.")
    else:
        log.info("Installing Oh My Zsh...")
        cmd = "curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh | sh -s -- --unattended --keep-zshrc"
        with console.status("[bold green]Installing Oh My Zsh...[/]", spinner="monkey"):
            try:
                run_command(cmd, as_user=TARGET_USER, shell=True, check=True)
                log.info(":rocket: Oh My Zsh installed.")
            except subprocess.CalledProcessError:
                log.error("[bold red]Oh My Zsh installation failed.[/]")

def install_omz_plugins(): # (Unchanged)
    log.info("Installing Oh My Zsh plugins...")
    zsh_custom_plugins = TARGET_USER_HOME / ".oh-my-zsh" / "custom" / "plugins"
    run_command(["mkdir", "-p", str(zsh_custom_plugins)], as_user=TARGET_USER)

    for plugin in OMZ_PLUGINS:
        plugin_name = plugin["name"]
        plugin_url = plugin["url"]
        target_dir = zsh_custom_plugins / plugin_name
        if target_dir.is_dir():
            log.warning(f"OMZ Plugin '[cyan]{plugin_name}[/]' already present. Skipping.")
        else:
            log.info(f"Cloning OMZ plugin '[cyan]{plugin_name}[/]'...")
            with console.status(f"[bold green]Cloning {plugin_name}...[/]", spinner="dots"):
                try:
                    run_command(["git", "clone", "--depth", "1", plugin_url, str(target_dir)], as_user=TARGET_USER)
                    log.info(f":heavy_check_mark: OMZ Plugin '[cyan]{plugin_name}[/]' installed.")
                except subprocess.CalledProcessError:
                    log.error(f"[bold red]Failed to clone OMZ plugin '{plugin_name}'.[/]")

def install_cargo_tools(): # (Unchanged)
    log.info(f"Installing Cargo tools: [cyan]{', '.join(CARGO_TOOLS)}[/]...")
    cargo_path_user = TARGET_USER_HOME / ".cargo" / "bin" / "cargo"
    effective_cargo_cmd = ""

    if check_command_exists(str(cargo_path_user), as_user=TARGET_USER):
         effective_cargo_cmd = str(cargo_path_user)
    elif shutil.which("cargo"):
        effective_cargo_cmd = "cargo"
    
    if not effective_cargo_cmd:
        log.warning("[bold yellow]Cargo command not found.[/] Skipping installation of Cargo tools.")
        return

    log.info(f"Using cargo: [blue]{effective_cargo_cmd}[/]")
    for tool in CARGO_TOOLS:
        log.info(f"Attempting to install '[cyan]{tool}[/]' with cargo...")
        try:
            list_result = run_command([effective_cargo_cmd, "install", "--list"], 
                                      as_user=TARGET_USER, capture_output=True, text=True, check=False)
            if list_result.returncode == 0 and f"{tool} v" in list_result.stdout:
                log.warning(f"Cargo tool '[cyan]{tool}[/]' seems to be already installed. Skipping.")
                continue
        except Exception as e:
            log.debug(f"Could not check if cargo tool '{tool}' is installed: {e}")

        with console.status(f"[bold green]Installing {tool} with cargo...[/]", spinner="bouncingBar"):
            try:
                run_command([effective_cargo_cmd, "install", tool], as_user=TARGET_USER)
                log.info(f":crates: Cargo tool '[cyan]{tool}[/]' installed.")
            except subprocess.CalledProcessError:
                log.error(f"[bold red]Failed to install Cargo tool '{tool}'.[/]")

def install_scripted_tools(): # (Unchanged)
    for tool_info in SCRIPTED_TOOLS:
        name = tool_info["name"]
        check_cmd_str_parts = shlex.split(tool_info["check_command"]) # Now a list
        url = tool_info["url"]
        method = tool_info["method"]

        log.info(f"Installing '[cyan]{name}[/]'...")
        if check_command_exists(check_cmd_str_parts, as_user=TARGET_USER):
            try:
                run_command(check_cmd_str_parts, as_user=TARGET_USER, capture_output=True, check=True)
                log.warning(f"'[cyan]{name}[/]' seems to be already installed (version check successful). Skipping.")
                continue
            except subprocess.CalledProcessError:
                log.debug(f"'{name}' command found, but version check failed. Proceeding with install/update.")
        
        log.info(f"Downloading and executing install script for '[cyan]{name}[/]'...")
        install_cmd_str = f"curl -fsSL {url} | {method}"
        with console.status(f"[bold green]Installing {name}...[/]", spinner="arrow3"):
            try:
                run_command(install_cmd_str, as_user=TARGET_USER, shell=True, check=True)
                if check_command_exists(check_cmd_str_parts, as_user=TARGET_USER):
                    log.info(f":white_check_mark: '[cyan]{name}[/]' installed successfully.")
                else:
                    log.error(f"[bold red]Installation of '[cyan]{name}[/]' might have failed (command not found after install).[/]")
            except subprocess.CalledProcessError:
                log.error(f"[bold red]Installation of '{name}' failed via script.[/]")

# --- Configuration File Management (copy_config_files - unchanged) ---
def copy_config_files(): # (Unchanged)
    log.info("Copying configuration files...")
    target_zshrc = TARGET_USER_HOME / ".zshrc"
    if ZSHRC_SOURCE_PATH.is_file():
        log.info(f"Copying [magenta]{ZSHRC_SOURCE_FILE_NAME}[/] to [cyan]{target_zshrc}[/]")
        if target_zshrc.exists():
            backup_zshrc = TARGET_USER_HOME / f".zshrc.backup.{os.urandom(4).hex()}"
            log.warning(f"Backing up existing .zshrc to [cyan]{backup_zshrc}[/]")
            try: run_command(["cp", str(target_zshrc), str(backup_zshrc)], as_user=TARGET_USER)
            except Exception: shutil.copy(target_zshrc, backup_zshrc)
        shutil.copy(ZSHRC_SOURCE_PATH, target_zshrc)
        os.chown(target_zshrc, pwd.getpwnam(TARGET_USER).pw_uid, pwd.getpwnam(TARGET_USER).pw_gid)
        log.info(f":floppy_disk: [magenta]{ZSHRC_SOURCE_FILE_NAME}[/] copied.")
    else:
        log.error(f"[bold red]Source file {ZSHRC_SOURCE_FILE_NAME} not found. Skipping .zshrc copy.[/]")

    nanorc_user_target_dir = TARGET_USER_HOME / ".nano"
    nanorc_user_target_file = nanorc_user_target_dir / "nanorc"
    if NANORC_SOURCE_PATH.is_file():
        run_command(["mkdir", "-p", str(nanorc_user_target_dir)], as_user=TARGET_USER)
        log.info(f"Copying [magenta]{NANORC_SOURCE_FILE_NAME}[/] to [cyan]{nanorc_user_target_file}[/]")
        if nanorc_user_target_file.exists():
            backup_nanorc = nanorc_user_target_dir / f"nanorc.backup.{os.urandom(4).hex()}"
            log.warning(f"Backing up existing nanorc to [cyan]{backup_nanorc}[/]")
            try: run_command(["cp", str(nanorc_user_target_file), str(backup_nanorc)], as_user=TARGET_USER)
            except Exception: shutil.copy(nanorc_user_target_file, backup_nanorc)
        shutil.copy(NANORC_SOURCE_PATH, nanorc_user_target_file)
        os.chown(nanorc_user_target_file, pwd.getpwnam(TARGET_USER).pw_uid, pwd.getpwnam(TARGET_USER).pw_gid)
        if not nanorc_user_target_dir.owner() == TARGET_USER: # Rough check
             os.chown(nanorc_user_target_dir, pwd.getpwnam(TARGET_USER).pw_uid, pwd.getpwnam(TARGET_USER).pw_gid)
        log.info(f":floppy_disk: [magenta]{NANORC_SOURCE_FILE_NAME}[/] copied to .nano directory.")
    else:
        log.error(f"[bold red]Source file {NANORC_SOURCE_FILE_NAME} not found. Skipping nanorc copy.[/]")

# --- Post-Installation Verification (perform_post_install_checks - unchanged) ---
def perform_post_install_checks(): # (Unchanged)
    log.info("Performing post-installation checks...")
    tools_to_check = ["zsh", "git", "curl", "eza", "dust", "btop", "bat", "fzf", "zoxide", "atuin", "nano"]
    all_passed = True
    report_lines = []

    for tool in tools_to_check:
        # Attempt to find the tool command, prioritizing user's local paths
        tool_cmd_str = tool # Command to actually run for version check
        found_path = None
        
        # Check typical user install paths first
        for user_path_prefix in [TARGET_USER_HOME / ".local" / "bin", TARGET_USER_HOME / ".cargo" / "bin"]:
            if (user_path_prefix / tool).is_file():
                found_path = str(user_path_prefix / tool)
                tool_cmd_str = found_path # Use absolute path if found in specific location
                break
        
        if not found_path: # If not in user paths, check system PATH
            sys_path_tool = shutil.which(tool)
            if sys_path_tool:
                found_path = sys_path_tool
                tool_cmd_str = found_path

        if found_path:
            version_output = " (version N/A)"
            try:
                run_as = TARGET_USER if TARGET_USER_HOME.as_posix() in found_path else None
                for v_flag in ["--version", "-V"]:
                    try:
                        result = run_command([tool_cmd_str, v_flag], capture_output=True, text=True, check=False, as_user=run_as)
                        if result.returncode == 0:
                            version_output = f" ([italic]{result.stdout.strip().splitlines()[0]}[/])"
                            break
                    except Exception: pass
                report_lines.append(f":heavy_check_mark: [green]Tool '[cyan]{tool}[/]' is available[/]{version_output}")
            except Exception as e:
                report_lines.append(f":heavy_check_mark: [green]Tool '[cyan]{tool}[/]' is available[/] (version check failed: {e})")
        else:
            is_expected = (tool in DNF_PACKAGES and IS_FEDORA) or \
                          (tool in CARGO_TOOLS) or \
                          any(t['name'] == tool for t in SCRIPTED_TOOLS) or \
                          (tool in ["zsh", "git", "curl", "nano"])
            if is_expected:
                report_lines.append(f":x: [bold red]Tool '[cyan]{tool}[/]' FAILED to be found.[/]")
                all_passed = False
            else:
                report_lines.append(f":warning: [yellow]Tool '[cyan]{tool}[/]' not found (may be expected).[/]")
    
    console.print(Panel("\n".join(report_lines), title="[bold]Post-Installation Check Summary[/]", expand=False, border_style="blue"))
    if all_passed: log.info("[bold green]All critical post-installation checks seem to have passed.[/]")
    else: log.warning("[bold yellow]Some post-installation checks failed. Review summary and logs.[/]")


# --- Main Setup Functions ---
def perform_initial_setup():
    """Orchestrates the Zsh, tools, and dotfiles setup."""
    console.rule("[bold sky_blue2]Starting Initial Environment Setup[/]", style="sky_blue2")
    
    console.rule("[bold cyan]System Check & Update[/]", style="cyan")
    perform_system_update_check()
    
    console.rule("[bold cyan]Critical Dependencies[/]", style="cyan")
    check_critical_deps()
    
    console.rule("[bold cyan]Package Installation (DNF)[/]", style="cyan")
    install_dnf_packages(DNF_PACKAGES) # Pass the main DNF package list
    
    console.rule("[bold cyan]Oh My Zsh & Plugins[/]", style="cyan")
    install_oh_my_zsh()
    install_omz_plugins()
    
    console.rule("[bold cyan]Cargo Tools[/]", style="cyan")
    install_cargo_tools()
    
    console.rule("[bold cyan]Additional Scripted Tools[/]", style="cyan")
    install_scripted_tools()
    
    console.rule("[bold cyan]Configuration Files[/]", style="cyan")
    copy_config_files()
    
    console.rule("[bold cyan]Post-Installation Verification[/]", style="cyan")
    perform_post_install_checks()

    console.print(Panel(Text("Initial Setup Process Completed!", style="bold green"), expand=False))

def manage_gnome_extensions():
    """Manages GNOME Shell extensions."""
    console.rule("[bold magenta]GNOME Shell Extension Management[/]", style="magenta")
    
    if not IS_FEDORA: # Or more broadly, if not on a GNOME system
        log.warning("GNOME extension management is typically for GNOME desktops (like on Fedora).")
        if not Confirm.ask("Attempt to proceed anyway?", default=False):
            return

    # Ensure necessary tools are installed (gnome-extensions-app, gnome-shell-extension-manager)
    # These are already in DNF_PACKAGES if initial setup ran, but good to check or install separately.
    gnome_tools = ["gnome-extensions-app", "gnome-shell-extension-manager"]
    missing_gnome_tools = [tool for tool in gnome_tools if not shutil.which(tool)]
    
    if missing_gnome_tools and IS_FEDORA:
        log.info(f"Installing required GNOME tools: {', '.join(missing_gnome_tools)}")
        install_dnf_packages(missing_gnome_tools) # Install only these if missing
    elif missing_gnome_tools and not IS_FEDORA:
        log.error(f"Missing GNOME tools: {', '.join(missing_gnome_tools)}. Please install them manually.")
        return

    log.info("GNOME Extension Management (Placeholder)")
    console.print("This section is for installing/managing GNOME Shell extensions.")
    console.print("Available tools:")
    console.print("- `gnome-extensions-app` (GUI for managing installed extensions)")
    console.print("- `extension-manager` (aka gnome-shell-extension-manager, another GUI)")
    console.print("- `gsettings` (command-line to enable/disable/configure extensions)")
    console.print("- `gnome-extensions` command (part of gnome-shell, e.g., `gnome-extensions list`)")

    # Example: List currently enabled extensions (run as target user)
    try:
        log.info("Listing enabled GNOME extensions (requires active GNOME session for user):")
        run_command(["gnome-extensions", "list", "--enabled"], as_user=TARGET_USER, capture_output=True)
        # The output will be in the log if capture_output=True and not printed directly
        # For direct print:
        # result = run_command(...)
        # console.print(result.stdout)
    except Exception as e:
        log.warning(f"Could not list GNOME extensions (maybe no active session for {TARGET_USER}?): {e}")

    # Placeholder for actual extension installation logic
    # This usually involves:
    # 1. Finding the UUID of the extension (e.g., from extensions.gnome.org)
    # 2. Installing it:
    #    - Manually: download zip, extract to ~/.local/share/gnome-shell/extensions/<uuid>
    #    - Using a tool like `gnome-shell-extension-installer` (AUR script, or its Python logic)
    #    - Some extensions might have their own install scripts or DNF packages.
    # 3. Enabling it: `gnome-extensions enable <uuid>` (as the user)
    # 4. (Optional) Configuring it with `gsettings`

    console.print(Panel(Text("GNOME Extension Management - To Be Implemented", style="bold yellow"), expand=False))
    log.info("Further implementation needed for specific GNOME extension installations.")
    # Example:
    # EXTENSION_UUID = "user-theme@gnome-shell-extensions.gcampax.github.com"
    # log.info(f"Attempting to enable extension: {EXTENSION_UUID}")
    # try:
    #     run_command(["gnome-extensions", "enable", EXTENSION_UUID], as_user=TARGET_USER)
    #     log.info(f"Extension {EXTENSION_UUID} enabled (if installed and compatible).")
    # except subprocess.CalledProcessError:
    #     log.error(f"Failed to enable {EXTENSION_UUID}. Ensure it's installed.")

# --- Main Application Logic ---
def display_main_menu():
    """Displays the main menu and handles user choice."""
    console.print(Panel(Text("Enhanced System Setup Utility", justify="center", style="bold white on dark_blue"), expand=False))
    
    menu_options: Dict[str, Tuple[str, Callable[[], None]]] = {
        "1": ("Perform Initial Environment Setup", perform_initial_setup),
        "2": ("Manage GNOME Shell Extensions", manage_gnome_extensions),
        "3": ("Exit", lambda: sys.exit(0))
    }

    while True:
        console.rule("[bold gold1]Main Menu[/]", style="gold1")
        table = Table(show_header=False, box=None, padding=(0,1))
        table.add_column(style="cyan", justify="right")
        table.add_column()
        for key, (description, _) in menu_options.items():
            table.add_row(f"[{key}]", description)
        console.print(Padding(table, (1,2)))

        choice = Prompt.ask("Enter your choice", choices=list(menu_options.keys()), show_choices=False, console=console)
        
        if choice in menu_options:
            description, action_func = menu_options[choice]
            log.info(f"User selected: ({choice}) {description}")
            if action_func:
                try:
                    action_func() # Execute the chosen function
                except SystemExit: # Allow sys.exit() to work for the Exit option
                    raise
                except Exception as e:
                    log.exception(f"Error during '{description}': {e}")
                    console.print_exception(show_locals=True)
                    console.print(Panel(f"An error occurred in '{description}'. Check logs.", title="[bold red]Action Failed[/]", border_style="red"))
            if choice == "3": # Exit
                break 
        else:
            console.print("[prompt.invalid]Invalid choice, please try again.")
        
        if not Confirm.ask("\nReturn to main menu?", default=True, console=console):
            break

def main():
    try:
        initialize_script() # Basic script init (sudo check, user detection)
        display_main_menu() # Show menu and handle actions
    except SystemExit:
        log.info("Script exited by user or explicit sys.exit().")
    except Exception as e:
        log.exception(f"[bold red]An unhandled critical error occurred in main: {e}[/]")
        console.print_exception(show_locals=True)
        console.print(Panel(f"A critical error occurred. Please check the logs at {LOG_FILE_PATH} and the console output above.",
                            title="[bold red]SCRIPT FAILED CRITICALLY[/]", border_style="red"))
        sys.exit(1)
    finally:
        final_log_path = LOG_FILE_PATH if LOG_FILE_PATH.name != "." else SCRIPT_DIR / LOG_FILE_NAME
        console.save_text(TARGET_USER_HOME / "setup_script_console_output.txt" if TARGET_USER_HOME.name != "." else SCRIPT_DIR / "setup_script_console_output.txt" )
        log.info(f"Main script execution finished. Console output saved. Full log at [link=file://{final_log_path}]{final_log_path}[/link]")

if __name__ == "__main__":
    main()
