# scripts/gnome_configuration.py
import logging
import os
import pwd # For getpwnam

from scripts.myrich import (
    print_header, print_info, print_error, print_success, print_step, print_warning, console
)
from scripts.utils import run_command

def _run_gsettings_as_user(key: str, value: str, schema: str) -> bool:
    """
    Helper to run a gsettings command, attempting to run as the original user if
    the script is executed with sudo.
    """
    sudo_user = os.environ.get('SUDO_USER')
    command_base = ["gsettings", "set", schema, key, value]

    final_command_str_for_logging = f"gsettings set {schema} {key} {value}"

    if os.geteuid() == 0 and sudo_user:
        # If running as root and SUDO_USER is available
        try:
            user_info = pwd.getpwnam(sudo_user)
            user_uid = user_info.pw_uid
            # Note: For gsettings to work reliably when run via sudo for a user,
            # the DBUS_SESSION_BUS_ADDRESS environment variable is crucial.
            # It typically looks like "unix:path=/run/user/UID/bus".
            dbus_address = f"unix:path=/run/user/{user_uid}/bus"

            # Command to run as the original user
            full_command = [
                "sudo", "-u", sudo_user,
                f"DBUS_SESSION_BUS_ADDRESS={dbus_address}",
                *command_base
            ]
            print_info(f"Attempting to set gsettings for user '{sudo_user}' (UID {user_uid}). Command: {final_command_str_for_logging}")
        except KeyError:
            print_warning(f"Could not get UID for user '{sudo_user}'. Falling back to simpler 'sudo -u {sudo_user} ...' for gsettings. This might not work if DBUS_SESSION_BUS_ADDRESS is not inherited.")
            full_command = ["sudo", "-u", sudo_user, *command_base]
        except Exception as e:
            print_error(f"Error preparing gsettings command for user '{sudo_user}': {e}")
            return False
    else:
        # Running as the user directly, or SUDO_USER not found (e.g. logged in as root)
        full_command = command_base
        current_user = os.getlogin()
        if os.geteuid() == 0 and not sudo_user:
            print_warning(f"Running gsettings as current user 'root' because SUDO_USER is not set. This will affect root's desktop settings if a session is active.")
            print_info(f"Executing for user 'root': {final_command_str_for_logging}")
        else:
            print_info(f"Executing for user '{current_user}': {final_command_str_for_logging}")


    stdout, stderr, returncode = run_command(full_command, capture_output=True, check=False, text=True)

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
    print_header("Phase 3: GNOME Configuration")
    phase_successful = True

    # Step 3.1: Install gnome-tweaks
    print_step("3.1", "Installing GNOME Tweaks")
    if run_command(["sudo", "dnf", "install", "-y", "gnome-tweaks"]):
        print_success("GNOME Tweaks installed successfully.")
    else:
        print_error("Failed to install GNOME Tweaks.")
        phase_successful = False # Continue with other steps but mark phase as failed

    # Step 3.2: Install GNOME Extensions app from Flathub
    print_step("3.2", "Installing GNOME Extensions App (Flatpak)")
    
    # Check if flatpak command exists
    flatpak_path_stdout, _, flatpak_path_retcode = run_command(["which", "flatpak"], capture_output=True, check=False)
    if flatpak_path_retcode != 0 or not flatpak_path_stdout.strip():
        print_error("Flatpak command not found. Cannot install GNOME Extensions app from Flathub.")
        print_info("Please ensure Flatpak is installed (e.g., via Phase 1 or 2).")
        phase_successful = False
    else:
        print_info("Flatpak command found.")
        # Check if flathub remote exists
        remotes_stdout, _, _ = run_command(["flatpak", "remotes", "--show-details"], capture_output=True, check=False)
        flathub_exists = remotes_stdout and "flathub" in remotes_stdout.lower()

        if not flathub_exists:
            print_warning("Flathub remote not found. Attempting to add it.")
            if run_command(["sudo", "flatpak", "remote-add", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"]):
                print_success("Flathub remote added successfully.")
                flathub_exists = True
            else:
                print_error("Failed to add Flathub remote. Cannot install GNOME Extensions app.")
                phase_successful = False
        
        if flathub_exists:
            if run_command(["sudo", "flatpak", "install", "-y", "flathub", "org.gnome.Extensions"]):
                print_success("GNOME Extensions app (org.gnome.Extensions) installed successfully from Flathub.")
            else:
                print_error("Failed to install GNOME Extensions app from Flathub.")
                phase_successful = False
        # else: error already reported if flathub could not be added

    # Step 3.3: Set GNOME theme to dark
    print_step("3.3", "Setting GNOME Interface Style to 'prefer-dark'")
    if _run_gsettings_as_user(key="color-scheme", value="prefer-dark", schema="org.gnome.desktop.interface"):
        print_success("GNOME color scheme set to 'prefer-dark'.")
    else:
        print_error("Failed to set GNOME color scheme to 'prefer-dark'.")
        # This is a desired outcome, so if it fails, the phase is not fully successful.
        phase_successful = False

    if phase_successful:
        print_success("GNOME Configuration (Phase 3) completed successfully!")
    else:
        print_error("GNOME Configuration (Phase 3) encountered errors. Please review the output.")
    
    return phase_successful
