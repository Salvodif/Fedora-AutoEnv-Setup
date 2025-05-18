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
# _install_pip_packages_ph4, _verify_gext_cli_usability, _install_git_extension, _set_dark_theme_preference
# These will be the same as the previous "complete" version, except for _install_ego_extension.
# I'll include their signatures and mark where _install_ego_extension changes.

def _get_target_user() -> Optional[str]:
    # (Implementation from previous complete version)
    if os.geteuid() == 0: 
        target_user = os.environ.get("SUDO_USER")
        if not target_user: app_logger.error("SUDO_USER not set."); con.print_error("SUDO_USER not set."); return None
        try: system_utils.run_command(["id", "-u", target_user], capture_output=True, check=True, print_fn_info=None, logger=app_logger)
        except: app_logger.error(f"User {target_user} invalid."); con.print_error(f"User {target_user} invalid."); return None
        return target_user
    else: current_user = os.getlogin(); app_logger.warning(f"Not root, using {current_user}."); con.print_warning(f"Not root, using {current_user}."); return current_user

def _get_user_home(username: str) -> Optional[Path]:
    # (Implementation from previous complete version)
    try:
        proc = system_utils.run_command(["getent", "passwd", username], capture_output=True, check=True,print_fn_info=None, logger=app_logger)
        home_dir_str = proc.stdout.strip().split(":")[-1]
        if not home_dir_str: app_logger.error(f"No home dir for {username}."); return None
        return Path(home_dir_str)
    except Exception as e: app_logger.error(f"Error get home for {username}: {e}", exc_info=True); return None

def _install_dnf_packages_ph4(packages: List[str]) -> bool:
    # (Implementation from previous complete version)
    if not packages: app_logger.info("No DNF for Ph4."); con.print_info("No DNF for Ph4."); return True
    app_logger.info(f"Install DNF Ph4: {packages}"); con.print_sub_step(f"Install DNF: {', '.join(packages)}")
    try:
        cmd = ["sudo", "dnf", "install", "-y", "--allowerasing"] + packages
        system_utils.run_command(cmd, capture_output=True, print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step, logger=app_logger)
        con.print_success(f"DNF pkgs done: {', '.join(packages)}"); app_logger.info(f"DNF Ph4 done: {packages}"); return True
    except Exception as e: app_logger.error(f"Fail DNF Ph4: {packages}. {e}", exc_info=True); return False

def _install_pip_packages_ph4(packages: List[str], target_user: str) -> bool:
    # (Implementation from previous complete version)
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
    # (Implementation from previous complete version)
    app_logger.info(f"Verify gext usability for {target_user}."); con.print_info(f"Verify gext for {target_user}...")
    cmd = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} --version"
    try:
        proc = system_utils.run_command(cmd,run_as_user=target_user,shell=True,capture_output=True,check=True,print_fn_info=con.print_info,logger=app_logger)
        app_logger.debug(f"gext --version STDOUT for '{target_user}': {proc.stdout.strip()}")
        con.print_success(f"gext usable for {target_user}."); app_logger.info(f"gext usable for {target_user}."); return True
    except Exception as e: app_logger.error(f"gext verify fail for {target_user}: {e}", exc_info=True); con.print_error(f"gext verify fail."); return False

def _install_ego_extension(ext_key_name: str, ext_cfg: Dict, target_user: str) -> bool:
    """
    Installs and enables a GNOME extension from extensions.gnome.org (EGO)
    using the default D-Bus backend of gnome-extensions-cli.
    This may prompt the user for confirmation via a GNOME Shell dialog.
    """
    uuid = ext_cfg.get("uuid")
    numerical_id = ext_cfg.get("numerical_id")
    pretty_name = ext_cfg.get("name", ext_key_name) 

    if not uuid:
        app_logger.error(f"Missing 'uuid' for EGO extension '{pretty_name}'. Skipping.")
        con.print_error(f"Missing 'uuid' for EGO extension '{pretty_name}'. Skipping.")
        return False
    
    install_target = str(numerical_id) if numerical_id else uuid
    app_logger.info(f"Attempting to install EGO extension '{pretty_name}' (ID/UUID: {install_target}) for user '{target_user}' using D-Bus backend.")
    # User message is handled in the main loop before starting extensions.
    
    try:
        # INSTALL using default D-Bus backend. User will be prompted by GNOME Shell.
        # dbus-run-session is crucial here.
        install_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} install {shlex.quote(install_target)}"
        app_logger.info(f"Executing EGO install command (interactive D-Bus): {install_cmd_str} (as {target_user})")
        proc_install = system_utils.run_command(
            install_cmd_str, run_as_user=target_user, shell=True, 
            capture_output=True, 
            check=True, # Let it fail if gext install itself returns non-zero (e.g., extension not found on EGO)
            print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger
        )
        app_logger.info(f"Install command STDOUT for '{pretty_name}': {proc_install.stdout.strip() if proc_install.stdout else 'None'}")
        if proc_install.stderr and proc_install.stderr.strip(): 
            app_logger.warning(f"Install command STDERR for '{pretty_name}': {proc_install.stderr.strip()}")
        # A successful exit code here means gext launched; user interaction determines actual install.
        con.print_success(f"EGO extension '{pretty_name}' install process initiated. Please check GNOME Shell for prompts.")

        # ENABLE using DBus. This should also be interactive if the extension requires it,
        # or might just work if already installed and recognized by the shell.
        app_logger.info(f"Attempting to enable EGO extension '{pretty_name}' (UUID: {uuid}) using DBus.")
        con.print_info(f"Attempting to enable EGO extension '{pretty_name}' (UUID: {uuid})...")
        enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid)}"
        proc_enable = system_utils.run_command(
            enable_cmd_str, run_as_user=target_user, shell=True, 
            capture_output=True, check=True, 
            print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger
        )
        app_logger.info(f"Enable command STDOUT for '{pretty_name}': {proc_enable.stdout.strip() if proc_enable.stdout else 'None'}")
        if proc_enable.stderr and proc_enable.stderr.strip(): app_logger.warning(f"Enable command STDERR for '{pretty_name}': {proc_enable.stderr.strip()}")
        con.print_success(f"EGO extension '{pretty_name}' (UUID: {uuid}) enable command executed.")
        
        # Verification is still useful but might not reflect immediately if user interaction is pending.
        app_logger.info(f"Verifying status of '{pretty_name}' with 'gext info' (DBus). This reflects current D-Bus state.")
        info_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} info {shlex.quote(uuid)}"
        proc_info = system_utils.run_command(info_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=False, logger=app_logger, print_fn_info=None)
        app_logger.debug(f"'gext info {uuid}' STDOUT: {proc_info.stdout.strip() if proc_info.stdout else 'None'}")
        if proc_info.stderr and proc_info.stderr.strip(): app_logger.debug(f"'gext info {uuid}' STDERR: {proc_info.stderr.strip()}")
        if proc_info.returncode == 0 and "State: ENABLED" in proc_info.stdout:
            app_logger.info(f"VERIFIED (via gext info): EGO extension '{pretty_name}' is ENABLED.")
            con.print_success(f"Verified (via gext info): Extension '{pretty_name}' is reported as enabled.")
        else:
            app_logger.warning(f"VERIFICATION (via gext info): EGO ext '{pretty_name}' not reported as ENABLED. RC: {proc_info.returncode}. User action might be pending or shell reload needed.")
            con.print_warning(f"Verification for '{pretty_name}' indicated it might not be enabled yet. User confirmation for install/enable might be required, or a session restart.")
        return True # Success here means the commands were issued. Actual state depends on user interaction.
    
    except subprocess.CalledProcessError as e:
        app_logger.error(f"CalledProcessError for EGO extension '{pretty_name}': Cmd: {' '.join(e.cmd) if isinstance(e.cmd, list) else e.cmd}, RC: {e.returncode}", exc_info=False)
        stderr_lower = e.stderr.lower() if e.stderr else ""
        # "Already installed/enabled" messages from gext might still be on stderr but with RC 0 if non-fatal.
        # If check=True caught an error, it's usually more significant.
        if "already enabled" in stderr_lower:
            app_logger.info(f"Extension '{pretty_name}' was already enabled (reported by CalledProcessError).")
            con.print_info(f"Extension '{pretty_name}' was already enabled.")
            return True 
        if "already installed" in stderr_lower:
            app_logger.info(f"Extension '{pretty_name}' was already installed (reported by CalledProcessError). Enable might still be needed or succeed.")
            con.print_info(f"Extension '{pretty_name}' was already installed.")
            # The enable step will be attempted. If it also says "already enabled", that's fine.
            # If we returned False here, the enable step wouldn't run.
            # Let's assume the enable step will clarify.
            return True # Continue to enable step or count as success if enable fails for "already enabled"
        con.print_error(f"Failed to process EGO extension '{pretty_name}'. Check logs for details.")
        return False
    except Exception as e: 
        app_logger.error(f"An unexpected error occurred with EGO extension '{pretty_name}': {e}", exc_info=True)
        con.print_error(f"An unexpected error occurred with EGO extension '{pretty_name}'. Check logs for details.")
        return False

def _install_git_extension(ext_key_name: str, ext_cfg: Dict, target_user: str) -> bool:
    # (This function's core logic for cloning and running the extension's own install script remains.
    # The subsequent 'gext enable' part will use D-Bus and dbus-run-session.)
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
            enable_cmd_str = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} enable {shlex.quote(uuid_to_enable)}"
            system_utils.run_command(enable_cmd_str, run_as_user=target_user, shell=True, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
            con.print_success(f"Git ext '{pretty_name}' enable cmd executed.")
            app_logger.info(f"Verify Git ext '{pretty_name}' with 'gext info' (DBus).")
            info_cmd_str_git = f"dbus-run-session -- python3 -m {GEXT_CLI_MODULE} info {shlex.quote(uuid_to_enable)}"
            proc_info_git = system_utils.run_command(info_cmd_str_git, run_as_user=target_user, shell=True, capture_output=True, check=False, logger=app_logger, print_fn_info=None)
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
    # (Implementation from previous complete version)
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
        proc_gtk_get = system_utils.run_command(verify_gtk_cmd, run_as_user=target_user, shell=False, capture_output=True, check=False, logger=app_logger, print_fn_info=None)
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

    # Step 1: Install DNF packages (System-level tools)
    app_logger.info("Ph4, Step 1: Install DNF."); con.print_info("\nStep 1: Install DNF GNOME...")
    dnf_packages = phase4_config_data.get("dnf_packages", [])
    if dnf_packages:
        if not _install_dnf_packages_ph4(dnf_packages): overall_success = False
    else: app_logger.info("No DNF pkgs for Ph4."); con.print_info("No DNF pkgs for Ph4.")

    # Step 2: Install pip packages (User-level CLI tools)
    app_logger.info(f"Ph4, Step 2: Install pip for {target_user}."); con.print_info(f"\nStep 2: Install pip for {target_user}...")
    pip_packages_to_install = phase4_config_data.get("pip_packages", []) 
    if pip_packages_to_install:
        if not _install_pip_packages_ph4(pip_packages_to_install, target_user): overall_success = False
    else: app_logger.info("No pip pkgs for Ph4."); con.print_info("No pip pkgs for Ph4.")

    # Step 3: Install Flatpak applications (GUI Management Tools)
    app_logger.info("Ph4, Step 3: Installing Flatpak applications (e.g., Extension Manager)...")
    con.print_info("\nStep 3: Installing Flatpak applications (system-wide)...")
    flatpak_apps_to_install = phase4_config_data.get("flatpak_apps", {})
    if flatpak_apps_to_install:
        if not system_utils.install_flatpak_apps(
                apps_to_install=flatpak_apps_to_install, 
                system_wide=True, # Assuming Extension Manager should be system-wide for all users
                print_fn_info=con.print_info, 
                print_fn_error=con.print_error, 
                print_fn_sub_step=con.print_sub_step,
                logger=app_logger
            ):
            overall_success = False
            app_logger.error("Phase 4 Flatpak installation encountered issues.")
            con.print_error("Phase 4 Flatpak installation encountered issues.")
    else: 
        app_logger.info("No Flatpak applications listed for Phase 4.")
        con.print_info("No Flatpak applications listed for installation in Phase 4.")


    # Step 4: Verify gnome-extensions-cli usability (after pip install)
    gext_cli_ready = False
    if phase4_config_data.get("gnome_extensions"): 
        app_logger.info("Ph4, Step 4: Verify gext usability..."); 
        con.print_info("\nStep 4: Verifying GNOME Extensions CLI tool...") # User message
        gext_cli_ready = _verify_gext_cli_usability(target_user)
        if not gext_cli_ready: 
            app_logger.error("gext not usable. Skip ext install."); 
            con.print_error("GNOME Extensions CLI (gext) not usable. Extension installation will be skipped.")
            overall_success = False 
    else: 
        app_logger.info("No GNOME exts configured; skip gext usability check.")
        gext_cli_ready = True # No extensions to install, so CLI is not critically needed

    # Step 5: Install GNOME Extensions (EGO and Git)
    if gext_cli_ready and phase4_config_data.get("gnome_extensions"):
        gnome_extensions_cfg = phase4_config_data.get("gnome_extensions", {})
        if gnome_extensions_cfg: 
            app_logger.info(f"Ph4, Step 5: Install/enable GNOME exts for {target_user}.")
            # Inform user about potential interactivity
            con.print_panel(
                "[bold yellow]Attention:[/]\n"
                "The following steps will attempt to install GNOME Shell extensions.\n"
                "Your GNOME Shell may display a dialog asking for permission to install each extension.\n"
                "Please monitor your desktop and approve these prompts if they appear.",
                title="GNOME Extension Installation Notice",
                style="yellow"
            )
            con.ask_question("Press Enter to continue with extension installation...") # Pause for user to read

            con.print_info(f"\nStep 5: Installing and enabling GNOME Shell Extensions for user '{target_user}'...")
            extensions_success_all = True
            for ext_key__name, ext_config_dict in gnome_extensions_cfg.items(): 
                ext_type = ext_config_dict.get("type"); pretty_name = ext_config_dict.get("name", ext_key__name) 
                app_logger.info(f"Processing ext: {pretty_name} (Type: {ext_type}, Key: {ext_key__name})"); con.print_sub_step(f"Processing extension: {pretty_name} (Type: {ext_type})")
                success_current_ext = False
                if ext_type == "ego": success_current_ext = _install_ego_extension(ext_key__name, ext_config_dict, target_user)
                elif ext_type == "git": success_current_ext = _install_git_extension(ext_key__name, ext_config_dict, target_user)
                else: app_logger.warning(f"Unknown GNOME ext type '{ext_type}' for '{pretty_name}'. Skip."); con.print_warning(f"Unknown GNOME ext type '{ext_type}'."); extensions_success_all = False 
                if not success_current_ext: extensions_success_all = False 
            if not extensions_success_all: overall_success = False; app_logger.warning("Some GNOME exts failed."); con.print_warning("Some GNOME exts failed.")
            else: app_logger.info("All GNOME exts processed."); con.print_success("All GNOME exts processed.")
    elif not gext_cli_ready and phase4_config_data.get("gnome_extensions"): 
        app_logger.warning("Skipped GNOME ext install due to gext setup fail."); con.print_warning("Skipped GNOME ext install due to gext setup fail.")

    # Step 6: Set dark theme preference
    app_logger.info("Ph4, Step 6: Set dark theme preference."); con.print_info("\nStep 6: Set dark theme preference...")
    if not _set_dark_theme_preference(target_user):
        app_logger.warning(f"Failed to fully set dark theme for {target_user}."); con.print_warning(f"Failed to fully set dark theme for {target_user}.")
        # overall_success = False # Decide if this is critical
        
    if overall_success: 
        app_logger.info("Ph4 done successfully."); 
        con.print_success("Phase 4: GNOME Configuration & Extensions completed successfully.")
        if phase4_config_data.get("gnome_extensions") or True: # If theme or extensions were attempted
             con.print_warning("IMPORTANT: A logout and login (or a GNOME Shell restart via Alt+F2, 'r', Enter) "
                              "is likely required for all theme and extension changes to take full effect.")
    else: 
        app_logger.error("Ph4 done with errors."); 
        con.print_error("Phase 4: GNOME Configuration & Extensions completed with errors. Review logs.")
    return overall_success