# Fedora-AutoEnv-Setup/scripts/phase6_additional_packages.py

import sys
import shlex # For quoting in custom repo commands
from pathlib import Path
from typing import List, Dict, Any # Added Any

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils

# --- Helper Functions ---

def _install_dnf_packages_ph6(packages: List[str]) -> bool:
    """Installs a list of DNF packages from already configured repositories."""
    if not packages:
        con.print_info("No standard DNF packages specified for installation in Phase 6.")
        return True

    con.print_sub_step(f"Installing standard DNF packages: {', '.join(packages)}")
    try:
        # Add --allowerasing for robustness, in case of minor conflicts
        cmd = ["sudo", "dnf", "install", "-y", "--allowerasing"] + packages
        system_utils.run_command(
            cmd, 
            capture_output=True, 
            check=True,
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"Successfully processed standard DNF packages: {', '.join(packages)}")
        return True
    except Exception: 
        con.print_error(f"Failed to install one or more standard DNF packages: {', '.join(packages)}. Check logs above.")
        return False

def _is_package_already_installed(pkg_name: str) -> bool:
    """Checks if a DNF package is already installed using 'rpm -q'."""
    if not pkg_name:
        return False
    try:
        # rpm -q returns 0 if installed, non-zero otherwise
        check_cmd = ["rpm", "-q", pkg_name]
        proc = system_utils.run_command(check_cmd, capture_output=True, check=False, print_fn_info=None) # Suppress info for this check
        return proc.returncode == 0
    except FileNotFoundError: # rpm command not found
        con.print_warning("'rpm' command not found. Cannot accurately check if package is installed.")
        return False # Assume not installed if rpm is missing
    except Exception as e:
        con.print_warning(f"Error checking if package '{pkg_name}' is installed: {e}")
        return False # Assume not installed on error

def _install_custom_repo_dnf_package(pkg_key: str, pkg_config: Dict[str, Any]) -> bool:
    """
    Handles the installation of a DNF package that requires custom repository setup.
    
    Args:
        pkg_key (str): The key from the YAML (e.g., "visual_studio_code").
        pkg_config (Dict[str, Any]): The configuration dictionary for this package.

    Returns:
        bool: True if successful, False otherwise.
    """
    friendly_name = pkg_config.get("name", pkg_key)
    check_pkg_name = pkg_config.get("check_if_installed_pkg")
    repo_commands = pkg_config.get("repo_setup_commands", [])
    # post_repo_cmd = pkg_config.get("post_repo_setup_command") # Example of how to get it
    dnf_install_pkg_name = pkg_config.get("dnf_package_to_install")

    con.print_sub_step(f"Processing custom DNF package: {friendly_name}")

    if not dnf_install_pkg_name:
        con.print_error(f"Missing 'dnf_package_to_install' for '{friendly_name}' in configuration. Skipping.")
        return False

    if check_pkg_name and _is_package_already_installed(check_pkg_name):
        con.print_info(f"Package '{friendly_name}' (checked as '{check_pkg_name}') seems to be already installed. Skipping setup and installation.")
        return True

    # Execute repository setup commands
    if repo_commands:
        con.print_info(f"Running repository setup commands for {friendly_name}...")
        for cmd_str in repo_commands:
            try:
                # Commands like 'echo ... | sudo tee ...' need shell=True
                # Ensure commands from YAML are safe or well-understood.
                # For `rpm --import`, shell=False is fine if cmd_str is just the command.
                # For `echo | sudo tee`, shell=True is required.
                # Let's assume complex commands from YAML might need shell=True.
                is_shell_needed = "|" in cmd_str or ">" in cmd_str or "<" in cmd_str or "&" in cmd_str
                
                # Most repo setup commands require root privileges, ensure 'sudo' is part of the command string
                # or handle it by always running these as root if the script itself is sudo.
                # The commands in YAML for vscode already include sudo.
                system_utils.run_command(
                    cmd_str, 
                    shell=is_shell_needed, # Be cautious with shell=True and external strings
                    check=True,
                    print_fn_info=con.print_info,
                    print_fn_error=con.print_error
                )
            except Exception as e:
                con.print_error(f"Failed to execute repository setup command for {friendly_name}: '{cmd_str}'. Error: {e}")
                return False
        con.print_success(f"Repository setup commands for {friendly_name} completed.")
    
    # Optional: Run a command after repo setup, e.g., dnf makecache
    # For VS Code, 'dnf install code' will likely refresh metadata for the new repo automatically.
    # If you had post_repo_cmd:
    # if post_repo_cmd:
    #     con.print_info(f"Running post-repository setup command for {friendly_name}: {post_repo_cmd}")
    #     try:
    #         system_utils.run_command(post_repo_cmd, shell=True, check=True, ...)
    #     except Exception as e:
    #         con.print_error(f"Post-repository setup command failed: {e}")
    #         return False

    # Install the DNF package
    con.print_info(f"Installing '{dnf_install_pkg_name}' for {friendly_name}...")
    try:
        install_cmd_list = ["sudo", "dnf", "install", "-y", "--allowerasing", dnf_install_pkg_name]
        system_utils.run_command(
            install_cmd_list,
            capture_output=True, # Or False to see live output
            check=True,
            print_fn_info=con.print_info,
            print_fn_error=con.print_error
        )
        con.print_success(f"Successfully installed '{friendly_name}' ({dnf_install_pkg_name}).")
        return True
    except Exception as e:
        con.print_error(f"Failed to install DNF package '{dnf_install_pkg_name}' for {friendly_name}. Error: {e}")
        return False

# --- Main Phase Function ---

def run_phase6(app_config: dict) -> bool:
    """Executes Phase 6: Additional User Packages Installation."""
    con.print_step("PHASE 6: Additional User Packages")
    overall_success = True
    
    phase6_config = config_loader.get_phase_data(app_config, "phase6_additional_packages")
    if not phase6_config:
        con.print_warning("No configuration found for Phase 6. Skipping additional package installation.")
        return True 

    # 1. Install standard DNF packages
    con.print_info("\nStep 1: Installing standard DNF packages...")
    dnf_packages_to_install = phase6_config.get("dnf_packages", [])
    if dnf_packages_to_install:
        if not _install_dnf_packages_ph6(dnf_packages_to_install):
            overall_success = False
    else:
        con.print_info("No standard DNF packages listed for installation in Phase 6.")

    # 2. Install DNF packages with custom repository setup
    con.print_info("\nStep 2: Installing DNF packages requiring custom repository setup...")
    custom_repo_pkgs = phase6_config.get("custom_repo_dnf_packages", {})
    if custom_repo_pkgs:
        for pkg_key, pkg_conf_dict in custom_repo_pkgs.items():
            if not isinstance(pkg_conf_dict, dict):
                con.print_warning(f"Invalid configuration for custom DNF package '{pkg_key}'. Skipping.")
                overall_success = False
                continue
            if not _install_custom_repo_dnf_package(pkg_key, pkg_conf_dict):
                overall_success = False
                # Error already logged by the helper function
    else:
        con.print_info("No custom repository DNF packages listed for installation in Phase 6.")


    # 3. Install Flatpak applications (Step number adjusted)
    con.print_info("\nStep 3: Installing additional Flatpak applications (system-wide)...")
    flatpak_apps_to_install = phase6_config.get("flatpak_apps", {})
    if flatpak_apps_to_install:
        if not system_utils.install_flatpak_apps(
            apps_to_install=flatpak_apps_to_install,
            system_wide=True,
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step
        ):
            overall_success = False
            con.print_error("Phase 6 Flatpak installation encountered issues.")
    else:
        con.print_info("No additional Flatpak applications listed for installation in Phase 6.")
    
    if overall_success:
        con.print_success("Phase 6: Additional User Packages completed successfully.")
    else:
        con.print_error("Phase 6: Additional User Packages completed with errors. Please review the output.")
    
    return overall_success