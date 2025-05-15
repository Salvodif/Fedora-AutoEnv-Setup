# scripts/additional_packages.py
import logging
import shutil # For shutil.which

from scripts.myrich import (
    print_header, print_info, print_error, print_success, print_step, console, print_warning
)
from scripts.utils import run_command

# --- Helper Functions ---

def _install_dnf_packages(config: dict) -> bool:
    """Installs DNF packages defined in DNF_PACKAGES_TO_INSTALL."""
    print_step("System Packages", "Installing DNF packages...")

    dnf_packages_to_install = config.get('dnf_packages', []) # Get from config
    if not dnf_packages_to_install:
        print_info("No DNF packages specified in configuration for installation.")
        return True


    all_successful = True
    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
    
    # Install all at once for efficiency
    # run_command uses check=True by default, returns boolean
    command = ["sudo", dnf_cmd, "install", "-y"] + dnf_packages_to_install
    if run_command(command):
        print_success(f"Successfully processed DNF packages: {', '.join(dnf_packages_to_install)}")
    else:
        print_error("Failed to install one or more DNF packages. Please check the output above.")
        # run_command with check=True already logs details
        all_successful = False
    
    # Alternatively, install one by one for more granular error reporting if preferred:
    # for pkg in DNF_PACKAGES_TO_INSTALL:
    #     print_info(f"Installing DNF package: {pkg}...")
    #     if run_command(["sudo", dnf_cmd, "install", "-y", pkg]): # check=True (default)
    #         print_success(f"DNF package '{pkg}' installed successfully.")
    #     else:
    #         print_error(f"Failed to install DNF package '{pkg}'.")
    #         all_successful = False
    return all_successful

def _install_flatpak_apps(config: dict) -> bool:
    """Installs Flatpak applications defined in FLATPAK_APPS_TO_INSTALL."""
    print_step("Flatpak Apps", "Installing Flatpak applications...")

    flatpak_apps_to_install = config.get('flatpak_apps', {}) # Get from config
    if not flatpak_apps_to_install:
        print_info("No Flatpak applications specified in configuration for installation.")
        return True

    all_successful = True

    # Check if flatpak is installed using check=False, capture_output=True
    flatpak_stdout, flatpak_stderr, flatpak_rc = run_command(["which", "flatpak"], capture_output=True, check=False)
    if flatpak_rc != 0:
        print_error("Flatpak command-line tool not found. Skipping Flatpak installations.")
        return False 

    # Ensure Flathub remote is added (system-wide)
    # Using check=False, capture_output=True to inspect output
    remotes_stdout, remotes_stderr, remotes_rc = run_command(
        ["flatpak", "remotes", "--system", "--show-details"], # Check system remotes
        capture_output=True, check=False
    )
    flathub_exists = remotes_rc == 0 and remotes_stdout and "flathub" in remotes_stdout.lower()

    if not flathub_exists:
        print_warning("Flathub remote not found in system remotes. Attempting to add it.")

        if run_command(["sudo", "flatpak", "remote-add", "--system", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"]):
            print_success("Flathub remote added successfully to system.")
            flathub_exists = True
        else:
            print_error("Failed to add Flathub remote to system.")
            # Continue, but Flathub installs will likely fail

    if not flathub_exists:
        print_error("Flathub remote is not available. Cannot install specified Flatpak applications from Flathub.")
        return False # Cannot proceed if Flathub is needed and not there

    for app_id, friendly_name in flatpak_apps_to_install.items():
        print_info(f"Installing Flatpak application: {friendly_name} ({app_id})...")
        # run_command with check=True (default) returns bool for flatpak install
        if run_command(["sudo", "flatpak", "install", "--system", "-y", "flathub", app_id]):
            print_success(f"Flatpak application '{friendly_name}' installed successfully.")
        else:
            print_error(f"Failed to install Flatpak application '{friendly_name}' ({app_id}).")
            all_successful = False
            # run_command with check=True already prints error details from subprocess
    
    return all_successful

# --- Main Function for this Module ---

def run_additional_packages_installation(config: dict):
    """Main function to orchestrate the installation of additional DNF and Flatpak packages."""
    print_header("Phase 6: Additional Packages Installation")
    
    # Group DNF installations
    dnf_success = _install_dnf_packages(config)
    console.rule() # Visual separator

    # Group Flatpak installations
    flatpak_success = _install_flatpak_apps(config)
    
    if dnf_success and flatpak_success:
        print_success("Additional packages installation phase completed successfully.")
        return True
    else:
        print_error("Additional packages installation phase encountered one or more errors. Please review logs.")
        return False
