# Fedora-AutoEnv-Setup/scripts/phase4_gnome_configuration.py

import subprocess
import sys
import os
import shutil
import shlex 
import tempfile 
from pathlib import Path
from typing import Optional, Dict, List

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils
from scripts.logger_utils import app_logger 

# --- Constants ---
GEXT_CLI_MODULE = "gnome_extensions_cli.cli" 

# --- Helper Functions ---

def _get_target_user() -> Optional[str]:
    """Determines the target user, typically from SUDO_USER."""
    if os.geteuid() == 0: 
        target_user = os.environ.get("SUDO_USER")
        if not target_user:
            app_logger.error("SUDO_USER env var not set while running as root.")
            con.print_error("SUDO_USER not set. Cannot determine target user for GNOME setup.")
            return None
        try: # Verify user exists
            system_utils.run_command(["id", "-u", target_user], capture_output=True, check=True, print_fn_info=None, logger=app_logger)
        except:
            app_logger.error(f"SUDO_USER '{target_user}' is not a valid system user.")
            con.print_error(f"SUDO_USER '{target_user}' is not a valid system user.")
            return None
        app_logger.info(f"Target user for GNOME configuration: {target_user}")
        return target_user
    else:
        current_user = os.getlogin()
        app_logger.warning(f"Script not root. Assuming current user '{current_user}' for GNOME tasks.")
        con.print_warning(f"Script not root. Assuming current user '{current_user}'. Some operations might need sudo if run standalone.")
        return current_user

def _install_dnf_packages(packages: List[str]) -> bool:
    """Installs specified DNF packages."""
    if not packages: app_logger.info("No DNF packages for Phase 4."); con.print_info("No DNF packages to install."); return True
    app_logger.info(f"Installing DNF packages: {packages}"); con.print_sub_step(f"Installing DNF packages: {', '.join(packages)}")
    try:
        cmd = ["sudo", "dnf", "install", "-y", "--allowerasing"] + packages
        system_utils.run_command(cmd, capture_output=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger)
        con.print_success(f"DNF packages processed: {', '.join(packages)}"); return True
    except Exception: app_logger.error(f"Failed DNF install: {packages}", exc_info=True); return False

def _install_pip_packages(packages: List[str], target_user: str) -> bool:
    """Installs specified pip packages for the target_user (--user)."""
    if not packages: app_logger.info("No pip packages for Phase 4."); con.print_info("No pip packages to install."); return True
    app_logger.info(f"Installing pip packages for {target_user}: {packages}"); con.print_sub_step(f"Installing pip packages for {target_user}: {', '.join(packages)}")
    all_ok = True
    for pkg in packages:
        cmd = f"python3 -m pip install --user --upgrade {shlex.quote(pkg)}"
        try:
            system_utils.run_command(cmd, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error,print_fn_sub_step=con.print_sub_step,logger=app_logger)
            con.print_success(f"Pip package '{pkg}' installed/updated for {target_user}.")
        except Exception: app_logger.error(f"Failed pip install of '{pkg}' for {target_user}", exc_info=True); all_ok = False
    return all_ok

def _verify_gext_is_usable(target_user: str) -> bool:
    """Checks if gnome-extensions-cli can be invoked."""
    app_logger.info(f"Verifying gnome-extensions-cli for {target_user}."); con.print_info(f"Verifying GNOME Extensions CLI for {target_user}...")
    cmd = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} --version"
    try:
        system_utils.run_command(cmd, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, logger=app_logger)
        con.print_success(f"GNOME Extensions CLI is available for {target_user}."); return True
    except Exception: app_logger.error(f"gext verification failed for {target_user}.", exc_info=True); con.print_error(f"gext verification failed."); return False

def _process_ego_extension(ext_key: str, ext_cfg: Dict, target_user: str) -> bool:
    """Installs and enables an EGO extension using gext (D-Bus mode)."""
    uuid = ext_cfg.get("uuid"); numerical_id = ext_cfg.get("numerical_id"); name = ext_cfg.get("name", ext_key)
    if not uuid: app_logger.error(f"No uuid for EGO ext '{name}'."); con.print_error(f"No uuid for EGO ext '{name}'."); return False
    
    install_id = str(numerical_id) if numerical_id else uuid
    app_logger.info(f"Processing EGO ext '{name}' (ID: {install_id}, UUID: {uuid}) for {target_user}.")
    con.print_info(f"Processing EGO extension: {name}...")

    try:
        # Install (may prompt user via GNOME Shell dialog)
        install_cmd = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} install {shlex.quote(install_id)}"
        app_logger.info(f"Executing EGO install: {install_cmd} (as {target_user})")
        system_utils.run_command(install_cmd, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
        app_logger.info(f"EGO ext '{name}' install command sent.")
        con.print_success(f"EGO ext '{name}' install process initiated (check desktop for prompts).")

        # Enable
        enable_cmd = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid)}"
        app_logger.info(f"Executing EGO enable: {enable_cmd} (as {target_user})")
        system_utils.run_command(enable_cmd, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
        app_logger.info(f"EGO ext '{name}' enable command sent.")
        con.print_success(f"EGO ext '{name}' enable process initiated.")
        return True
    except subprocess.CalledProcessError as e:
        stderr_lower = e.stderr.lower() if e.stderr else ""
        if "already installed" in stderr_lower or "already enabled" in stderr_lower:
            app_logger.info(f"EGO ext '{name}' already installed/enabled (reported: {stderr_lower[:100]}).")
            con.print_info(f"EGO ext '{name}' already installed/enabled.")
            return True # Treat as success
        app_logger.error(f"Error processing EGO ext '{name}': {e}", exc_info=False); con.print_error(f"Error EGO ext '{name}'."); return False
    except Exception as e:
        app_logger.error(f"Unexpected error EGO ext '{name}': {e}", exc_info=True); con.print_error(f"Unexpected error EGO ext '{name}'."); return False

def _process_git_extension(ext_key: str, ext_cfg: Dict, target_user: str) -> bool:
    """Installs and enables a Git-based extension."""
    git_url = ext_cfg.get("url"); script_name = ext_cfg.get("install_script"); uuid = ext_cfg.get("uuid_to_enable"); name = ext_cfg.get("name", ext_key)
    if not git_url or not script_name: app_logger.error(f"No url/script for Git ext '{name}'."); con.print_error(f"No url/script Git ext '{name}'."); return False
    app_logger.info(f"Processing Git ext '{name}' from {git_url} for {target_user}."); con.print_info(f"Processing Git extension: {name}...")

    script_cmd = f"./{shlex.quote(script_name)}" if script_name.endswith(".sh") else shlex.quote(script_name)
    repo_name = Path(git_url).name.removesuffix(".git")
    shell_safe_name = shlex.quote(name)
    
    user_script = f"""
        set -e; PRETTY_NAME={shell_safe_name}
        TMP_DIR=$(mktemp -d -t gnome_git_ext_{shlex.quote(ext_key)}_XXXXXX)
        trap 'echo "Cleaning $TMP_DIR for $PRETTY_NAME"; rm -rf "$TMP_DIR"' EXIT
        git clone --depth=1 {shlex.quote(git_url)} "$TMP_DIR/{shlex.quote(repo_name)}"
        cd "$TMP_DIR/{shlex.quote(repo_name)}"
        if [ -f "{script_name}" ] && [[ "{script_name}" == *.sh ]]; then chmod +x "{script_name}"; fi
        dbus-run-session -- {script_cmd}
        echo "Install script for $PRETTY_NAME done."
    """
    try:
        system_utils.run_command(user_script, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger)
        con.print_success(f"Git ext '{name}' install script executed.")
        if uuid:
            enable_cmd = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid)}"
            app_logger.info(f"Executing Git ext enable: {enable_cmd} (as {target_user})")
            system_utils.run_command(enable_cmd, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
            con.print_success(f"Git ext '{name}' (UUID: {uuid}) enable command executed.")
        return True
    except Exception as e: app_logger.error(f"Error Git ext '{name}': {e}", exc_info=True); con.print_error(f"Error Git ext '{name}'."); return False

def _apply_dark_mode(target_user: str) -> bool:
    """Applies dark mode preference using gsettings."""
    app_logger.info(f"Setting dark mode for {target_user}."); con.print_sub_step(f"Setting dark mode for {target_user}...")
    schema = "org.gnome.desktop.interface"; key = "color-scheme"; value = "prefer-dark"
    cmd = ["dbus-run-session", "--", "gsettings", "set", schema, key, value]
    try:
        system_utils.run_command(cmd, run_as_user=target_user, shell=False, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
        con.print_success(f"Dark mode preference set for {target_user}.")
        # Attempt to set Adwaita-dark GTK theme as a best effort
        gtk_key = "gtk-theme"; gtk_value = "Adwaita-dark"
        cmd_gtk = ["dbus-run-session", "--", "gsettings", "set", schema, gtk_key, gtk_value]
        system_utils.run_command(cmd_gtk, run_as_user=target_user, shell=False, capture_output=True, check=False, print_fn_info=None, logger=app_logger) # check=False
        app_logger.info(f"Attempted to set {gtk_key} to {gtk_value}.")
        return True
    except Exception: app_logger.error(f"Failed to set dark mode for {target_user}.", exc_info=True); con.print_error(f"Failed to set dark mode."); return False

# --- Main Phase Function ---
def run_phase4(app_config: dict) -> bool:
    app_logger.info("Starting Phase 4: GNOME Configuration & Extensions.")
    con.print_step("PHASE 4: GNOME Configuration & Extensions")
    overall_success = True
    
    cfg = config_loader.get_phase_data(app_config, "phase4_gnome_configuration")
    if not cfg: app_logger.warning("No config Ph4. Skip."); con.print_warning("No config Ph4. Skip."); return True 

    target_user = _get_target_user()
    if not target_user: return False 
    
    app_logger.info(f"Run GNOME configs for: {target_user}"); con.print_info(f"Run GNOME configs for: [bold cyan]{target_user}[/bold cyan]")

    # 1. Install Management Tools (DNF, Pip, Flatpak)
    con.print_info("\nStep 1: Installing GNOME management tools (DNF, Pip, Flatpak)...")
    if not _install_dnf_packages(cfg.get("dnf_packages", [])): overall_success = False
    if not _install_pip_packages(cfg.get("pip_packages", []), target_user): overall_success = False
    if cfg.get("flatpak_apps"):
        if not system_utils.install_flatpak_apps(apps_to_install=cfg.get("flatpak_apps",{}), system_wide=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger):
            overall_success = False; app_logger.error("Ph4 Flatpak tool install issues.")
    else: app_logger.info("No Flatpak management tools for Ph4."); con.print_info("No Flatpak management tools for Ph4.")

    # 2. Verify gext CLI
    gext_ok = False
    if cfg.get("gnome_extensions"):
        con.print_info("\nStep 2: Verifying GNOME Extensions CLI tool...")
        gext_ok = _verify_gext_is_usable(target_user)
        if not gext_ok: overall_success = False; app_logger.error("gext not usable. Extensions will be skipped.")
    else: gext_ok = True # Not needed if no extensions are configured

    # 3. Install GNOME Extensions
    if gext_ok and cfg.get("gnome_extensions"):
        extensions_cfg = cfg.get("gnome_extensions", {})
        if extensions_cfg:
            con.print_info("\nStep 3: Installing GNOME Shell Extensions...")
            con.print_panel(
                "[bold yellow]Attention:[/]\n"
                "This script will now attempt to install GNOME Shell extensions.\n"
                "Your desktop may display dialogs asking for permission for each installation.\n"
                "[bold]Please monitor your desktop and approve these prompts.[/]",
                title="Interactive Extension Installation", style="yellow"
            )
            if not con.confirm_action("Ready to proceed with interactive extension installation?", default=True):
                app_logger.info("User skipped interactive extension installation."); con.print_info("Extension installation skipped.")
            else:
                all_ext_ok = True
                for ext_key, ext_val in extensions_cfg.items():
                    ext_type = ext_val.get("type")
                    if ext_type == "ego":
                        if not _process_ego_extension(ext_key, ext_val, target_user): all_ext_ok = False
                    elif ext_type == "git":
                        if not _process_git_extension(ext_key, ext_val, target_user): all_ext_ok = False
                    else: app_logger.warning(f"Unknown ext type '{ext_type}' for '{ext_key}'."); con.print_warning(f"Unknown ext type '{ext_type}'."); all_ext_ok = False
                if not all_ext_ok: overall_success = False; con.print_warning("Some extensions failed.")
                else: con.print_success("All extensions processed.")
        else: app_logger.info("No extensions listed in YAML."); con.print_info("No extensions to install.")
    elif not gext_ok and cfg.get("gnome_extensions"):
        con.print_warning("Skipped extension installation as GNOME Extensions CLI was not usable.")
        
    # 4. Set Dark Mode
    con.print_info("\nStep 4: Setting Dark Mode...")
    if not _apply_dark_mode(target_user):
        app_logger.warning(f"Failed to set dark mode for {target_user}."); # Non-critical for overall_success
        con.print_warning(f"Failed to set dark mode for {target_user}.")

    # Final summary
    if overall_success:
        app_logger.info("Phase 4 completed successfully."); con.print_success("Phase 4: GNOME Configuration & Extensions completed successfully.")
        if cfg.get("gnome_extensions") or True: # If any visual changes were attempted
             con.print_warning("IMPORTANT: A logout/login or GNOME Shell restart (Alt+F2, 'r', Enter) "
                              "is likely required for all theme and extension changes to take full effect.")
    else:
        app_logger.error("Phase 4 completed with errors."); con.print_error("Phase 4: GNOME Configuration & Extensions completed with errors. Review logs.")
    return overall_success