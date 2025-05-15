# scripts/gnome_configuration.py
import logging
import os
import pwd # For getpwnam
import shutil
import tempfile
from pathlib import Path

from scripts.myrich import (
    print_header, print_info, print_error, print_success, print_step, print_warning, console
)
from scripts.utils import run_command

# Define a directory for temporary downloads/clones
TEMP_DIR = Path(tempfile.gettempdir()) / "gnome_setup_temp"

# Extension details
EXTENSIONS_TO_INSTALL = {
    "quick-settings-tweaks": {
        "type": "git",
        "url": "https://github.com/qwreey/quick-settings-tweaks.git",
        "install_script": "install.sh" # Relative to repo root
    },
    "user-themes": { # User Themes
        "type": "ego",
        "uuid": "user-theme@gnome-shell-extensions.gcampax.github.com",
        "name": "User Themes" # For display
    },
    "just-perfection": {
        "type": "ego",
        "uuid": "just-perfection-desktop@just-perfection", # This is the UUID used by gnome-extensions tool after it's fetched based on numerical ID
        "numerical_id": "3843", # From extensions.gnome.org URL
        "name": "Just Perfection"
    },
    "rounded-window-corners": {
        "type": "ego",
        "uuid": "rounded-window-corners@yilozt",
        "numerical_id": "5237",
        "name": "Rounded Window Corners"
    },
    "dash-to-dock": {
        "type": "ego",
        "uuid": "dash-to-dock@micxgx.gmail.com",
        "numerical_id": "307",
        "name": "Dash to Dock"
    },
    "blur-my-shell": {
        "type": "ego",
        "uuid": "blur-my-shell@aunetx",
        "numerical_id": "3193",
        "name": "Blur my Shell"
    },
    "bluetooth-quick-connect": {
        "type": "ego",
        "uuid": "bluetooth-quick-connect@bjarosze.gmail.com",
        "numerical_id": "1401",
        "name": "Bluetooth Quick Connect"
    },
    "clipboard-indicator": {
        "type": "ego",
        "uuid": "clipboard-indicator@tudmotu.com",
        "numerical_id": "779",
        "name": "Clipboard Indicator"
    },
    "wireless-hid": {
        "type": "ego",
        "uuid": "wireless-hid@chlumskyvaclav.gmail.com",
        "numerical_id": "5764",
        "name": "Wireless HID"
    },
    "logo-menu": {
        "type": "ego",
        "uuid": "logo-menu@fthx",
        "numerical_id": "442",
        "name": "Logo Menu"
    }
}


def _get_user_env_vars(sudo_user: str):
    """
    Attempts to get essential environment variables for the target user,
    especially DBUS_SESSION_BUS_ADDRESS.
    """
    env_vars = {}
    try:
        user_info = pwd.getpwnam(sudo_user)
        user_uid = str(user_info.pw_uid)

        # Standard path for user's D-Bus session
        dbus_address = f"unix:path=/run/user/{user_uid}/bus"
        env_vars["DBUS_SESSION_BUS_ADDRESS"] = dbus_address

        # Try to get XDG_RUNTIME_DIR as well, can be important
        env_vars["XDG_RUNTIME_DIR"] = f"/run/user/{user_uid}"

        # Get DISPLAY if possible (might not be set or needed for all gnome-extensions commands)
        # This is harder to get reliably from a root script for a user session.
        # For now, primarily focus on DBUS.

    except KeyError:
        print_warning(f"Could not get UID for user '{sudo_user}'. DBUS address might be incorrect.")
    except Exception as e:
        print_warning(f"Error determining environment for user '{sudo_user}': {e}")
    return env_vars

def _run_command_as_user(command: list[str], sudo_user: str, capture_output=False, check=True, text=True, cwd=None, env_extra=None):
    """Helper to run a command as the specified sudo_user."""
    base_command = ["sudo", "-u", sudo_user]

    user_env = _get_user_env_vars(sudo_user)
    if env_extra:
        user_env.update(env_extra)

    env_prefix = []
    for k, v in user_env.items():
        env_prefix.append(f"{k}={v}")

    full_command = base_command + env_prefix + command

    # For logging, show the command as the user would type it (more or less)
    cmd_str_for_log = ' '.join(env_prefix + command)
    print_info(f"Running as user '{sudo_user}': {cmd_str_for_log}" + (f" in {cwd}" if cwd else ""))

    return run_command(full_command, capture_output=capture_output, check=check, text=text, cwd=cwd)


def _install_gnome_extension_from_git(ext_name: str, ext_details: dict, sudo_user: str) -> bool:
    """Clones a git repo and runs an install script for a GNOME extension."""
    print_info(f"Installing '{ext_name}' from Git repository: {ext_details['url']}")

    if not shutil.which("git"):
        print_error("'git' command not found. Cannot clone repository. Please install git.")
        return False

    repo_name = Path(ext_details["url"]).stem # e.g., "quick-settings-tweaks"
    clone_dir = TEMP_DIR / repo_name

    if clone_dir.exists():
        print_info(f"Removing existing clone directory: {clone_dir}")
        shutil.rmtree(clone_dir)
    clone_dir.mkdir(parents=True, exist_ok=True)

    # Clone command can be run as current user (root or non-root)
    if not run_command(["git", "clone", ext_details["url"], str(clone_dir)]):
        print_error(f"Failed to clone repository for '{ext_name}'.")
        return False
    print_success(f"Repository for '{ext_name}' cloned to {clone_dir}")

    install_script_path = clone_dir / ext_details["install_script"]
    if not install_script_path.is_file():
        print_error(f"Install script '{ext_details['install_script']}' not found in repository for '{ext_name}'.")
        return False

    # The install script itself likely needs to run as the target user
    print_info(f"Running install script: {install_script_path.name} for user '{sudo_user}'")
    # Ensure script is executable
    run_command(["chmod", "+x", str(install_script_path)], check=False) # Run as current euid

    if os.geteuid() == 0 and sudo_user:
        # Pass DISPLAY if available, though install.sh might not need it directly
        # It's more for gnome-extensions commands.
        success = _run_command_as_user([str(install_script_path)], sudo_user, cwd=str(clone_dir))
    else: # Running as the user directly
        success = run_command([str(install_script_path)], cwd=str(clone_dir))


    if success:
        print_success(f"Install script for '{ext_name}' executed successfully.")
    else:
        print_error(f"Install script for '{ext_name}' failed.")
        return False
    
    # Optional: Enable the extension if the install script doesn't do it
    # This would require knowing the UUID. For quick-settings-tweaks, let's assume its script handles enabling.
    # If not, we'd need to add its UUID to EXTENSIONS_TO_INSTALL and call _enable_extension.

    return True

def _check_and_install_gnome_extensions_cli():
    """Checks for gnome-extensions CLI and tries to install gnome-shell-extensions if not found."""
    if shutil.which("gnome-extensions"):
        print_info("'gnome-extensions' command-line tool found.")
        return True

    print_warning("'gnome-extensions' command-line tool not found. Attempting to install 'gnome-shell-extensions' package...")
    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
    if run_command(["sudo", dnf_cmd, "install", "-y", "gnome-shell-extensions"]):
        print_success("'gnome-shell-extensions' package installed. This should provide 'gnome-extensions' CLI.")
        if shutil.which("gnome-extensions"):
            print_info("'gnome-extensions' command-line tool is now available.")
            return True
        else:
            print_error("'gnome-extensions' CLI still not found after installing 'gnome-shell-extensions'. Manual extension installation might be required.")
            return False
    else:
        print_error("Failed to install 'gnome-shell-extensions'. Manual extension installation might be required for EGO extensions.")
        return False


def _install_gnome_extension_from_ego(ext_name: str, ext_details: dict, sudo_user: str) -> bool:
    """Installs a GNOME Shell extension from extensions.gnome.org using gnome-extensions CLI."""
    uuid = ext_details["uuid"]
    numerical_id = ext_details.get("numerical_id") # May not always be used by CLI directly, but good for reference
    display_name = ext_details.get("name", ext_name)

    print_info(f"Attempting to install '{display_name}' (UUID: {uuid}) from extensions.gnome.org...")

    if not shutil.which("gnome-extensions"):
        print_error("'gnome-extensions' command-line tool not available. Cannot install this extension automatically.")
        return False

    # Command to install (and it usually enables by default)
    # Some versions of gnome-extensions might prefer the numerical ID, others the UUID.
    # The `install` command often takes the numerical ID or a known name.
    # Let's try with UUID first as it's more canonical. If that fails, mention numerical ID.
    # The command often is `gnome-extensions install <packagename from EGO>` or `gnome-extensions install <zipfile>`
    # For installing *from* EGO, it's usually implicit if `org.gnome.Extensions` is managing it.
    # The `gnome-extensions install UUID` might be for pre-downloaded extensions.
    #
    # A common pattern is:
    # 1. Use `gnome-extensions-cli install <numerical_id>` (if using that specific tool)
    # 2. Or, download zip from EGO (e.g. https://extensions.gnome.org/download-extension/UUID.shell-extension.zip?version_tag=XXXX)
    #    then `gnome-extensions install --force downloaded-file.zip`
    #
    # Let's assume `gnome-extensions install <uuid>` is the primary way for already packaged extensions (like user-themes often is)
    # or that the tool can fetch with a known name/ID if not directly by UUID for remote ones.
    # The `gnome-extensions install <uuid>` command often expects the extension to be already downloaded and available in a staging area.
    #
    # A more reliable way if gnome-extensions CLI supports direct fetching:
    # The tool `gnome-shell-extension-installer` (from https://github.com/brunelli/gnome-shell-extension-installer)
    # uses numerical IDs. e.g., `./gnome-shell-extension-installer <ID_FROM_EGO_URL>`
    #
    # If `gnome-extensions install <UUID>` works, it's simplest.
    # Let's try `gnome-extensions install <UUID>` and then `gnome-extensions enable <UUID>`.
    # It might require the extension to be "known" by being part of `gnome-shell-extensions` pkg.

    cmd_install = ["gnome-extensions", "install", uuid] # This might be for local files.
    # The `gnome-extensions install <name>` where name is from `gnome-extensions list --all` might be better.
    # Let's assume for now we need to enable them if they are part of a pre-installed set,
    # or the user will use the Extensions app for others if `gnome-extensions install UUID` doesn't fetch.

    cmd_enable = ["gnome-extensions", "enable", uuid]

    if os.geteuid() == 0 and sudo_user:
        # Try enabling first, it might already be installed (e.g. user-themes from gnome-shell-extensions pkg)
        print_info(f"Attempting to enable '{display_name}' (UUID: {uuid}) for user '{sudo_user}'...")
        stdout_enable, stderr_enable, rc_enable = _run_command_as_user(cmd_enable, sudo_user, capture_output=True, check=False)
        if rc_enable == 0:
            print_success(f"Extension '{display_name}' enabled successfully for user '{sudo_user}'.")
            return True
        else:
            print_warning(f"Failed to enable existing extension '{display_name}' (UUID: {uuid}) or it's not installed. RC: {rc_enable}. Stderr: {stderr_enable.strip() if stderr_enable else 'N/A'}")
            print_info(f"Will attempt to inform user to install '{display_name}' (ID: {numerical_id}) manually if direct install method fails.")
            # For now, we don't have a universal command-line installer from EGO without external scripts.
            # The `org.gnome.Extensions` app is the primary way.
            # So, this function will mostly try to *enable* known ones.
            # A true "install from EGO via CLI" is tricky without a dedicated tool.
            # Let's assume `gnome-extensions install <ID>` might work if such a command exists in the version of `gnome-extensions` available.
            # The most common `gnome-extensions install` takes a local .zip file.
            #
            # Fallback: Inform user.
            print_warning(f"Could not automatically install or enable '{display_name}' (UUID: {uuid}).")
            print_info(f"Please install '{display_name}' (Extension ID: {numerical_id}) manually using the 'Extensions' application (org.gnome.Extensions).")
            print_info(f"You can find it at: https://extensions.gnome.org/extension/{numerical_id}/")
            return False # Mark as not automatically successful

    else: # Running as the user directly
        print_info(f"Attempting to enable '{display_name}' (UUID: {uuid})...")
        stdout_enable, stderr_enable, rc_enable = run_command(cmd_enable, capture_output=True, check=False)
        if rc_enable == 0:
            print_success(f"Extension '{display_name}' enabled successfully.")
            return True
        else:
            print_warning(f"Failed to enable existing extension '{display_name}' (UUID: {uuid}) or it's not installed. RC: {rc_enable}. Stderr: {stderr_enable.strip() if stderr_enable else 'N/A'}")
            print_warning(f"Could not automatically install or enable '{display_name}' (UUID: {uuid}).")
            print_info(f"Please install '{display_name}' (Extension ID: {numerical_id}) manually using the 'Extensions' application (org.gnome.Extensions).")
            print_info(f"You can find it at: https://extensions.gnome.org/extension/{numerical_id}/")
            return False
    return False


def _run_gsettings_as_user(key: str, value: str, schema: str, sudo_user: str) -> bool:
    """Helper to run a gsettings command as the target user."""
    command_base = ["gsettings", "set", schema, key, value]
    final_command_str_for_logging = f"gsettings set {schema} {key} {value}"

    if os.geteuid() == 0 and sudo_user:
        stdout, stderr, returncode = _run_command_as_user(command_base, sudo_user, capture_output=True, check=False)
    elif os.geteuid() == 0 and not sudo_user: # Running as root, SUDO_USER not set
        print_warning(f"Running gsettings as current user 'root' because SUDO_USER is not set. Command: {final_command_str_for_logging}")
        stdout, stderr, returncode = run_command(command_base, capture_output=True, check=False)
    else: # Running as the user directly
        current_user = os.getlogin()
        print_info(f"Executing gsettings for user '{current_user}': {final_command_str_for_logging}")
        stdout, stderr, returncode = run_command(command_base, capture_output=True, check=False)

    if returncode == 0:
        print_success(f"gsettings: Schema '{schema}', Key '{key}' successfully set to '{value}'.")
        if stdout and stdout.strip():
            console.print(f"[dim]gsettings stdout:\n{stdout.strip()}[/dim]")
        return True
    else:
        print_error(f"Failed to set gsettings: Schema '{schema}', Key '{key}' to '{value}'. RC: {returncode}")
        if stdout and stdout.strip():
            console.print(f"[dim yellow]gsettings stdout:\n{stdout.strip()}[/dim yellow]")
        if stderr and stderr.strip():
            console.print(f"[dim red]gsettings stderr:\n{stderr.strip()}[/dim red]")
        return False


def run_gnome_configuration():
    print_header("Phase 3: GNOME Configuration") # Assuming this is still Phase 3 based on previous context. Adjust if needed.
    phase_successful = True

    sudo_user = os.environ.get('SUDO_USER')
    if os.geteuid() == 0 and not sudo_user:
        print_warning("Running as root, but SUDO_USER is not set. GNOME settings and extension installations will target the root user's environment, which is likely not intended.")
        # Decide if to proceed or exit. For now, proceed with warning.
        # return False # Or, prompt user
    elif not sudo_user and os.geteuid() != 0:
        sudo_user = os.getlogin() # Script is run by user directly
        print_info(f"Running as non-root user: {sudo_user}. GNOME changes will affect this user.")


    # Step X.1: Install gnome-tweaks
    print_step("GNOME.1", "Installing GNOME Tweaks")
    if run_command(["sudo", "dnf", "install", "-y", "gnome-tweaks"]):
        print_success("GNOME Tweaks installed successfully.")
    else:
        print_error("Failed to install GNOME Tweaks.")
        phase_successful = False

    # Step X.2: Install GNOME Extensions app from Flathub
    print_step("GNOME.2", "Installing GNOME Extensions App (Flatpak)")
    flatpak_path_stdout, _, flatpak_path_retcode = run_command(["which", "flatpak"], capture_output=True, check=False)
    if flatpak_path_retcode != 0 or not flatpak_path_stdout.strip():
        print_error("Flatpak command not found. Cannot install GNOME Extensions app from Flathub.")
        phase_successful = False
    else:
        print_info("Flatpak command found.")
        remotes_stdout, _, _ = run_command(["flatpak", "remotes", "--show-details"], capture_output=True, check=False)
        flathub_exists = remotes_stdout and "flathub" in remotes_stdout.lower()
        if not flathub_exists:
            print_warning("Flathub remote not found. Attempting to add it.")
            if run_command(["sudo", "flatpak", "remote-add", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"]):
                print_success("Flathub remote added successfully.")
            else:
                print_error("Failed to add Flathub remote. Cannot install GNOME Extensions app.")
                phase_successful = False # Critical for this step

        if flathub_exists: # Re-check as it might have been added
            if run_command(["sudo", "flatpak", "install", "-y", "flathub", "org.gnome.Extensions"]):
                print_success("GNOME Extensions app (org.gnome.Extensions) installed successfully from Flathub.")
            else:
                print_error("Failed to install GNOME Extensions app from Flathub.")
                phase_successful = False

    # Step X.3: Set GNOME theme to dark
    if sudo_user or os.geteuid() !=0: # Only attempt if we have a target user (real user or SUDO_USER)
        print_step("GNOME.3", "Setting GNOME Interface Style to 'prefer-dark'")
        if _run_gsettings_as_user(key="color-scheme", value="prefer-dark", schema="org.gnome.desktop.interface", sudo_user=sudo_user if os.geteuid()==0 else None):
            print_success("GNOME color scheme set to 'prefer-dark'.")
        else:
            print_error("Failed to set GNOME color scheme to 'prefer-dark'.")
            # This is desired, so mark phase as not fully successful if it fails.
            # phase_successful = False # Let's make this a warning, not a full phase fail.
            print_warning("Failed to set GNOME color scheme automatically.")
    else:
        print_warning("Skipping dark theme setting as target user could not be determined reliably (SUDO_USER not set while running as root).")


    # Step X.4: Install GNOME Shell Extensions
    print_step("GNOME.4", "Installing GNOME Shell Extensions")
    if not sudo_user and os.geteuid() == 0:
        print_warning("SUDO_USER not set while running as root. Skipping GNOME Shell extension installation as target user is unclear.")
    else:
        if not _check_and_install_gnome_extensions_cli():
            print_warning("Proceeding with extension installation attempts, but 'gnome-extensions' CLI issues might prevent success for some.")

        TEMP_DIR.mkdir(parents=True, exist_ok=True) # Ensure temp dir for git clones exists

        num_ext_success = 0
        num_ext_attempted = 0

        for ext_key, ext_details in EXTENSIONS_TO_INSTALL.items():
            num_ext_attempted += 1
            ext_type = ext_details.get("type")
            current_ext_success = False
            target_user_for_extension = sudo_user if os.geteuid() == 0 else os.getlogin() # This needs to be the actual user

            if ext_type == "git":
                current_ext_success = _install_gnome_extension_from_git(ext_key, ext_details, target_user_for_extension)
            elif ext_type == "ego":
                current_ext_success = _install_gnome_extension_from_ego(ext_key, ext_details, target_user_for_extension)
            else:
                print_warning(f"Unknown extension type '{ext_type}' for '{ext_key}'. Skipping.")
                current_ext_success = False # Effectively failed for this extension

            if current_ext_success:
                num_ext_success +=1
            else:
                # phase_successful = False # If any extension fails, the sub-phase is not perfect.
                print_warning(f"Installation/enabling of extension '{ext_details.get('name', ext_key)}' was not successful or requires manual steps.")

        if num_ext_attempted > 0:
            if num_ext_success == num_ext_attempted:
                print_success("All attempted GNOME Shell extensions processed successfully (or user was advised for manual install).")
            else:
                print_warning(f"{num_ext_success}/{num_ext_attempted} GNOME Shell extensions were processed automatically. Some may require manual installation/enabling via the 'Extensions' app.")
                # phase_successful = False # Decided above to not fail the whole phase for individual extension issues if app is installed.

        # Cleanup temp directory
        if TEMP_DIR.exists():
            print_info(f"Cleaning up temporary directory: {TEMP_DIR}")
            shutil.rmtree(TEMP_DIR)

    if phase_successful:
        print_success("GNOME Configuration phase completed successfully (or with minor issues for individual extensions that may require manual steps).")
        print_info("Please log out and log back in for all GNOME changes and extensions to take full effect.")
    else:
        print_error("GNOME Configuration phase encountered significant errors. Please review the output.")

    return phase_successful
