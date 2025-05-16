# Fedora-AutoEnv-Setup/scripts/phase6_additional_packages.py

import sys
from pathlib import Path
from typing import List, Dict

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils

# --- Helper Functions ---

def _install_dnf_packages_ph6(packages: List[str]) -> bool:
    """
    Installs a list of DNF packages.
    This is a utility function specific to this phase but could be
    further generalized into system_utils if more phases need simple DNF installs.
    For now, keeping it here for clarity of Phase 6.
    """
    if not packages:
        con.print_info("No DNF packages specified for installation in Phase 6.")
        return True

    con.print_sub_step(f"Installing DNF packages: {', '.join(packages)}")
    all_successful = True
    # Install packages one by one or in batches to give more granular feedback
    # For simplicity, installing all at once. run_command will log details.
    try:
        cmd = ["sudo", "dnf", "install", "-y"] + packages
        system_utils.run_command(
            cmd, 
            capture_output=True, # Set to False if you want to see live DNF output
            check=True,
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"Successfully processed DNF packages: {', '.join(packages)}")
    except Exception: # Error already logged by run_command
        con.print_error(f"Failed to install one or more DNF packages: {', '.join(packages)}. Check logs above.")
        all_successful = False
    return all_successful

# --- Main Phase Function ---

def run_phase6(app_config: dict) -> bool:
    """Executes Phase 6: Additional User Packages Installation."""
    con.print_step("PHASE 6: Additional User Packages")
    overall_success = True
    
    phase6_config = config_loader.get_phase_data(app_config, "phase6_additional_packages")
    if not phase6_config:
        con.print_warning("No configuration found for Phase 6. Skipping additional package installation.")
        return True # No config means nothing to do, technically success.

    # 1. Install DNF packages
    con.print_info("\nStep 1: Installing additional DNF packages...")
    dnf_packages_to_install = phase6_config.get("dnf_packages", [])
    if dnf_packages_to_install:
        if not _install_dnf_packages_ph6(dnf_packages_to_install):
            overall_success = False
            # Error message already printed by _install_dnf_packages_ph6
    else:
        con.print_info("No additional DNF packages listed for installation in Phase 6.")

    # 2. Install Flatpak applications
    con.print_info("\nStep 2: Installing additional Flatpak applications (system-wide)...")
    flatpak_apps_to_install = phase6_config.get("flatpak_apps", {}) # {app_id: friendly_name}
    if flatpak_apps_to_install:
        if not system_utils.install_flatpak_apps(
            apps_to_install=flatpak_apps_to_install,
            system_wide=True, # Assuming system-wide for these additional apps
            remote_name="flathub", # Defaulting to flathub
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step
        ):
            overall_success = False
            # Error message already printed by system_utils.install_flatpak_apps
            con.print_error("Phase 6 Flatpak installation encountered issues.")
    else:
        con.print_info("No additional Flatpak applications listed for installation in Phase 6.")
    
    # Add sections for other package managers if needed (e.g., Snap, direct downloads)

    if overall_success:
        con.print_success("Phase 6: Additional User Packages completed successfully.")
    else:
        con.print_error("Phase 6: Additional User Packages completed with errors. Please review the output.")
    
    return overall_success