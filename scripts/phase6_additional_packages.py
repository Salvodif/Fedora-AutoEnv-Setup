# Fedora-AutoEnv-Setup/scripts/phase6_additional_packages.py

import sys
import shlex 
from pathlib import Path
from typing import List, Dict, Any 
import subprocess # For CalledProcessError in type hints

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils
from scripts.logger_utils import app_logger

# --- Helper Functions ---

def _install_dnf_packages_ph6(packages: List[str]) -> bool:
    """Installs a list of DNF packages from already configured repositories."""
    if not packages:
        app_logger.info("No standard DNF packages specified for installation in Phase 6.")
        con.print_info("No standard DNF packages specified for installation in Phase 6.")
        return True

    app_logger.info(f"Attempting to install standard DNF packages: {packages}")
    con.print_sub_step(f"Installing standard DNF packages: {', '.join(packages)}")
    try:
        cmd = ["sudo", "dnf", "install", "-y", "--allowerasing"] + packages
        system_utils.run_command(
            cmd, 
            capture_output=True, 
            check=True,
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step,
            logger=app_logger
        )
        con.print_success(f"Successfully processed standard DNF packages: {', '.join(packages)}")
        app_logger.info(f"Successfully processed standard DNF packages: {packages}")
        return True
    except Exception as e: 
        app_logger.error(f"Failed to install one or more standard DNF packages: {packages}. Error: {e}", exc_info=True)
        # Error already logged to console by system_utils.run_command via print_fn_error
        return False

def _is_package_already_installed(pkg_name: str) -> bool:
    """Checks if a DNF package is already installed using 'rpm -q'."""
    if not pkg_name:
        return False # Cannot check an empty package name
    app_logger.debug(f"Checking if package '{pkg_name}' is installed.")
    try:
        check_cmd = ["rpm", "-q", pkg_name]
        proc = system_utils.run_command(
            check_cmd, 
            capture_output=True, 
            check=False, # rpm -q exits non-zero if not installed, which is not an error for this check
            print_fn_info=None, # Suppress "Executing..." for this quiet check
            logger=app_logger # Log the check command execution itself at debug level
        )
        if proc.returncode == 0:
            app_logger.info(f"Package '{pkg_name}' is already installed.")
            return True
        else:
            app_logger.info(f"Package '{pkg_name}' is not installed (rpm -q exit code: {proc.returncode}).")
            return False
    except FileNotFoundError: 
        app_logger.warning("'rpm' command not found. Cannot accurately check if package is installed.")
        con.print_warning("'rpm' command not found. Cannot accurately check if package is installed.")
        return False 
    except Exception as e:
        app_logger.warning(f"Error checking if package '{pkg_name}' is installed: {e}", exc_info=True)
        con.print_warning(f"Error checking if package '{pkg_name}' is installed.")
        return False 

def _install_custom_repo_dnf_package(pkg_key: str, pkg_config: Dict[str, Any]) -> bool:
    """
    Handles the installation of a DNF package that requires custom repository setup.
    """
    friendly_name = pkg_config.get("name", pkg_key)
    check_pkg_name = pkg_config.get("check_if_installed_pkg")
    repo_commands = pkg_config.get("repo_setup_commands", [])
    dnf_install_pkg_name = pkg_config.get("dnf_package_to_install")

    app_logger.info(f"Processing custom DNF package: {friendly_name} (Key: {pkg_key})")
    con.print_sub_step(f"Processing custom DNF package: {friendly_name}")

    if not dnf_install_pkg_name:
        app_logger.error(f"Missing 'dnf_package_to_install' for '{friendly_name}' in configuration. Skipping.")
        con.print_error(f"Missing 'dnf_package_to_install' for '{friendly_name}' in configuration. Skipping.")
        return False

    if check_pkg_name and _is_package_already_installed(check_pkg_name):
        app_logger.info(f"Package '{friendly_name}' (checked as '{check_pkg_name}') seems to be already installed. Skipping setup and installation.")
        con.print_info(f"Package '{friendly_name}' (checked as '{check_pkg_name}') seems to be already installed. Skipping setup and installation.")
        return True

    if repo_commands:
        app_logger.info(f"Running repository setup commands for {friendly_name}...")
        con.print_info(f"Running repository setup commands for {friendly_name}...")
        for cmd_str_from_yaml in repo_commands:
            app_logger.debug(f"Executing repo setup command: {cmd_str_from_yaml}")
            try:
                system_utils.run_command(
                    cmd_str_from_yaml, 
                    shell=True, # ALWAYS use shell=True for these YAML-defined full command strings
                    check=True,
                    print_fn_info=con.print_info, 
                    print_fn_error=con.print_error,
                    logger=app_logger
                )
            except Exception as e: 
                app_logger.error(f"Failed to execute repository setup command for {friendly_name}: '{cmd_str_from_yaml}'. Error: {e}", exc_info=True)
                con.print_error(f"Failed to execute repository setup command for {friendly_name}: '{cmd_str_from_yaml}'.")
                return False
        app_logger.info(f"Repository setup commands for {friendly_name} completed.")
        con.print_success(f"Repository setup commands for {friendly_name} completed.")
    
    app_logger.info(f"Installing '{dnf_install_pkg_name}' for {friendly_name}...")
    con.print_info(f"Installing '{dnf_install_pkg_name}' for {friendly_name}...")
    try:
        install_cmd_list = ["sudo", "dnf", "install", "-y", "--allowerasing", dnf_install_pkg_name]
        system_utils.run_command(
            install_cmd_list,
            capture_output=True, 
            check=True,
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            logger=app_logger
        )
        app_logger.info(f"Successfully installed '{friendly_name}' ({dnf_install_pkg_name}).")
        con.print_success(f"Successfully installed '{friendly_name}' ({dnf_install_pkg_name}).")
        return True
    except Exception as e:
        app_logger.error(f"Failed to install DNF package '{dnf_install_pkg_name}' for {friendly_name}. Error: {e}", exc_info=True)
        con.print_error(f"Failed to install DNF package '{dnf_install_pkg_name}' for {friendly_name}.")
        return False

# --- Main Phase Function ---

def run_phase6(app_config: dict) -> bool:
    """Executes Phase 6: Additional User Packages Installation."""
    app_logger.info("Starting Phase 6: Additional User Packages.")
    con.print_step("PHASE 6: Additional User Packages")
    overall_success = True
    
    phase6_config = config_loader.get_phase_data(app_config, "phase6_additional_packages")
    if not phase6_config:
        app_logger.warning("No configuration found for Phase 6 in YAML. Skipping phase.")
        con.print_warning("No configuration found for Phase 6. Skipping additional package installation.")
        return True 

    # 1. Install standard DNF packages
    app_logger.info("Phase 6, Step 1: Installing standard DNF packages...")
    con.print_info("\nStep 1: Installing standard DNF packages...")
    dnf_packages_to_install = phase6_config.get("dnf_packages", [])
    if dnf_packages_to_install:
        if not _install_dnf_packages_ph6(dnf_packages_to_install):
            overall_success = False
    else:
        app_logger.info("No standard DNF packages listed for Phase 6.")
        con.print_info("No standard DNF packages listed for installation in Phase 6.")

    # 2. Install DNF packages with custom repository setup
    app_logger.info("Phase 6, Step 2: Installing DNF packages requiring custom repository setup...")
    con.print_info("\nStep 2: Installing DNF packages requiring custom repository setup...")
    custom_repo_pkgs = phase6_config.get("custom_repo_dnf_packages", {})
    if custom_repo_pkgs:
        for pkg_key, pkg_conf_dict in custom_repo_pkgs.items():
            if not isinstance(pkg_conf_dict, dict):
                app_logger.warning(f"Invalid configuration for custom DNF package '{pkg_key}' in YAML. Expected a dictionary. Skipping.")
                con.print_warning(f"Invalid configuration for custom DNF package '{pkg_key}'. Skipping.")
                overall_success = False # Mark as an issue
                continue
            if not _install_custom_repo_dnf_package(pkg_key, pkg_conf_dict):
                overall_success = False
    else:
        app_logger.info("No custom repository DNF packages listed for Phase 6.")
        con.print_info("No custom repository DNF packages listed for installation in Phase 6.")

    # 3. Install Flatpak applications
    app_logger.info("Phase 6, Step 3: Installing Flatpak applications...")
    con.print_info("\nStep 3: Installing additional Flatpak applications (system-wide)...")
    flatpak_apps_to_install = phase6_config.get("flatpak_apps", {})
    if flatpak_apps_to_install:
        if not system_utils.install_flatpak_apps(
            apps_to_install=flatpak_apps_to_install,
            system_wide=True,
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step,
            logger=app_logger
        ):
            overall_success = False
            app_logger.error("Phase 6 Flatpak installation encountered issues.")
            con.print_error("Phase 6 Flatpak installation encountered issues.")
    else:
        app_logger.info("No Flatpak applications listed for Phase 6.")
        con.print_info("No additional Flatpak applications listed for installation in Phase 6.")
    
    if overall_success:
        app_logger.info("Phase 6: Additional User Packages completed successfully.")
        con.print_success("Phase 6: Additional User Packages completed successfully.")
    else:
        app_logger.error("Phase 6: Additional User Packages completed with errors.")
        con.print_error("Phase 6: Additional User Packages completed with errors. Please review the output and log file.")
    
    return overall_success