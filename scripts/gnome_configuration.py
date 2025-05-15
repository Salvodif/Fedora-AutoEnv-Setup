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

# EXTENSIONS_TO_INSTALL is now passed via config parameter

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
        
    return run_command(full_command, capture_output=capture_output, check=check, text=text, cwd=cwd)

def _enable_extension(uuid: str, display_name: str, sudo_user_for_cmd: str) -> bool:
    if not shutil.which("gnome-extensions"):
        print_warning(f"'gnome-extensions' tool not found. Cannot enable '{display_name}'.")
        return False

    print_info(f"Attempting to enable '{display_name}' (UUID: {uuid}) for user '{sudo_user_for_cmd}'...")
    cmd_enable = ["gnome-extensions", "enable", uuid]
    
    stdout, stderr, rc = "", "", -1 
    if os.geteuid() == 0 and sudo_user_for_cmd != os.getlogin() and sudo_user_for_cmd != 'root':
        stdout, stderr, rc = _run_command_as_user(cmd_enable, sudo_user_for_cmd, capture_output=True, check=False)
    else:
        stdout, stderr, rc = run_command(cmd_enable, capture_output=True, check=False)

    if rc == 0:
        print_success(f"Extension '{display_name}' enabled successfully for user '{sudo_user_for_cmd}'.")
        return True
    else:
        print_warning(f"Failed to enable extension '{display_name}' (UUID: {uuid}). RC: {rc}.")
        # if stdout and stdout.strip(): console.print(f"[dim]Stdout: {stdout.strip()}[/dim]")
        # if stderr and stderr.strip(): console.print(f"[dim]Stderr: {stderr.strip()}[/dim]")
        return False

def _get_gnome_shell_version(target_user_for_cmd: str) -> str | None:
    cmd = ["gnome-shell", "--version"]
    print_info(f"Attempting to get GNOME Shell version for user '{target_user_for_cmd}'...")

    stdout, stderr, rc = "", "", -1 
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
        # if stdout and stdout.strip(): console.print(f"[dim]Stdout: {stdout.strip()}[/dim]")
        # if stderr and stderr.strip(): console.print(f"[dim]Stderr: {stderr.strip()}[/dim]")
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

    if not run_command(["git", "clone", ext_details["url"], str(clone_dir)]):
        print_error(f"Failed to clone repository for '{ext_details['name']}'.")
        return False
    print_success(f"Repository for '{ext_details['name']}' cloned to {clone_dir}")

    install_script_path = clone_dir / ext_details["install_script"]
    if not install_script_path.is_file():
        print_error(f"Install script '{ext_details['install_script']}' not found for '{ext_details['name']}'.")
        return False
    
    if not run_command(["chmod", "+x", str(install_script_path)], check=True):
        print_error(f"Failed to make install script executable: {install_script_path}")
        return False

    target_user_for_cmd = sudo_user if os.geteuid() == 0 and sudo_user else os.getlogin()
    print_info(f"Running install script: {install_script_path.name} for user '{target_user_for_cmd}'")
    
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
        # if script_stdout and script_stdout.strip(): console.print(f"[dim]Stdout: {script_stdout.strip()}[/dim]")
        # if script_stderr and script_stderr.strip(): console.print(f"[dim]Stderr: {script_stderr.strip()}[/dim]")
        return False
    print_success(f"Install script for '{ext_details['name']}' executed.")
    
    uuid_to_enable = ext_details.get("uuid_to_enable")
    if uuid_to_enable:
        return _enable_extension(uuid_to_enable, ext_details['name'], target_user_for_cmd)
    return True


def _check_and_install_gnome_extensions_cli(dnf_packages_config: list):
    """
    Checks for 'gnome-extensions' CLI tool and attempts to install 'gnome-shell-extensions'
    if not found and if 'gnome-shell-extensions' is in the provided DNF package list.
    """
    if shutil.which("gnome-extensions"):
        print_info("'gnome-extensions' command-line tool found.")
        return True
    
    cli_tool_package = "gnome-shell-extensions" 
    if cli_tool_package not in dnf_packages_config:
        print_warning(f"'{cli_tool_package}' package (which provides 'gnome-extensions' CLI) is not specified in the DNF configuration for this phase.")
        print_warning("Cannot automatically install 'gnome-extensions' CLI tool. Manual installation may be required if extensions fail.")
        return False 

    print_warning(f"'gnome-extensions' tool not found. Attempting to install '{cli_tool_package}' as per DNF configuration...")
    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
    
    if run_command(["sudo", dnf_cmd, "install", "-y", cli_tool_package]):
        print_success(f"'{cli_tool_package}' installed. This should provide 'gnome-extensions' CLI.")
        if shutil.which("gnome-extensions"): # Verify again
            return True
        else:
            print_error("'gnome-extensions' CLI still not found after attempting install.")
            return False
    else:
        print_error(f"Failed to install '{cli_tool_package}'.")
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
        return False # Changed: If tool not available, this is a failure to automate for this ext.

    # Attempt to enable first, it might already be installed
    if _enable_extension(uuid, display_name, target_user_for_cmd):
        return True # Already installed and enabled

    print_info(f"Extension '{display_name}' not enabled or not installed. Attempting automated download and installation...")

    if not shutil.which("curl"):
        print_warning("'curl' command not found. Cannot download EGO extension automatically.")
        _advise_manual_install(display_name, numerical_id)
        return True # Return True as we advised manual, not a hard error for the process itself.

    shell_version_full = _get_gnome_shell_version(target_user_for_cmd)
    if not shell_version_full:
        print_warning(f"Could not get GNOME Shell version for user '{target_user_for_cmd}'. Unable to find compatible extension version from EGO.")
        _advise_manual_install(display_name, numerical_id)
        return True

    shell_version_major = shell_version_full.split('.')[0] 

    api_url = f"https://extensions.gnome.org/extension-info/?uuid={uuid}&shell_version={shell_version_major}"
    print_info(f"Fetching extension data from EGO API: {api_url}")
    
    api_stdout, api_stderr, api_rc = run_command(["curl", "-s", "-L", api_url], capture_output=True, check=False, text=True)

    if api_rc != 0 or not api_stdout:
        print_error(f"Failed to fetch extension data for '{display_name}' from EGO. curl RC: {api_rc}")
        # if api_stdout and api_stdout.strip(): console.print(f"[dim]API Stdout: {api_stdout.strip()}[/dim]")
        # if api_stderr and api_stderr.strip(): console.print(f"[dim]API Stderr: {api_stderr.strip()}[/dim]")
        _advise_manual_install(display_name, numerical_id)
        return True

    try:
        ext_info = json.loads(api_stdout)
        download_url_path = ext_info.get("download_url")
        if not download_url_path:
            print_warning(f"No download URL found in EGO API response for '{display_name}' (Shell {shell_version_major}). It might not be compatible or exist for this version.")
            _advise_manual_install(display_name, numerical_id)
            return True
    except json.JSONDecodeError:
        print_error(f"Failed to parse JSON response from EGO for '{display_name}'. Response: {api_stdout[:200]}...")
        _advise_manual_install(display_name, numerical_id)
        return True

    full_download_url = f"https://extensions.gnome.org{download_url_path}"
    zip_file_path_str = "" 
    try:
        # Ensure TEMP_DIR exists (it should from the main run_gnome_configuration function)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip", dir=str(TEMP_DIR)) as tmp_zip_file_obj:
            zip_file_path_str = tmp_zip_file_obj.name
        
        print_info(f"Downloading '{display_name}' from {full_download_url} to {zip_file_path_str}")
        dl_stdout, dl_stderr, dl_rc = run_command(["curl", "-L", "-o", zip_file_path_str, full_download_url], capture_output=True, check=False)

        if dl_rc != 0:
            print_error(f"Failed to download '{display_name}'. curl RC: {dl_rc}")
            # if dl_stdout and dl_stdout.strip(): console.print(f"[dim]DL Stdout: {dl_stdout.strip()}[/dim]")
            # if dl_stderr and dl_stderr.strip(): console.print(f"[dim]DL Stderr: {dl_stderr.strip()}[/dim]")
            _advise_manual_install(display_name, numerical_id)
            return True 
        
        print_success(f"'{display_name}' downloaded to {zip_file_path_str}")

        print_info(f"Installing '{display_name}' from {zip_file_path_str} for user '{target_user_for_cmd}'...")
        # --force is important to overwrite if a previous attempt left a partial install
        install_cmd = ["gnome-extensions", "install", "--force", zip_file_path_str] 
        
        install_stdout, install_stderr, install_rc = "", "", -1
        if os.geteuid() == 0 and target_user_for_cmd != os.getlogin() and target_user_for_cmd != 'root':
            install_stdout, install_stderr, install_rc = _run_command_as_user(install_cmd, target_user_for_cmd, capture_output=True, check=False)
        else:
            install_stdout, install_stderr, install_rc = run_command(install_cmd, capture_output=True, check=False)

        if install_rc == 0:
            print_success(f"Extension '{display_name}' installed via gnome-extensions tool.")
        else:
            print_warning(f"Failed to install '{display_name}' using gnome-extensions. RC: {install_rc}")
            # if install_stdout and install_stdout.strip(): console.print(f"[dim]Install Stdout: {install_stdout.strip()}[/dim]")
            # if install_stderr and install_stderr.strip(): console.print(f"[dim]Install Stderr: {install_stderr.strip()}[/dim]")
            _advise_manual_install(display_name, numerical_id)
            return True # Advised manual, so not a hard failure for this function's contract
    finally:
        if zip_file_path_str and Path(zip_file_path_str).exists():
            try:
                os.remove(zip_file_path_str)
            except OSError as e_rm:
                print_warning(f"Could not remove temporary zip file {zip_file_path_str}: {e_rm}")

    # After successful install, try to enable it again
    if _enable_extension(uuid, display_name, target_user_for_cmd):
        return True
    else:
        print_warning(f"Extension '{display_name}' installed but could not be enabled. Try enabling manually or restart GNOME Shell.")
        _advise_manual_install(display_name, numerical_id) # Advise manual enable
        return True # Considered True as install happened, enable is separate concern for user.


def _advise_manual_install(display_name, numerical_id):
    print_info(f"Please try to install or enable '{display_name}' manually.")
    print_info("You can use the 'GNOME Extension Manager' application (if installed) or the 'Extensions' application from GNOME Tweaks/Software.")
    if numerical_id:
        print_info(f"Find on EGO: https://extensions.gnome.org/extension/{numerical_id}/ (numerical ID: {numerical_id})")


def _run_gsettings_as_user(key: str, value: str, schema: str, sudo_user_for_cmd: str) -> bool:
    command_base = ["gsettings", "set", schema, key, value]
    
    stdout, stderr, returncode = "", "", -1
    if os.geteuid() == 0 and sudo_user_for_cmd != os.getlogin() and sudo_user_for_cmd != 'root':
        stdout, stderr, returncode = _run_command_as_user(command_base, sudo_user_for_cmd, capture_output=True, check=False)
    else:
        stdout, stderr, returncode = run_command(command_base, capture_output=True, check=False)
    
    if returncode == 0:
        print_success(f"gsettings: User '{sudo_user_for_cmd}', Schema '{schema}', Key '{key}' set to '{value}'.")
        return True
    else:
        print_error(f"Failed to set gsettings for user '{sudo_user_for_cmd}': {schema} {key} to {value}. RC: {returncode}")
        # if stdout and stdout.strip(): console.print(f"[dim]gsettings Stdout: {stdout.strip()}[/dim]")
        # if stderr and stderr.strip(): console.print(f"[dim]gsettings Stderr: {stderr.strip()}[/dim]")
        return False

def run_gnome_configuration(config: dict):
    print_header("Phase 4: GNOME Configuration")
    phase_overall_success = True # Assume success, set to False on critical errors
    
    # Get package lists and extension details from the passed config
    dnf_packages_for_gnome = config.get('dnf_packages', [])
    flatpak_apps_for_gnome = config.get('flatpak_apps', {})
    extensions_to_install = config.get('gnome_extensions', {})

    # Determine target user for GNOME settings
    target_gnome_user = os.environ.get('SUDO_USER')
    current_login_user = os.getlogin()

    if os.geteuid() == 0: # Running as root
        if not target_gnome_user: 
            print_warning("Running as root without SUDO_USER. GNOME settings will target root's environment, which is usually not intended.")
            target_gnome_user = 'root' # Explicitly set for clarity, though gsettings might default to this anyway.
    else: # Running as a non-root user
        target_gnome_user = current_login_user
        print_info(f"Running as non-root user: {target_gnome_user}. GNOME changes will affect this user.")

    print_info(f"Target user for GNOME configurations: {target_gnome_user}")

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # --- Step 4.1: Install GNOME Extension Manager (Flatpak) ---
    extension_manager_app_id = "com.mattjakeman.ExtensionManager" # Key from YAML
    extension_manager_friendly_name = flatpak_apps_for_gnome.get(extension_manager_app_id)

    if extension_manager_friendly_name:
        print_step("4.1", f"Installing {extension_manager_friendly_name} (Flatpak)")
        flatpak_stdout, flatpak_stderr, flatpak_rc = run_command(["which", "flatpak"], capture_output=True, check=False)
        if flatpak_rc != 0:
            print_error("Flatpak command not found. Cannot install GNOME Extension Manager.")
            phase_overall_success = False # This is a prerequisite for easy extension management
        else:
            print_info("Flatpak command found.")
            remotes_stdout, remotes_stderr, remotes_rc = run_command(["flatpak", "remotes", "--system", "--show-details"], capture_output=True, check=False)
            flathub_exists = remotes_rc == 0 and remotes_stdout and "flathub" in remotes_stdout.lower()
            
            if not flathub_exists:
                print_warning("Flathub remote not found. Attempting to add it system-wide.")
                # Flatpak remote-add requires sudo
                if run_command(["sudo", "flatpak", "remote-add", "--system", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"]):
                    print_success("Flathub remote added successfully to system.")
                    flathub_exists = True # Update status
                else:
                    print_error("Failed to add Flathub remote system-wide.")
                    phase_overall_success = False # Cannot install from Flathub if remote add fails
            
            if flathub_exists:
                # Flatpak install also requires sudo for system install
                if run_command(["sudo", "flatpak", "install", "--system", "-y", "flathub", extension_manager_app_id]):
                    print_success(f"{extension_manager_friendly_name} installed/verified from Flathub.")
                else:
                    print_error(f"Failed to install/verify {extension_manager_friendly_name} from Flathub.")
                    # Not necessarily failing phase_overall_success, as other methods might work
            else: # If Flathub is still not available
                print_error(f"Flathub remote not available. Cannot install {extension_manager_friendly_name}.")
                phase_overall_success = False
    else:
        print_info("GNOME Extension Manager (com.mattjakeman.ExtensionManager) not specified in Flatpak configuration for this phase. Skipping its installation.")
    
    console.rule()

    # --- Step 4.2: Install GNOME Tweaks (DNF) ---
    gnome_tweaks_package = "gnome-tweaks" # Key from YAML
    if gnome_tweaks_package in dnf_packages_for_gnome:
        print_step("4.2", "Installing GNOME Tweaks (for additional settings)")
        dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
        # DNF install requires sudo
        if run_command(["sudo", dnf_cmd, "install", "-y", gnome_tweaks_package]):
            print_success("GNOME Tweaks installed successfully.")
        else:
            print_error("Failed to install GNOME Tweaks.")
            # Not necessarily failing phase_overall_success, as it's a helper tool
    else:
        print_info("GNOME Tweaks not specified in DNF configuration for this phase. Skipping its installation.")

    console.rule()

    # --- Step 4.3: Set GNOME Interface Style to 'prefer-dark' ---
    print_step("4.3", f"Setting GNOME Interface Style to 'prefer-dark' for user '{target_gnome_user}'")
    if not _run_gsettings_as_user(key="color-scheme", value="'prefer-dark'", schema="org.gnome.desktop.interface", sudo_user_for_cmd=target_gnome_user):
        print_warning(f"Failed to set GNOME color scheme to 'prefer-dark' for user '{target_gnome_user}'. This is a non-critical issue.")
        # Not failing phase_overall_success for this

    console.rule()

    # --- Step 4.4: Process GNOME Shell Extensions ---
    print_step("4.4", f"Processing GNOME Shell Extensions for user '{target_gnome_user}'")
    
    # Check/install 'gnome-extensions' CLI tool first, using the DNF package list from config
    if not _check_and_install_gnome_extensions_cli(dnf_packages_for_gnome):
        print_warning("Issues with 'gnome-extensions' CLI tool setup. Automatic extension installation/enablement might fail.")
        # Not setting phase_overall_success = False here, as manual advice is given per extension.

    num_ext_success = 0
    num_ext_attempted = 0

    if not extensions_to_install:
        print_info("No GNOME Shell extensions specified in the configuration for this phase.")
    else:
        for ext_key, ext_details in extensions_to_install.items():
            num_ext_attempted += 1
            ext_type = ext_details.get("type")
            ext_name_friendly = ext_details.get("name", ext_key) # Use friendly name
            current_ext_processed_ok = False 

            console.print(f"\n[cyan]Processing extension: {ext_name_friendly}[/cyan]")
            if ext_type == "git":
                current_ext_processed_ok = _install_gnome_extension_from_git(ext_key, ext_details, target_gnome_user)
            elif ext_type == "ego":
                current_ext_processed_ok = _install_gnome_extension_from_ego(ext_key, ext_details, target_gnome_user)
            else:
                print_warning(f"Unknown extension type '{ext_type}' for '{ext_name_friendly}'. Skipping.")
            
            if current_ext_processed_ok:
                num_ext_success +=1
            else: 
                # _install_..._from_ego often returns True even if it advises manual install.
                # A False return from those usually means a more direct failure of the automation attempt.
                print_warning(f"Automated processing of '{ext_name_friendly}' encountered an issue or advised manual steps.")
                # Don't set phase_overall_success = False here, as individual extensions are often optional
                # and manual fallbacks are provided.
    
    if num_ext_attempted > 0:
        if num_ext_success == num_ext_attempted:
            print_success(f"All {num_ext_attempted} attempted GNOME Shell extensions processed successfully through automation.")
        else:
            # This count might be misleading if _install_..._from_ego returns True on "advise manual".
            # A more accurate message would be based on how many returned False.
            print_warning(f"Processed {num_ext_attempted} GNOME Shell extensions. {num_ext_success} reported success from automation. Some may require manual attention (see logs/output).")

    console.rule()
    # Cleanup TEMP_DIR for EGO downloads
    if TEMP_DIR.exists():
        try:
            shutil.rmtree(TEMP_DIR)
            print_info(f"Cleaned up temporary directory: {TEMP_DIR}")
        except Exception as e_rmtree:
            print_warning(f"Could not fully clean up temporary directory {TEMP_DIR}: {e_rmtree}")


    if phase_overall_success:
        print_success("GNOME Configuration phase completed. Review messages for any items requiring manual attention.")
    else:
        print_error("GNOME Configuration phase encountered one or more critical errors. Please review messages.")
    
    print_info("A logout/login or system reboot is often recommended for all GNOME changes and extensions to take full effect.")
    return phase_overall_success

if __name__ == '__main__':
    # Example for testing (requires a dummy config or manual setup of it)
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s')
    console.print("[yellow]Running gnome_configuration.py directly for testing.[/yellow]")
    
    # Mock configuration for testing
    mock_config_gnome = {
        "dnf_packages": ["gnome-tweaks", "gnome-shell-extensions"],
        "flatpak_apps": {
            "com.mattjakeman.ExtensionManager": "GNOME Extension Manager"
        },
        "gnome_extensions": {
            # "user-themes": { # Keep this commented for faster testing unless you need it
            #     "type": "ego", "uuid": "user-theme@gnome-shell-extensions.gcampax.github.com",
            #     "name": "User Themes", "numerical_id": "19"
            # },
            "just-perfection": {
                 "type": "ego", "uuid": "just-perfection-desktop@just-perfection",
                 "numerical_id": "3843", "name": "Just Perfection"
            }
            # Add a git extension if you have one to test, e.g., quick-settings-tweaks
        }
    }
    if os.geteuid() != 0:
        print_error("This test script part requires sudo for DNF/Flatpak installs if they are not present.")
        print_info("If packages/tools are already installed, some parts might run without sudo.")
        # sys.exit("Run with sudo for full test.") # Uncomment if you want to enforce sudo for testing

    if run_gnome_configuration(mock_config_gnome):
        print_success("GNOME configuration test script finished successfully.")
    else:
        print_error("GNOME configuration test script finished with errors.")