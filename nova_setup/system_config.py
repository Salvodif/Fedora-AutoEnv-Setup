import os
import sys
import pwd
import shutil
import configparser
from pathlib import Path

from . import shared_state
from . import utils as command_utils

def initialize_script_base_paths():
    """Sets SCRIPT_DIR and derived source paths in shared_state."""
    # SCRIPT_DIR is the directory of the main install.py, which is one level up from this module's dir
    shared_state.SCRIPT_DIR = Path(__file__).parent.parent.resolve()
    shared_state.LOG_FILE_PATH = shared_state.SCRIPT_DIR / shared_state.LOG_FILE_NAME
    
    shared_state.ZSHRC_SOURCE_PATH = shared_state.SCRIPT_DIR / shared_state.ZSHRC_SUBDIRECTORY / shared_state.ZSHRC_SOURCE_FILE_NAME
    shared_state.NANORC_SOURCE_PATH = shared_state.SCRIPT_DIR / shared_state.NANORC_SUBDIRECTORY / shared_state.NANORC_SOURCE_FILE_NAME


def _setup_google_chrome_repo():
    if not shared_state.IS_FEDORA: return
    shared_state.log.info("Setting up Google Chrome repository...")
    repo_file_path = Path("/etc/yum.repos.d/google-chrome.repo")
    if repo_file_path.exists():
        shared_state.log.info("Google Chrome repository file already exists. Skipping setup.")
        return
    
    repo_content = """[google-chrome]
name=google-chrome
baseurl=http://dl.google.com/linux/chrome/rpm/stable/$basearch
enabled=1
gpgcheck=1
gpgkey=https://dl.google.com/linux/linux_signing_key.pub
"""
    try:
        with open(repo_file_path, "w", encoding="utf-8") as f:
            f.write(repo_content)
        shared_state.log.info(f"Google Chrome repository configured at {repo_file_path}")
        command_utils.run_command(["rpm", "--import", "https://dl.google.com/linux/linux_signing_key.pub"])
        shared_state.log.info("Google GPG key imported.")
    except Exception as e:
        shared_state.log.error(f"Failed to set up Google Chrome repository: {e}")

def perform_system_update_check():
    shared_state.log.info("Checking OS...")
    os_release_path = Path("/etc/os-release")
    if not os_release_path.is_file():
        shared_state.log.warning("No /etc/os-release. Assuming non-Fedora."); return
    
    Console, Panel, Text, Confirm, _, _, _, _, _ = shared_state.get_rich_components()

    try:
        content = os_release_path.read_text()
        os_vars = dict(l.split('=', 1) for l in content.splitlines() if '=' in l)
        os_id = os_vars.get('ID','').strip('"')
        os_id_like = os_vars.get('ID_LIKE','').strip('"')
        pretty_name = os_vars.get('PRETTY_NAME', 'Unknown OS').strip('"')

        if os_id == "fedora" or "fedora" in os_id_like.split():
            shared_state.IS_FEDORA = True
            shared_state.log.info(f":package: Fedora detected ([italic green]{pretty_name}[/]). Pre-configuring DNF & Repos...")
            
            dnf_conf_file = Path("/etc/dnf/dnf.conf")
            dnf_parser = configparser.ConfigParser(allow_no_value=True, comment_prefixes=('#',';'), inline_comment_prefixes=('#',';'), strict=False)
            dnf_parser.optionxform = str
            needs_write = False
            if dnf_conf_file.is_file(): 
                try: dnf_parser.read(dnf_conf_file, encoding='utf-8')
                except Exception as e: shared_state.log.warning(f"Parse error {dnf_conf_file}: {e}")
            if not dnf_parser.has_section('main'): dnf_parser.add_section('main'); needs_write=True
            for k,v in {"max_parallel_downloads": "10", "fastestmirror": "true"}.items():
                if dnf_parser.get('main', k, fallback=None) != v: dnf_parser.set('main', k, v); needs_write=True
            if needs_write:
                if dnf_conf_file.is_file(): shutil.copy2(dnf_conf_file, dnf_conf_file.with_suffix(f"{dnf_conf_file.suffix}.bkp_nova_{os.urandom(4).hex()}"))
                with open(dnf_conf_file, 'w', encoding='utf-8') as cf: dnf_parser.write(cf, space_around_delimiters=False)
                shared_state.log.info(f"Updated DNF config: {dnf_conf_file}")
            else: shared_state.log.info(f"DNF settings in {dnf_conf_file} already good.")
            
            try: command_utils.run_command(["dnf", "install", "-y", "fedora-workstation-repositories"]); shared_state.log.info("Fedora third-party repos package checked/installed.")
            except Exception as e: shared_state.log.error(f"Failed `fedora-workstation-repositories` install: {e}")
            
            try:
                ver = command_utils.run_command("rpm -E %fedora", shell=True, capture_output=True, text=True, check=True).stdout.strip()
                if not ver.isdigit(): raise ValueError(f"Bad Fedora version: {ver}")
                for rt in ["free", "nonfree"]: command_utils.run_command(["dnf", "install", "-y", f"https://download1.rpmfusion.org/{rt}/fedora/rpmfusion-{rt}-release-{ver}.noarch.rpm"])
                shared_state.log.info("RPM Fusion repos setup.")
            except Exception as e: shared_state.log.error(f"RPM Fusion setup failed: {e}")

            _setup_google_chrome_repo()

            with shared_state.console.status("[bold green]Updating/upgrading system (dnf)...[/]", spinner="dots"):
                try: command_utils.run_command(["dnf", "update", "-y"]); command_utils.run_command(["dnf", "upgrade", "-y"])
                except Exception: shared_state.log.error("[bold red]DNF update/upgrade failed or timed out.")
            shared_state.log.info(":white_check_mark: System update/upgrade attempt complete.")
        else:
            shared_state.log.warning(f"OS: [yellow]{pretty_name}[/]. Optimized for Fedora.")
            if not Confirm.ask("Continue anyway?", default=False, console=shared_state.console): sys.exit(0)
    except Exception as e:
        shared_state.log.error(f"OS check error: {e}")
        if shared_state.console: shared_state.console.print_exception(max_frames=3)

def check_critical_deps():
    shared_state.log.info("Checking critical deps (git, curl)...")
    missing = [d for d in ["git", "curl"] if not shutil.which(d)]
    if missing:
        if shared_state.IS_FEDORA: shared_state.log.warning(f"Missing: {', '.join(missing)}. Will be DNF installed.")
        else: shared_state.log.critical(f"Missing: {', '.join(missing)}. Install and re-run."); sys.exit(1)
    else: shared_state.log.info(":heavy_check_mark: Critical deps available.")