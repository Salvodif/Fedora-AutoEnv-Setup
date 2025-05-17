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
# _get_target_user, _get_user_home, _install_dnf_packages_ph4, 
# _install_pip_packages_ph4, _verify_gext_cli_usability are kept as the last complete version.
# I will paste them at the end for completeness of this file response.

def _get_target_user() -> Optional[str]:
    if os.geteuid() == 0: 
        target_user = os.environ.get("SUDO_USER")
        if not target_user: app_logger.error("SUDO_USER not set."); con.print_error("SUDO_USER not set."); return None
        try: system_utils.run_command(["id", "-u", target_user], capture_output=True, check=True, print_fn_info=None, logger=app_logger)
        except: app_logger.error(f"User {target_user} invalid."); con.print_error(f"User {target_user} invalid."); return None
        return target_user
    else: current_user = os.getlogin(); app_logger.warning(f"Not root, using {current_user}."); con.print_warning(f"Not root, using {current_user}."); return current_user

def _get_user_home(username: str) -> Optional[Path]:
    try:
        proc = system_utils.run_command(["getent", "passwd", username], capture_output=True, check=True,print_fn_info=None, logger=app_logger)
        home_dir_str = proc.stdout.strip().split(":")[-1]
        if not home_dir_str: app_logger.error(f"No home dir for {username}."); return None
        return Path(home_dir_str)
    except Exception as e: app_logger.error(f"Error get home for {username}: {e}", exc_info=True); return None

def _install_dnf_packages_ph4(packages: List[str]) -> bool:
    if not packages: app_logger.info("No DNF for Ph4."); con.print_info("No DNF for Ph4."); return True
    app_logger.info(f"Install DNF Ph4: {packages}"); con.print_sub_step(f"Install DNF: {', '.join(packages)}")
    try:
        cmd = ["sudo", "dnf", "install", "-y", "--allowerasing"] + packages
        system_utils.run_command(cmd, capture_output=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger)
        con.print_success(f"DNF pkgs done: {', '.join(packages)}"); app_logger.info(f"DNF Ph4 done: {packages}"); return True
    except Exception as e: app_logger.error(f"Fail DNF Ph4: {packages}. {e}", exc_info=True); return False

def _install_pip_packages_ph4(packages: List[str], target_user: str) -> bool:
    if not packages: app_logger.info("No pip for Ph4."); con.print_info("No pip for Ph4."); return True
    app_logger.info(f"Install pip for {target_user}: {packages}"); con.print_sub_step(f"Install pip for {target_user}: {', '.join(packages)}")
    all_success = True
    for pkg_name in packages:
        app_logger.info(f"Pip install {pkg_name} for {target_user}."); con.print_info(f"Pip install {pkg_name} for {target_user}...")
        cmd = f"python3 -m pip install --user --upgrade {shlex.quote(pkg_name)}"
        try:
            system_utils.run_command(cmd, run_as_user=target_user, shell=True, capture_output=True, check=True,print_fn_info=con.print_info, print_fn_error=con.print_error,print_fn_sub_step=con.print_sub_step,logger=app_logger)
            con.print_success(f"Pip {pkg_name} done for {target_user}."); app_logger.info(f"Pip {pkg_name} done for {target_user}.")
        except FileNotFoundError: app_logger.error(f"python3/pip not found for {target_user} for {pkg_name}."); con.print_error(f"python3/pip not found for {target_user}."); all_success = False; break 
        except Exception as e: app_logger.error(f"Fail pip {pkg_name} for {target_user}: {e}", exc_info=True); con.print_error(f"Fail pip {pkg_name}."); all_success = False
    return all_success

def _verify_gext_cli_usability(target_user: str) -> bool:
    app_logger.info(f"Verify gext usability for {target_user}."); con.print_info(f"Verify gext for {target_user}...")
    cmd = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} --version"
    try:
        proc = system_utils.run_command(cmd,run_as_user=target_user,shell=True,capture_output=True,check=True,print_fn_info=con.print_info,logger=app_logger)
        app_logger.debug(f"gext --version STDOUT for '{target_user}': {proc.stdout.strip()}")
        con.print_success(f"gext usable for {target_user}."); app_logger.info(f"gext usable for {target_user}."); return True
    except Exception as e: app_logger.error(f"gext verify fail for {target_user}: {e}", exc_info=True); con.print_error(f"gext verify fail."); return False

def _install_ego_extension(ext_key_name: str, ext_cfg: Dict, target_user: str) -> bool:
    uuid = ext_cfg.get("uuid"); numerical_id = ext_cfg.get("numerical_id"); pretty_name = ext_cfg.get("name", ext_key_name) 
    if not uuid: app_logger.error(f"No uuid EGO ext '{pretty_name}'. Skip."); con.print_error(f"No uuid EGO ext '{pretty_name}'. Skip."); return False
    install_target = str(numerical_id) if numerical_id else uuid
    app_logger.info(f"Install EGO ext '{pretty_name}' ({install_target}) for {target_user} using --filesystem.")
    con.print_info(f"Install EGO ext '{pretty_name}' ({install_target}) for {target_user}...")
    try:
        # INSTALL using --filesystem backend (no dbus-run-session needed for this part)
        install_cmd_list = ["python3", "-m", GEXT_CLI_MODULE, "install", "--filesystem", install_target]
        app_logger.info(f"Exec EGO install cmd: {' '.join(install_cmd_list)} (as {target_user})")
        proc_install = system_utils.run_command(install_cmd_list, run_as_user=target_user, shell=False, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
        app_logger.info(f"Install STDOUT '{pretty_name}': {proc_install.stdout.strip() if proc_install.stdout else 'None'}")
        if proc_install.stderr and proc_install.stderr.strip(): app_logger.warning(f"Install STDERR '{pretty_name}': {proc_install.stderr.strip()}")
        con.print_success(f"EGO ext '{pretty_name}' install cmd executed.")

        app_logger.info(f"Enable EGO ext '{pretty_name}' (UUID: {uuid}) using DBus.")
        con.print_info(f"Enable EGO ext '{pretty_name}' (UUID: {uuid})...")
        # ENABLE using DBus (dbus-run-session is appropriate here)
        enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid)}"
        proc_enable = system_utils.run_command(enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
        app_logger.info(f"Enable STDOUT '{pretty_name}': {proc_enable.stdout.strip() if proc_enable.stdout else 'None'}")
        if proc_enable.stderr and proc_enable.stderr.strip(): app_logger.warning(f"Enable STDERR '{pretty_name}': {proc_enable.stderr.strip()}")
        con.print_success(f"EGO ext '{pretty_name}' enable cmd executed.")
        
        app_logger.info(f"Verify EGO ext '{pretty_name}' with 'gext info' (DBus).")
        info_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} info {shlex.quote(uuid)}"
        proc_info = system_utils.run_command(info_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=False, logger=app_logger)
        app_logger.debug(f"gext info STDOUT '{uuid}': {proc_info.stdout.strip() if proc_info.stdout else 'None'}")
        if proc_info.stderr and proc_info.stderr.strip(): app_logger.debug(f"gext info STDERR '{uuid}': {proc_info.stderr.strip()}")
        if proc_info.returncode == 0 and "State: ENABLED" in proc_info.stdout:
            app_logger.info(f"VERIFIED: EGO ext '{pretty_name}' ENABLED."); con.print_success(f"VERIFIED: Ext '{pretty_name}' ENABLED.")
        else:
            app_logger.warning(f"VERIFY PROBLEM: EGO ext '{pretty_name}' not ENABLED. RC: {proc_info.returncode}. May need session restart."); con.print_warning(f"VERIFY: '{pretty_name}' not enabled. May need session restart.")
        return True
    except subprocess.CalledProcessError as e: # Catch errors from check=True commands
        app_logger.error(f"CalledProcessError EGO ext '{pretty_name}': Cmd: {' '.join(e.cmd) if isinstance(e.cmd, list) else e.cmd}, RC: {e.returncode}", exc_info=False)
        stderr_lower = e.stderr.lower() if e.stderr else ""
        if "already enabled" in stderr_lower: app_logger.info(f"Ext '{pretty_name}' already enabled."); con.print_info(f"Ext '{pretty_name}' already enabled."); return True 
        if "already installed" in stderr_lower: # This might come from install --filesystem too
            app_logger.info(f"Ext '{pretty_name}' already installed. Trying enable again."); con.print_info(f"Ext '{pretty_name}' already installed. Try enable...")
            try: # Try enable again
                enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid)}"
                system_utils.run_command(enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True,print_fn_info=con.print_info,print_fn_error=con.print_error, logger=app_logger)
                con.print_success(f"EGO ext '{pretty_name}' enabled after 'already installed'."); return True
            except Exception as e_enable: app_logger.error(f"Fail enable EGO ext '{pretty_name}' after 'already installed': {e_enable}", exc_info=True); con.print_error(f"Fail enable EGO '{pretty_name}'."); return False
        con.print_error(f"Failed EGO ext '{pretty_name}'. Check logs."); return False
    except Exception as e: app_logger.error(f"Unexpected error EGO ext '{pretty_name}': {e}", exc_info=True); con.print_error(f"Unexpected error EGO ext '{pretty_name}'."); return False

def _install_git_extension(ext_key_name: str, ext_cfg: Dict, target_user: str) -> bool:
    git_url = ext_cfg.get("url"); install_script_name = ext_cfg.get("install_script") 
    uuid_to_enable = ext_cfg.get("uuid_to_enable"); pretty_name = ext_cfg.get("name", ext_key_name)
    if not git_url or not install_script_name: app_logger.error(f"No url/script Git ext '{pretty_name}'. Skip."); con.print_error(f"No url/script Git ext '{pretty_name}'. Skip."); return False
    app_logger.info(f"Install Git ext '{pretty_name}' from {git_url} for {target_user}."); con.print_info(f"Install Git ext '{pretty_name}' from {git_url} for {target_user}...")
    install_script_command_part = ""
    if install_script_name.lower() == "make install": install_script_command_part = "make install"
    elif install_script_name.lower() == "make": install_script_command_part = "make"
    elif install_script_name.endswith(".sh"): install_script_command_part = f"./{shlex.quote(install_script_name)}"
    else: install_script_command_part = shlex.quote(install_script_name) 
    repo_name_from_url = Path(git_url).name.removesuffix(".git") if Path(git_url).name.endswith(".git") else Path(git_url).name
    shell_safe_pretty_name = shlex.quote(pretty_name)
    # The install script itself should copy files to the correct user extension path.
    # dbus-run-session for the install script is kept in case it internally calls gsettings or other D-Bus services.
    script_to_run_as_user = f"""
        set -e; SHELL_PRETTY_NAME={shell_safe_pretty_name}
        TMP_EXT_DIR=$(mktemp -d -t gnome_ext_{shlex.quote(ext_key_name)}_XXXXXX)
        trap 'echo "Cleaning up $TMP_EXT_DIR for $SHELL_PRETTY_NAME (user $(whoami))"; rm -rf "$TMP_EXT_DIR"' EXIT
        echo "Cloning {shlex.quote(git_url)} into $TMP_EXT_DIR/{shlex.quote(repo_name_from_url)} (user $(whoami))..."
        git clone --depth=1 {shlex.quote(git_url)} "$TMP_EXT_DIR/{shlex.quote(repo_name_from_url)}"
        cd "$TMP_EXT_DIR/{shlex.quote(repo_name_from_url)}"
        echo "CWD for install: $(pwd)"; echo "Run install script: {install_script_command_part}..."
        if [ -f "{install_script_name}" ] && [[ "{install_script_name}" == *.sh ]]; then chmod +x "{install_script_name}"; fi
        dbus-run-session -- {install_script_command_part} 
        echo "Install script for $SHELL_PRETTY_NAME finished."
    """
    try:
        app_logger.info(f"Exec install script for '{pretty_name}' as {target_user}."); con.print_sub_step(f"Exec install script for '{pretty_name}' as {target_user}.")
        system_utils.run_command(script_to_run_as_user, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger)
        con.print_success(f"Git ext '{pretty_name}' install script executed.")
        if uuid_to_enable:
            app_logger.info(f"Enable Git ext '{pretty_name}' (UUID: {uuid_to_enable}) using DBus.")
            con.print_info(f"Enable '{pretty_name}' (UUID: {uuid_to_enable})...")
            # ENABLE using DBus
            enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid_to_enable)}"
            system_utils.run_command(enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
            con.print_success(f"Git ext '{pretty_name}' enable cmd executed.")
            app_logger.info(f"Verify Git ext '{pretty_name}' with 'gext info' (DBus).")
            info_cmd_str_git = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} info {shlex.quote(uuid_to_enable)}"
            proc_info_git = system_utils.run_command(info_cmd_str_git, run_as_user=target_user, shell=True, capture_output=True, check=False, logger=app_logger)
            app_logger.debug(f"gext info STDOUT '{uuid_to_enable}': {proc_info_git.stdout.strip() if proc_info_git.stdout else 'None'}")
            if proc_info_git.stderr and proc_info_git.stderr.strip(): app_logger.debug(f"gext info STDERR '{uuid_to_enable}': {proc_info_git.stderr.strip()}")
            if proc_info_git.returncode == 0 and "State: ENABLED" in proc_info_git.stdout:
                app_logger.info(f"VERIFIED: Git ext '{pretty_name}' ENABLED."); con.print_success(f"VERIFIED: Ext '{pretty_name}' ENABLED.")
            else:
                app_logger.warning(f"VERIFY PROBLEM: Git ext '{pretty_name}' not ENABLED. RC: {proc_info_git.returncode}. May need session restart."); con.print_warning(f"VERIFY: '{pretty_name}' not enabled. May need session restart.")
        else: con.print_info(f"No 'uuid_to_enable' for '{pretty_name}'.")
        return True
    except FileNotFoundError as e: app_logger.error(f"File not found Git ext '{pretty_name}': {e}. git/mktemp missing?", exc_info=True); con.print_error(f"File not found for Git ext '{pretty_name}'."); return False
    except subprocess.CalledProcessError as e:
        app_logger.error(f"CalledProcessError Git ext '{pretty_name}': Cmd: {' '.join(e.cmd) if isinstance(e.cmd, list) else e.cmd}, RC: {e.returncode}", exc_info=False)
        stderr_lower = e.stderr.lower() if e.stderr else ""
        if "already enabled" in stderr_lower: app_logger.info(f"Ext '{pretty_name}' already enabled."); con.print_info(f"Ext '{pretty_name}' already enabled."); return True 
        con.print_error(f"Failed Git ext '{pretty_name}'. Review logs."); return False
    except Exception as e: app_logger.error(f"Unexpected error Git ext '{pretty_name}': {e}", exc_info=True); con.print_error(f"Unexpected error Git ext '{pretty_name}'."); return False

def _set_dark_theme_preference(target_user: str) -> bool:
    app_logger.info(f"Attempting to set system appearance to dark mode for user '{target_user}'.")
    con.print_sub_step(f"Attempting to set system appearance to dark mode for user '{target_user}'...")
    schema = "org.gnome.desktop.interface"; color_scheme_key = "color-scheme"; color_scheme_value = "prefer-dark" 
    app_logger.info(f"Setting GSettings: {schema} {color_scheme_key} to '{color_scheme_value}' (as {target_user})")
    con.print_info(f"Setting GSettings: {schema} {color_scheme_key} to '{color_scheme_value}' (as {target_user})")
    cmd_color_scheme = ["dbus-run-session", "--", "gsettings", "set", schema, color_scheme_key, color_scheme_value]
    success_color_scheme = False
    try:
        system_utils.run_command(cmd_color_scheme,run_as_user=target_user,shell=False,capture_output=True,check=True,print_fn_info=con.print_info,print_fn_error=con.print_error,logger=app_logger)
        app_logger.info(f"GSettings: '{schema} {color_scheme_key}' successfully set to '{color_scheme_value}'."); con.print_success(f"GSettings: '{schema} {color_scheme_key}' set."); success_color_scheme = True
    except FileNotFoundError: app_logger.error(f"gsettings/dbus-run-session not found for dark theme.", exc_info=True); con.print_error(f"gsettings/dbus-run-session not found."); return False 
    except subprocess.CalledProcessError as e: app_logger.error(f"Failed set GSettings '{schema} {color_scheme_key}'. Cmd: {' '.join(e.cmd)}, RC: {e.returncode}", exc_info=False); con.print_error(f"Failed set GSettings '{schema} {color_scheme_key}'.")
    except Exception as e: app_logger.error(f"Unexpected error setting '{color_scheme_key}': {e}", exc_info=True); con.print_error(f"Unexpected error setting '{color_scheme_key}'.")
    
    gtk_theme_key = "gtk-theme"; gtk_theme_value = "Adwaita-dark" 
    app_logger.info(f"Attempting GSettings: {schema} {gtk_theme_key} to '{gtk_theme_value}' (as {target_user})")
    con.print_info(f"Attempting GSettings: {schema} {gtk_theme_key} to '{gtk_theme_value}' (as {target_user})")
    cmd_gtk_theme = ["dbus-run-session", "--", "gsettings", "set", schema, gtk_theme_key, gtk_theme_value]
    try:
        system_utils.run_command(cmd_gtk_theme,run_as_user=target_user,shell=False,capture_output=True,check=False,print_fn_info=con.print_info,print_fn_error=con.print_error,logger=app_logger)
        app_logger.info(f"Attempt to set GSettings '{gtk_theme_key}' to '{gtk_theme_value}' completed.")
        verify_gtk_cmd = ["dbus-run-session", "--", "gsettings", "get", schema, gtk_theme_key]
        proc_gtk_get = system_utils.run_command(verify_gtk_cmd, run_as_user=target_user, shell=False, capture_output=True, check=False, logger=app_logger)
        app_logger.debug(f"Current value of '{schema} {gtk_theme_key}': {proc_gtk_get.stdout.strip() if proc_gtk_get.stdout else 'N/A'}")
    except Exception as e: app_logger.warning(f"Could not set/verify '{gtk_theme_key}': {e}. Non-critical.", exc_info=True)

    if success_color_scheme: app_logger.info("GNOME dark mode pref applied. May need logout/login."); con.print_info("GNOME dark mode pref applied. May need logout/login.")
    else: app_logger.warning("Primary dark mode (color-scheme) failed."); con.print_warning("Primary dark mode (color-scheme) failed.")
    return success_color_scheme

# --- Main Phase Function ---
def run_phase4(app_config: dict) -> bool:
    app_logger.info("Starting Phase 4: GNOME Configuration & Extensions.")
    con.print_step("PHASE 4: GNOME Configuration & Extensions")
    overall_success = True
    phase4_config_data = config_loader.get_phase_data(app_config, "phase4_gnome_configuration")
    if not phase4_config_data: app_logger.warning("No config Ph4. Skip."); con.print_warning("No config Ph4. Skip."); return True 
    target_user = _get_target_user()
    if not target_user: return False 
    _ = _get_user_home(target_user) 
    app_logger.info(f"Run GNOME configs for user: {target_user}"); con.print_info(f"Run GNOME configs for user: [bold cyan]{target_user}[/bold cyan]")

    app_logger.info("Ph4, Step 1: Install DNF."); con.print_info("\nStep 1: Install DNF GNOME...")
    dnf_packages = phase4_config_data.get("dnf_packages", [])
    if dnf_packages:
        if not _install_dnf_packages_ph4(dnf_packages): overall_success = False
    else: app_logger.info("No DNF pkgs for Ph4."); con.print_info("No DNF pkgs for Ph4.")

    app_logger.info(f"Ph4, Step 2: Install pip for {target_user}."); con.print_info(f"\nStep 2: Install pip for {target_user}...")
    pip_packages_to_install = phase4_config_data.get("pip_packages", []) 
    if pip_packages_to_install:
        if not _install_pip_packages_ph4(pip_packages_to_install, target_user): overall_success = False
    else: app_logger.info("No pip pkgs for Ph4."); con.print_info("No pip pkgs for Ph4.")

    gext_cli_ready = False
    if phase4_config_data.get("gnome_extensions"): 
        app_logger.info("Ph4, Step 3: Verify gext usability..."); gext_cli_ready = _verify_gext_cli_usability(target_user)
        if not gext_cli_ready: app_logger.error("gext not usable. Skip ext install."); con.print_error("gext not usable. Skip ext install."); overall_success = False 
    else: app_logger.info("No GNOME exts configured; skip gext usability check."); gext_cli_ready = True 

    if gext_cli_ready and phase4_config_data.get("gnome_extensions"):
        gnome_extensions_cfg = phase4_config_data.get("gnome_extensions", {})
        if gnome_extensions_cfg: 
            app_logger.info(f"Ph4, Step 4: Install/enable GNOME exts for {target_user}."); con.print_info(f"\nStep 4: Install/enable GNOME exts for {target_user}...")
            extensions_success_all = True
            for ext_key__name, ext_config_dict in gnome_extensions_cfg.items(): 
                ext_type = ext_config_dict.get("type"); pretty_name = ext_config_dict.get("name", ext_key__name) 
                app_logger.info(f"Processing ext: {pretty_name} (Type: {ext_type}, Key: {ext_key__name})"); con.print_sub_step(f"Processing ext: {pretty_name} (Type: {ext_type})")
                success_current_ext = False
                if ext_type == "ego": success_current_ext = _install_ego_extension(ext_key__name, ext_config_dict, target_user)
                elif ext_type == "git": success_current_ext = _install_git_extension(ext_key__name, ext_config_dict, target_user)
                else: app_logger.warning(f"Unknown GNOME ext type '{ext_type}' for '{pretty_name}'. Skip."); con.print_warning(f"Unknown GNOME ext type '{ext_type}'."); extensions_success_all = False 
                if not success_current_ext: extensions_success_all = False 
            if not extensions_success_all: overall_success = False; app_logger.warning("Some GNOME exts failed."); con.print_warning("Some GNOME exts failed.")
            else: app_logger.info("All GNOME exts processed."); con.print_success("All GNOME exts processed.")
    elif not gext_cli_ready and phase4_config_data.get("gnome_extensions"): app_logger.warning("Skipped GNOME ext install due to gext setup fail."); con.print_warning("Skipped GNOME ext install due to gext setup fail.")

    app_logger.info("Ph4, Step 5: Install Flatpak apps."); con.print_info("\nStep 5: Install Flatpak apps (system-wide)...")
    flatpak_apps_to_install = phase4_config_data.get("flatpak_apps", {})
    if flatpak_apps_to_install:
        if not system_utils.install_flatpak_apps(apps_to_install=flatpak_apps_to_install, system_wide=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger):
            overall_success = False; app_logger.error("Ph4 Flatpak install issues."); con.print_error("Ph4 Flatpak install issues.")
    else: app_logger.info("No Flatpak apps for Ph4."); con.print_info("No Flatpak apps for Ph4.")

    app_logger.info("Ph4, Step 6: Set dark theme preference."); con.print_info("\nStep 6: Set dark theme preference...")
    if not _set_dark_theme_preference(target_user):
        app_logger.warning(f"Failed to fully set dark theme for {target_user}."); con.print_warning(f"Failed to fully set dark theme for {target_user}.")
        # overall_success = False # Decide if this is critical
        
    if overall_success: app_logger.info("Ph4 done successfully."); con.print_success("Phase 4: GNOME Configuration & Extensions completed successfully.")
    else: app_logger.error("Ph4 done with errors."); con.print_error("Phase 4: GNOME Configuration & Extensions completed with errors. Review logs.")
    return overall_success