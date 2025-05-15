# scripts/gnome_configuration.py
import logging
import os
import pwd
import shutil
import tempfile
from pathlib import Path

from scripts.myrich import (
    print_header, print_info, print_error, print_success, print_step, print_warning, console
)
from scripts.utils import run_command

TEMP_DIR = Path(tempfile.gettempdir()) / "gnome_setup_temp"

EXTENSIONS_TO_INSTALL = {
    "user-themes": {
        "type": "ego", "uuid": "user-theme@gnome-shell-extensions.gcampax.github.com",
        "name": "User Themes", "numerical_id": "19" # Often pre-packaged or installed with gnome-shell-extensions
    },
    "quick-settings-tweaks": {
        "type": "git", "url": "https://github.com/qwreey/quick-settings-tweaks.git",
        "install_script": "install.sh", "name": "Quick Settings Tweaks",
        "uuid_to_enable": "quick-settings-tweaks@qwreey" # Assumed UUID after install.sh
    },
    "just-perfection": {
        "type": "ego", "uuid": "just-perfection-desktop@just-perfection",
        "numerical_id": "3843", "name": "Just Perfection"
    },
    "rounded-window-corners": {
        "type": "ego", "uuid": "rounded-window-corners@yilozt",
        "numerical_id": "5237", "name": "Rounded Window Corners"
    },
    "dash-to-dock": {
        "type": "ego", "uuid": "dash-to-dock@micxgx.gmail.com",
        "numerical_id": "307", "name": "Dash to Dock"
    },
    "blur-my-shell": {
        "type": "ego", "uuid": "blur-my-shell@aunetx",
        "numerical_id": "3193", "name": "Blur my Shell"
    },
    "bluetooth-quick-connect": {
        "type": "ego", "uuid": "bluetooth-quick-connect@bjarosze.gmail.com",
        "numerical_id": "1401", "name": "Bluetooth Quick Connect"
    },
    "clipboard-indicator": {
        "type": "ego", "uuid": "clipboard-indicator@tudmotu.com",
        "numerical_id": "779", "name": "Clipboard Indicator"
    },
    "wireless-hid": {
        "type": "ego", "uuid": "wireless-hid@chlumskyvaclav.gmail.com",
        "numerical_id": "5764", "name": "Wireless HID"
    },
    "logo-menu": {
        "type": "ego", "uuid": "logo-menu@fthx",
        "numerical_id": "442", "name": "Logo Menu"
    }
}

def _get_user_env_vars(sudo_user: str):
    env_vars = {}
    try:
        user_info = pwd.getpwnam(sudo_user)
        user_uid = str(user_info.pw_uid)
        dbus_address = f"unix:path=/run/user/{user_uid}/bus"
        env_vars["DBUS_SESSION_BUS_ADDRESS"] = dbus_address
        env_vars["XDG_RUNTIME_DIR"] = f"/run/user/{user_uid}"
        # Try to get DISPLAY and XAUTHORITY, might be needed for gnome-extensions tool
        # This is tricky and might not always work reliably from a root script.
        # `loginctl show-session $(loginctl list-sessions | grep $USER | awk '{print $1}') -p Display -p Xauthority`
        # is one way to query it, but complex to integrate here.
        # For now, rely on DBUS_SESSION_BUS_ADDRESS and XDG_RUNTIME_DIR.
    except KeyError:
        print_warning(f"Could not get UID for user '{sudo_user}'. DBUS address might be incorrect.")
    except Exception as e:
        print_warning(f"Error determining environment for user '{sudo_user}': {e}")
    return env_vars

def _run_command_as_user(command: list[str], sudo_user: str, capture_output=False, check=True, text=True, cwd=None, env_extra=None):
    base_command = ["sudo", "-i", "-u", sudo_user] # -i simulates a login shell, might help with env
    
    user_env = _get_user_env_vars(sudo_user) # Get DBUS, XDG_RUNTIME_DIR
    if env_extra: # For things like DISPLAY if we can get it
        user_env.update(env_extra)

    env_prefix = []
    for k, v in user_env.items():
        env_prefix.append(f"{k}={v}")
    
    # Construct the command to be run by sudo
    # Instead of prefixing, pass to sudo's environment handling if possible, or use `env`
    # `sudo -u user VAR1=val1 VAR2=val2 command` is a common pattern.
    # However, `-i` will reset much of the environment.
    # A more robust way is `sudo -u user sh -c 'export VAR1=val1; export VAR2=val2; command'`
    # For simplicity with current run_command, we will use the env prefix with `env` command
    
    if env_prefix:
        # Using `env` command to set environment variables for the executed command
        full_command = base_command + ["env"] + env_prefix + command
    else:
        full_command = base_command + command
        
    cmd_str_for_log = ' '.join(command) # Log the core command
    if env_prefix:
        cmd_str_for_log = ' '.join(env_prefix) + ' ' + cmd_str_for_log
        
    print_info(f"Running as user '{sudo_user}': {cmd_str_for_log}" + (f" in {cwd}" if cwd else ""))

    return run_command(full_command, capture_output=capture_output, check=check, text=text, cwd=cwd)

def _enable_extension(uuid: str, display_name: str, sudo_user: str) -> bool:
    """Attempts to enable a GNOME Shell extension."""
    if not shutil.which("gnome-extensions"):
        print_warning(f"'gnome-extensions' tool not found. Cannot enable '{display_name}'.")
        return False

    print_info(f"Attempting to enable '{display_name}' (UUID: {uuid}) for user '{sudo_user}'...")
    cmd_enable = ["gnome-extensions", "enable", uuid]
    
    # Determine user for command execution
    target_user_for_cmd = sudo_user if os.geteuid() == 0 and sudo_user else os.getlogin()

    if os.geteuid() == 0 and sudo_user: # Running as root, targeting sudo_user
        stdout, stderr, rc = _run_command_as_user(cmd_enable, target_user_for_cmd, capture_output=True, check=False)
    else: # Running as the user directly
        stdout, stderr, rc = run_command(cmd_enable, capture_output=True, check=False)

    if rc == 0:
        print_success(f"Extension '{display_name}' enabled successfully for user '{target_user_for_cmd}'.")
        return True
    else:
        print_warning(f"Failed to enable extension '{display_name}' (UUID: {uuid}). RC: {rc}.")
        if stdout and stdout.strip(): console.print(f"[dim]Stdout: {stdout.strip()}[/dim]")
        if stderr and stderr.strip(): console.print(f"[dim]Stderr: {stderr.strip()}[/dim]")
        print_info(f"It might need to be enabled manually via the Extensions app or it might not be installed correctly.")
        return False

def _install_gnome_extension_from_git(ext_name: str, ext_details: dict, sudo_user: str) -> bool:
    print_info(f"Installing '{ext_details['name']}' from Git repository: {ext_details['url']}")
    if not shutil.which("git"):
        print_error("'git' command not found. Cannot clone. Please install git.")
        return False

    repo_name = Path(ext_details["url"]).stem
    clone_dir = TEMP_DIR / repo_name
    if clone_dir.exists():
        shutil.rmtree(clone_dir)
    clone_dir.mkdir(parents=True, exist_ok=True)

    if not run_command(["git", "clone", ext_details["url"], str(clone_dir)]):
        print_error(f"Failed to clone repository for '{ext_details['name']}'.")
        return False
    print_success(f"Repository for '{ext_details['name']}' cloned to {clone_dir}")

    install_script_path = clone_dir / ext_details["install_script"]
    if not install_script_path.is_file():
        print_error(f"Install script '{ext_details['install_script']}' not found for '{ext_details['name']}'.")
        return False
    
    run_command(["chmod", "+x", str(install_script_path)], check=False) # Make executable by current euid

    print_info(f"Running install script: {install_script_path.name} for user '{sudo_user}'")
    target_user_for_cmd = sudo_user if os.geteuid() == 0 and sudo_user else os.getlogin()
    
    script_executed_successfully = False
    if os.geteuid() == 0 and sudo_user:
        script_executed_successfully = _run_command_as_user([str(install_script_path)], target_user_for_cmd, cwd=str(clone_dir))
    else:
        script_executed_successfully = run_command([str(install_script_path)], cwd=str(clone_dir))

    if not script_executed_successfully:
        print_error(f"Install script for '{ext_details['name']}' failed.")
        return False
    print_success(f"Install script for '{ext_details['name']}' executed.")
    
    uuid_to_enable = ext_details.get("uuid_to_enable")
    if uuid_to_enable:
        return _enable_extension(uuid_to_enable, ext_details['name'], target_user_for_cmd)
    return True


def _check_and_install_gnome_extensions_cli():
    if shutil.which("gnome-extensions"):
        print_info("'gnome-extensions' command-line tool found.")
        return True
    print_warning("'gnome-extensions' tool not found. Attempting to install 'gnome-shell-extensions'...")
    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
    if run_command(["sudo", dnf_cmd, "install", "-y", "gnome-shell-extensions"]):
        print_success("'gnome-shell-extensions' installed. This should provide 'gnome-extensions' CLI.")
        if shutil.which("gnome-extensions"):
            return True
        else:
            print_error("'gnome-extensions' CLI still not found. Manual EGO extension installation likely needed.")
            return False
    else:
        print_error("Failed to install 'gnome-shell-extensions'. Manual EGO extension installation likely needed.")
        return False

def _install_gnome_extension_from_ego(ext_name: str, ext_details: dict, sudo_user: str) -> bool:
    uuid = ext_details["uuid"]
    numerical_id = ext_details.get("numerical_id")
    display_name = ext_details.get("name", ext_name)
    target_user_for_cmd = sudo_user if os.geteuid() == 0 and sudo_user else os.getlogin()

    print_info(f"Processing EGO extension '{display_name}' (UUID: {uuid})...")

    if not shutil.which("gnome-extensions"):
        print_error("'gnome-extensions' tool not available. Cannot manage this extension automatically.")
        _advise_manual_install(display_name, numerical_id)
        return False # Cannot proceed with this extension

    # First, try to enable it. It might already be installed (e.g. user-themes).
    if _enable_extension(uuid, display_name, target_user_for_cmd):
        return True # Already installed and now enabled

    # If enabling failed, it's likely not installed.
    # The `gnome-extensions install <UUID>` command usually installs from a local file.
    # True CLI installation from extensions.gnome.org is not standardly supported by `gnome-extensions` alone.
    # It requires either downloading the .zip manually or using a third-party installer script.
    # We will rely on the user using the "Extensions" app (org.gnome.Extensions) for these.
    print_warning(f"Extension '{display_name}' (UUID: {uuid}) could not be enabled (likely not installed).")
    _advise_manual_install(display_name, numerical_id)
    
    # We return True here because the *attempt* to process is done, and user is advised.
    # The overall phase success should depend on critical components, not every single optional extension.
    # However, if strictness is required, this could return False. For now, let's be lenient.
    return True # Consider this "processed with advice" rather than a hard failure for this specific extension.

def _advise_manual_install(display_name, numerical_id):
    print_info(f"Please install '{display_name}' (Extension ID: {numerical_id}) manually using the 'GNOME Extension Manager' application (installed from Flathub).")
    if numerical_id:
        print_info(f"You can find it on extensions.gnome.org: https://extensions.gnome.org/extension/{numerical_id}/")


def _run_gsettings_as_user(key: str, value: str, schema: str, sudo_user_for_cmd: str) -> bool:
    command_base = ["gsettings", "set", schema, key, value]
    
    if os.geteuid() == 0 and sudo_user_for_cmd:
        stdout, stderr, returncode = _run_command_as_user(command_base, sudo_user_for_cmd, capture_output=True, check=False)
    elif os.geteuid() == 0 and not sudo_user_for_cmd:
        print_warning(f"Running gsettings as 'root': gsettings set {schema} {key} {value}")
        stdout, stderr, returncode = run_command(command_base, capture_output=True, check=False)
    else:
        print_info(f"Executing for current user: gsettings set {schema} {key} {value}")
        stdout, stderr, returncode = run_command(command_base, capture_output=True, check=False)
    
    if returncode == 0:
        print_success(f"gsettings: Schema '{schema}', Key '{key}' set to '{value}'.")
        return True
    else:
        print_error(f"Failed to set gsettings: {schema} {key} to {value}. RC: {returncode}")
        if stdout and stdout.strip(): console.print(f"[dim]Stdout: {stdout.strip()}[/dim]")
        if stderr and stderr.strip(): console.print(f"[dim]Stderr: {stderr.strip()}[/dim]")
        return False

def run_gnome_configuration():
    print_header("Phase 4: GNOME Configuration") # Assuming this is Phase 4 from previous reorg
    phase_overall_success = True
    
    # Determine target user for GNOME settings
    # SUDO_USER is the user who invoked sudo. If not set (e.g. root logged in directly),
    # then operations might target root's GUI, which is usually not intended.
    target_gnome_user = os.environ.get('SUDO_USER')
    if os.geteuid() == 0 and not target_gnome_user: # Running as root, no SUDO_USER
        print_warning("Running as root without SUDO_USER. GNOME settings will target root's environment.")
        # Allow to proceed, but it's a warning. Could prompt user here.
    elif os.geteuid() != 0: # Running as a non-root user
        target_gnome_user = os.getlogin()
        print_info(f"Running as non-root user: {target_gnome_user}. GNOME changes will affect this user.")
    # If os.geteuid() == 0 and target_gnome_user IS set, we use target_gnome_user.

    # Step 4.1: Install GNOME Extension Manager (Flatpak)
    print_step("4.1", "Installing GNOME Extension Manager (Flatpak)")
    gnome_ext_manager_installed = False
    flatpak_path_stdout, _, flatpak_path_retcode = run_command(["which", "flatpak"], capture_output=True, check=False)
    if flatpak_path_retcode != 0 or not flatpak_path_stdout.strip():
        print_error("Flatpak command not found. Cannot install GNOME Extension Manager.")
        phase_overall_success = False
    else:
        print_info("Flatpak command found.")
        remotes_stdout, _, _ = run_command(["flatpak", "remotes", "--show-details"], capture_output=True, check=False)
        flathub_exists = remotes_stdout and "flathub" in remotes_stdout.lower()
        if not flathub_exists:
            print_warning("Flathub remote not found. Attempting to add it.")
            if run_command(["sudo", "flatpak", "remote-add", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"]):
                print_success("Flathub remote added successfully.")
                flathub_exists = True # Update status
            else:
                print_error("Failed to add Flathub remote. Cannot install GNOME Extension Manager.")
                phase_overall_success = False
        
        if flathub_exists:
            if run_command(["sudo", "flatpak", "install", "-y", "flathub", "com.mattjakeman.ExtensionManager"]): # Correct Flathub ID
                print_success("GNOME Extension Manager (com.mattjakeman.ExtensionManager) installed successfully from Flathub.")
                gnome_ext_manager_installed = True
            else:
                print_error("Failed to install GNOME Extension Manager from Flathub.")
                phase_overall_success = False
    
    # Step 4.2: Install gnome-tweaks
    print_step("4.2", "Installing GNOME Tweaks (for additional settings)")
    if run_command(["sudo", "dnf", "install", "-y", "gnome-tweaks"]):
        print_success("GNOME Tweaks installed successfully.")
    else:
        print_error("Failed to install GNOME Tweaks.")
        # phase_overall_success = False # Tweaks is useful but not as critical as Extension Manager

    # Step 4.3: Set GNOME theme to dark
    if target_gnome_user:
        print_step("4.3", "Setting GNOME Interface Style to 'prefer-dark'")
        if not _run_gsettings_as_user(key="color-scheme", value="prefer-dark", schema="org.gnome.desktop.interface", sudo_user_for_cmd=target_gnome_user):
            print_warning("Failed to set GNOME color scheme to 'prefer-dark' automatically.")
            # Not failing the whole phase for this.
    else:
        print_warning("Skipping dark theme setting as target user for GNOME is unclear (SUDO_USER not set and not running as non-root).")

    # Step 4.4: Install & Enable GNOME Shell Extensions
    if not target_gnome_user:
        print_warning("Skipping GNOME Shell extension installation/enabling as target user for GNOME is unclear.")
    elif not gnome_ext_manager_installed:
        print_warning("Skipping GNOME Shell extension installation/enabling as GNOME Extension Manager failed to install.")
        phase_overall_success = False # If manager isn't there, can't expect user to easily manage extensions
    else:
        print_step("4.4", "Processing GNOME Shell Extensions")
        if not _check_and_install_gnome_extensions_cli():
            print_warning("Issues with 'gnome-extensions' CLI tool. Some extensions might not be auto-enabled.")

        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        num_ext_success = 0
        num_ext_attempted = 0

        for ext_key, ext_details in EXTENSIONS_TO_INSTALL.items():
            num_ext_attempted += 1
            ext_type = ext_details.get("type")
            current_ext_processed_ok = False # True if processed without hard error, even if manual step advised

            if ext_type == "git":
                current_ext_processed_ok = _install_gnome_extension_from_git(ext_key, ext_details, target_gnome_user)
            elif ext_type == "ego":
                current_ext_processed_ok = _install_gnome_extension_from_ego(ext_key, ext_details, target_gnome_user)
            else:
                print_warning(f"Unknown extension type '{ext_type}' for '{ext_key}'. Skipping.")
            
            if current_ext_processed_ok: # This means it either succeeded OR user was advised for manual for EGO
                num_ext_success +=1
            else: # This means a hard failure in the processing logic itself (e.g. git clone failed)
                phase_overall_success = False # A failure in git install is more critical than "advise manual" for EGO.
        
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        
        if num_ext_attempted > 0:
            if num_ext_success == num_ext_attempted:
                print_success("All attempted GNOME Shell extensions processed.")
            else:
                print_warning(f"Some GNOME Shell extensions encountered issues during processing or require manual steps.")


    if phase_overall_success:
        print_success("GNOME Configuration phase completed.")
        print_info("A logout/login or reboot is recommended for all GNOME changes and extensions to take full effect.")
    else:
        print_error("GNOME Configuration phase encountered errors. Please review messages.")
    
    return phase_overall_success

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    run_gnome_configuration()