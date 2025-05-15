# scripts/gnome_configuration.py
import logging
import os
import pwd
import shutil
import tempfile
from pathlib import Path
import json

from scripts.myrich import (
    print_header, print_info, print_error, print_success, print_step, print_warning, console
)
from scripts.utils import run_command # Correctly imported

TEMP_DIR = Path(tempfile.gettempdir()) / "gnome_setup_temp"

EXTENSIONS_TO_INSTALL = {
    "user-themes": {
        "type": "ego", "uuid": "user-theme@gnome-shell-extensions.gcampax.github.com",
        "name": "User Themes", "numerical_id": "19"
    },
    "quick-settings-tweaks": {
        "type": "git", "url": "https://github.com/qwreey/quick-settings-tweaks.git",
        "install_script": "install.sh", "name": "Quick Settings Tweaks",
        "uuid_to_enable": "quick-settings-tweaks@qwreey"
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
    if not sudo_user:
        print_warning("Sudo user not provided to _get_user_env_vars; cannot determine specific user environment.")
        return env_vars
    try:
        user_info = pwd.getpwnam(sudo_user)
        user_uid = str(user_info.pw_uid)
        dbus_address = f"unix:path=/run/user/{user_uid}/bus"
        env_vars["DBUS_SESSION_BUS_ADDRESS"] = dbus_address
        env_vars["XDG_RUNTIME_DIR"] = f"/run/user/{user_uid}"
    except KeyError:
        print_warning(f"Could not get UID for user '{sudo_user}'. DBUS address might be incorrect.")
    except Exception as e:
        print_warning(f"Error determining environment for user '{sudo_user}': {e}")
    return env_vars

def _run_command_as_user(command: list[str], sudo_user: str, capture_output=False, check=True, text=True, cwd=None, env_extra=None):
    base_command = ["sudo", "-i", "-u", sudo_user]
    
    user_env = _get_user_env_vars(sudo_user)
    if env_extra:
        user_env.update(env_extra)

    env_prefix = []
    for k, v in user_env.items():
        env_prefix.append(f"{k}={v}")
    
    if env_prefix:
        full_command = base_command + ["env"] + env_prefix + command
    else:
        full_command = base_command + command
        
    # Logging of the effective command is handled by run_command in utils.py
    # No need to print_info here as utils.py does it.

    return run_command(full_command, capture_output=capture_output, check=check, text=text, cwd=cwd)

def _enable_extension(uuid: str, display_name: str, sudo_user_for_cmd: str) -> bool:
    if not shutil.which("gnome-extensions"):
        print_warning(f"'gnome-extensions' tool not found. Cannot enable '{display_name}'.")
        return False

    print_info(f"Attempting to enable '{display_name}' (UUID: {uuid}) for user '{sudo_user_for_cmd}'...")
    cmd_enable = ["gnome-extensions", "enable", uuid]
    
    stdout, stderr, rc = "", "", -1 # Initialize
    if os.geteuid() == 0 and sudo_user_for_cmd != os.getlogin() and sudo_user_for_cmd != 'root':
        stdout, stderr, rc = _run_command_as_user(cmd_enable, sudo_user_for_cmd, capture_output=True, check=False)
    else:
        stdout, stderr, rc = run_command(cmd_enable, capture_output=True, check=False)

    if rc == 0:
        print_success(f"Extension '{display_name}' enabled successfully for user '{sudo_user_for_cmd}'.")
        return True
    else:
        # Error/warning printed by run_command if it fails and check=True, or we print our own if check=False
        print_warning(f"Failed to enable extension '{display_name}' (UUID: {uuid}). RC: {rc}.")
        # utils.py's run_command already prints stdout/stderr if capture_output=True
        # if stdout and stdout.strip(): console.print(f"[dim]Stdout: {stdout.strip()}[/dim]")
        # if stderr and stderr.strip(): console.print(f"[dim]Stderr: {stderr.strip()}[/dim]")
        return False

def _get_gnome_shell_version(target_user_for_cmd: str) -> str | None:
    cmd = ["gnome-shell", "--version"]
    print_info(f"Attempting to get GNOME Shell version for user '{target_user_for_cmd}'...")

    stdout, stderr, rc = "", "", -1 # Initialize
    if os.geteuid() == 0 and target_user_for_cmd != os.getlogin() and target_user_for_cmd != 'root':
        stdout, stderr, rc = _run_command_as_user(cmd, target_user_for_cmd, capture_output=True, check=False)
    else:
        stdout, stderr, rc = run_command(cmd, capture_output=True, check=False)

    if rc == 0 and stdout and "GNOME Shell" in stdout:
        try:
            version_full = stdout.strip().split("GNOME Shell ")[1]
            print_success(f"GNOME Shell version found for user '{target_user_for_cmd}': {version_full}")
            return version_full
        except IndexError:
            print_warning(f"Could not parse GNOME Shell version from output: '{stdout.strip()}'")
            return None
    else:
        print_warning(f"Could not determine GNOME Shell version for user '{target_user_for_cmd}'. RC: {rc}")
        return None

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

    # run_command with check=True (default) returns bool
    if not run_command(["git", "clone", ext_details["url"], str(clone_dir)]):
        print_error(f"Failed to clone repository for '{ext_details['name']}'.") # run_command already prints error
        return False
    print_success(f"Repository for '{ext_details['name']}' cloned to {clone_dir}")

    install_script_path = clone_dir / ext_details["install_script"]
    if not install_script_path.is_file():
        print_error(f"Install script '{ext_details['install_script']}' not found for '{ext_details['name']}'.")
        return False
    
    # Use check=True for chmod, expect it to succeed.
    if not run_command(["chmod", "+x", str(install_script_path)], check=True):
        print_error(f"Failed to make install script executable: {install_script_path}")
        return False

    target_user_for_cmd = sudo_user if os.geteuid() == 0 and sudo_user else os.getlogin()
    print_info(f"Running install script: {install_script_path.name} for user '{target_user_for_cmd}'")
    
    script_executed_successfully = False
    # When check=False, must use capture_output=True to get rc from utils.run_command
    # to reliably check for success.
    script_stdout, script_stderr, script_rc = "", "", -1
    if os.geteuid() == 0 and target_user_for_cmd != os.getlogin() and target_user_for_cmd != 'root':
        script_stdout, script_stderr, script_rc = _run_command_as_user(
            [str(install_script_path)], target_user_for_cmd, 
            cwd=str(clone_dir), check=False, capture_output=True
        )
    else:
        script_stdout, script_stderr, script_rc = run_command(
            [str(install_script_path)], 
            cwd=str(clone_dir), check=False, capture_output=True
        )
    script_executed_successfully = (script_rc == 0)

    if not script_executed_successfully:
        print_error(f"Install script for '{ext_details['name']}' failed. RC: {script_rc}")
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
    # run_command with check=True (default) returns bool
    if run_command(["sudo", dnf_cmd, "install", "-y", "gnome-shell-extensions"]):
        print_success("'gnome-shell-extensions' installed. This should provide 'gnome-extensions' CLI.")
        if shutil.which("gnome-extensions"):
            return True
        else:
            print_error("'gnome-extensions' CLI still not found after attempting install.")
            return False
    else:
        # run_command already prints error if dnf install fails
        print_error("Failed to install 'gnome-shell-extensions'.")
        return False

def _install_gnome_extension_from_ego(ext_name: str, ext_details: dict, sudo_user: str) -> bool:
    uuid = ext_details["uuid"]
    numerical_id = ext_details.get("numerical_id")
    display_name = ext_details.get("name", ext_name)
    
    target_user_for_cmd = sudo_user if os.geteuid() == 0 and sudo_user else os.getlogin()

    print_info(f"Processing EGO extension '{display_name}' (UUID: {uuid}) for user '{target_user_for_cmd}'.")

    if not shutil.which("gnome-extensions"):
        print_error("'gnome-extensions' tool not available. Cannot manage this extension automatically.")
        _advise_manual_install(display_name, numerical_id)
        return False 

    if _enable_extension(uuid, display_name, target_user_for_cmd):
        return True

    print_info(f"Extension '{display_name}' not enabled or not installed. Attempting automated download and installation...")

    if not shutil.which("curl"):
        print_warning("'curl' command not found. Cannot download EGO extension automatically.")
        _advise_manual_install(display_name, numerical_id)
        return True 

    shell_version_full = _get_gnome_shell_version(target_user_for_cmd)
    if not shell_version_full:
        print_warning(f"Could not get GNOME Shell version for user '{target_user_for_cmd}'. Unable to find compatible extension version from EGO.")
        _advise_manual_install(display_name, numerical_id)
        return True

    shell_version_major = shell_version_full.split('.')[0] 

    api_url = f"https://extensions.gnome.org/extension-info/?uuid={uuid}&shell_version={shell_version_major}"
    print_info(f"Fetching extension data from EGO API: {api_url}")
    
    # Use check=False, capture_output=True for curl API call
    api_stdout, api_stderr, api_rc = run_command(["curl", "-s", "-L", api_url], capture_output=True, check=False, text=True)

    if api_rc != 0 or not api_stdout:
        print_error(f"Failed to fetch extension data for '{display_name}' from EGO. curl RC: {api_rc}")
        _advise_manual_install(display_name, numerical_id)
        return True

    try:
        ext_info = json.loads(api_stdout)
        download_url_path = ext_info.get("download_url")
        if not download_url_path:
            print_warning(f"No download URL found in EGO API response for '{display_name}' (Shell {shell_version_major}). It might not be compatible.")
            _advise_manual_install(display_name, numerical_id)
            return True
    except json.JSONDecodeError:
        print_error(f"Failed to parse JSON response from EGO for '{display_name}'.")
        _advise_manual_install(display_name, numerical_id)
        return True

    full_download_url = f"https://extensions.gnome.org{download_url_path}"
    zip_file_path_str = "" # Initialize
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip", dir=str(TEMP_DIR)) as tmp_zip_file_obj:
            zip_file_path_str = tmp_zip_file_obj.name
        
        print_info(f"Downloading '{display_name}' from {full_download_url} to {zip_file_path_str}")
        # Use check=False, capture_output=True for curl download
        dl_stdout, dl_stderr, dl_rc = run_command(["curl", "-L", "-o", zip_file_path_str, full_download_url], capture_output=True, check=False)

        if dl_rc != 0:
            print_error(f"Failed to download '{display_name}'. curl RC: {dl_rc}")
            _advise_manual_install(display_name, numerical_id)
            return True 
        
        print_success(f"'{display_name}' downloaded to {zip_file_path_str}")

        print_info(f"Installing '{display_name}' from {zip_file_path_str} for user '{target_user_for_cmd}'...")
        install_cmd = ["gnome-extensions", "install", "--force", zip_file_path_str] # Added --force
        
        install_stdout, install_stderr, install_rc = "", "", -1
        # Use check=False, capture_output=True for gnome-extensions install
        if os.geteuid() == 0 and target_user_for_cmd != os.getlogin() and target_user_for_cmd != 'root':
            install_stdout, install_stderr, install_rc = _run_command_as_user(install_cmd, target_user_for_cmd, capture_output=True, check=False)
        else:
            install_stdout, install_stderr, install_rc = run_command(install_cmd, capture_output=True, check=False)

        if install_rc == 0:
            print_success(f"Extension '{display_name}' installed via gnome-extensions tool.")
        # gnome-extensions install with --force might not give "already installed" in stderr in the same way,
        # but successful overwriting/installing will have rc == 0.
        # If it's truly already there and perfect, enabling it first would have caught it.
        else:
            print_warning(f"Failed to install '{display_name}' using gnome-extensions. RC: {install_rc}")
            _advise_manual_install(display_name, numerical_id)
            return True 
    finally:
        if zip_file_path_str and Path(zip_file_path_str).exists():
            os.remove(zip_file_path_str)

    if _enable_extension(uuid, display_name, target_user_for_cmd):
        return True
    else:
        print_warning(f"Extension '{display_name}' installed but could not be enabled. Try enabling manually or restart GNOME Shell.")
        _advise_manual_install(display_name, numerical_id)
        return True


def _advise_manual_install(display_name, numerical_id):
    print_info(f"Please install or enable '{display_name}' manually.")
    print_info("You can use the 'GNOME Extension Manager' application (if installed) or the 'Extensions' application.")
    if numerical_id:
        print_info(f"Find on EGO: https://extensions.gnome.org/extension/{numerical_id}/")


def _run_gsettings_as_user(key: str, value: str, schema: str, sudo_user_for_cmd: str) -> bool:
    command_base = ["gsettings", "set", schema, key, value]
    
    stdout, stderr, returncode = "", "", -1
    # Use check=False, capture_output=True for gsettings
    if os.geteuid() == 0 and sudo_user_for_cmd != os.getlogin() and sudo_user_for_cmd != 'root':
        stdout, stderr, returncode = _run_command_as_user(command_base, sudo_user_for_cmd, capture_output=True, check=False)
    else:
        stdout, stderr, returncode = run_command(command_base, capture_output=True, check=False)
    
    if returncode == 0:
        print_success(f"gsettings: User '{sudo_user_for_cmd}', Schema '{schema}', Key '{key}' set to '{value}'.")
        return True
    else:
        print_error(f"Failed to set gsettings for user '{sudo_user_for_cmd}': {schema} {key} to {value}. RC: {returncode}")
        return False

def run_gnome_configuration():
    print_header("Phase 4: GNOME Configuration")
    phase_overall_success = True
    
    target_gnome_user = os.environ.get('SUDO_USER')
    current_login_user = os.getlogin()

    if os.geteuid() == 0: 
        if not target_gnome_user: 
            print_warning("Running as root without SUDO_USER. GNOME settings will target root's environment.")
            target_gnome_user = 'root' 
    else: 
        target_gnome_user = current_login_user
        print_info(f"Running as non-root user: {target_gnome_user}. GNOME changes will affect this user.")

    print_info(f"Target user for GNOME configurations: {target_gnome_user}")

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    print_step("4.1", "Installing GNOME Extension Manager (Flatpak)")
    # Check for flatpak with check=False, capture_output=True
    flatpak_stdout, flatpak_stderr, flatpak_rc = run_command(["which", "flatpak"], capture_output=True, check=False)
    if flatpak_rc != 0:
        print_error("Flatpak command not found. Cannot install GNOME Extension Manager.")
    else:
        print_info("Flatpak command found.")
        # Check remotes with check=False, capture_output=True
        remotes_stdout, remotes_stderr, remotes_rc = run_command(["flatpak", "remotes", "--show-details"], capture_output=True, check=False)
        flathub_exists = remotes_rc == 0 and remotes_stdout and "flathub" in remotes_stdout.lower()
        
        if not flathub_exists:
            print_warning("Flathub remote not found. Attempting to add it system-wide.")
            # Add remote with check=True (default), returns bool
            if run_command(["sudo", "flatpak", "remote-add", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"]):
                print_success("Flathub remote added successfully.")
            else:
                print_error("Failed to add Flathub remote.") # run_command already prints details
        
        # Re-check after attempting to add
        remotes_stdout, remotes_stderr, remotes_rc = run_command(["flatpak", "remotes", "--show-details"], capture_output=True, check=False)
        flathub_exists = remotes_rc == 0 and remotes_stdout and "flathub" in remotes_stdout.lower()

        if flathub_exists:
            # Install flatpak with check=True (default), returns bool
            if run_command(["sudo", "flatpak", "install", "-y", "flathub", "com.mattjakeman.ExtensionManager"]):
                print_success("GNOME Extension Manager (com.mattjakeman.ExtensionManager) installed/verified from Flathub.")
            else:
                print_error("Failed to install/verify GNOME Extension Manager from Flathub.")
        else:
            print_error("Flathub remote not available. Cannot install GNOME Extension Manager.")
    
    print_step("4.2", "Installing GNOME Tweaks (for additional settings)")
    # Install package with check=True (default), returns bool
    if run_command(["sudo", "dnf", "install", "-y", "gnome-tweaks"]):
        print_success("GNOME Tweaks installed successfully.")
    else:
        print_error("Failed to install GNOME Tweaks.")

    print_step("4.3", f"Setting GNOME Interface Style to 'prefer-dark' for user '{target_gnome_user}'")
    if not _run_gsettings_as_user(key="color-scheme", value="'prefer-dark'", schema="org.gnome.desktop.interface", sudo_user_for_cmd=target_gnome_user):
        print_warning(f"Failed to set GNOME color scheme to 'prefer-dark' for user '{target_gnome_user}'.")

    print_step("4.4", f"Processing GNOME Shell Extensions for user '{target_gnome_user}'")
    
    if not _check_and_install_gnome_extensions_cli():
        print_warning("Issues with 'gnome-extensions' CLI tool setup. Some extensions might not be auto-installed/enabled.")

    num_ext_success = 0
    num_ext_attempted = 0
    for ext_key, ext_details in EXTENSIONS_TO_INSTALL.items():
        num_ext_attempted += 1
        ext_type = ext_details.get("type")
        current_ext_processed_ok = False 

        if ext_type == "git":
            current_ext_processed_ok = _install_gnome_extension_from_git(ext_key, ext_details, target_gnome_user)
        elif ext_type == "ego":
            current_ext_processed_ok = _install_gnome_extension_from_ego(ext_key, ext_details, target_gnome_user)
        else:
            print_warning(f"Unknown extension type '{ext_type}' for '{ext_key}'. Skipping.")
        
        if current_ext_processed_ok:
            num_ext_success +=1
        else: 
            phase_overall_success = False 
    
    # Cleanup TEMP_DIR contents if necessary, but usually OS handles /tmp
    # if TEMP_DIR.exists():
    #     shutil.rmtree(TEMP_DIR) # Careful if other processes might use this named temp dir

    if num_ext_attempted > 0:
        if num_ext_success == num_ext_attempted:
            print_success("All attempted GNOME Shell extensions processed (either successfully or with manual fallback advice).")
        else:
            print_warning(f"{num_ext_attempted - num_ext_success} GNOME Shell extensions encountered hard errors during processing.")

    if phase_overall_success:
        print_success("GNOME Configuration phase completed.")
    else:
        print_error("GNOME Configuration phase encountered one or more errors. Please review messages.")
    
    print_info("A logout/login or system reboot is often recommended for all GNOME changes and extensions to take full effect.")
    return phase_overall_success
