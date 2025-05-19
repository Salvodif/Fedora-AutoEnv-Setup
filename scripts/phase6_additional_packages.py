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

# _install_dnf_packages_ph6 removed, use system_utils.install_dnf_packages

def _is_package_already_installed(pkg_name: str) -> bool:
    """Checks if a DNF package is already installed using 'rpm -q'."""
    if not pkg_name:
        app_logger.debug("Empty package name passed to _is_package_already_installed.")
        return False 
    app_logger.debug(f"Checking if package '{pkg_name}' is installed.")
    try:
        proc = system_utils.run_command(
            ["rpm", "-q", pkg_name], 
            capture_output=True, 
            check=False, # check=False as non-zero means not installed
            print_fn_info=None, # Be quiet for this check
            logger=app_logger 
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
                    shell=True, 
                    check=True,
                    print_fn_info=con.print_info, 
                    print_fn_error=con.print_error,
                    logger=app_logger
                )
            except Exception: # Error already logged by run_command
                app_logger.error(f"Failed to execute repository setup command for {friendly_name}: '{cmd_str_from_yaml}'.")
                # con.print_error already called by run_command
                return False
        app_logger.info(f"Repository setup commands for {friendly_name} completed.")
        con.print_success(f"Repository setup commands for {friendly_name} completed.")
    
    app_logger.info(f"Installing '{dnf_install_pkg_name}' for {friendly_name}...")
    # con.print_info(f"Installing '{dnf_install_pkg_name}' for {friendly_name}...") # Handled by install_dnf_packages
    
    if system_utils.install_dnf_packages(
        [dnf_install_pkg_name],
        allow_erasing=True, # Good default for custom packages that might replace things
        print_fn_info=con.print_info,
        print_fn_error=con.print_error,
        print_fn_sub_step=con.print_sub_step,
        logger=app_logger
    ):
        app_logger.info(f"Successfully installed '{friendly_name}' ({dnf_install_pkg_name}).")
        # con.print_success(f"Successfully installed '{friendly_name}' ({dnf_install_pkg_name}).") # Handled by install_dnf_packages
        return True
    else:
        app_logger.error(f"Failed to install DNF package '{dnf_install_pkg_name}' for {friendly_name}.")
        # con.print_error already called by install_dnf_packages
        return False

# --- Main Phase Function ---

def run_phase6(app_config: dict) -> bool:
    """Executes Phase 6: Additional User Packages Installation."""
    app_logger.info("Starting Phase 6: Additional User Packages.")
    con.print_step("PHASE 6: Additional User Packages")
    overall_success = True
    
    phase6_config = config_loader.get_phase_data(app_config, "phase6_additional_packages")
    if not phase6_config:
        app_logger.warning("No configuration found for Phase 6 in config. Skipping phase.")
        con.print_warning("No configuration found for Phase 6. Skipping additional package installation.")
        return True 

    app_logger.info("Phase 6, Step 1: Installing standard DNF packages...")
    con.print_info("\nStep 1: Installing standard DNF packages...")
    dnf_packages_to_install = phase6_config.get("dnf_packages", [])
    if dnf_packages_to_install:
        if not system_utils.install_dnf_packages(
            dnf_packages_to_install,
            allow_erasing=True, # Safe default for additional packages
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step,
            logger=app_logger
        ):
            overall_success = False
    else:
        app_logger.info("No standard DNF packages listed for Phase 6.")
        con.print_info("No standard DNF packages listed for installation in Phase 6.")

    app_logger.info("Phase 6, Step 2: Installing DNF packages requiring custom repository setup...")
    con.print_info("\nStep 2: Installing DNF packages requiring custom repository setup...")
    custom_repo_pkgs = phase6_config.get("custom_repo_dnf_packages", {})
    if custom_repo_pkgs:
        for pkg_key, pkg_conf_dict in custom_repo_pkgs.items():
            if not isinstance(pkg_conf_dict, dict):
                app_logger.warning(f"Invalid configuration for custom DNF package '{pkg_key}' in config. Expected a dictionary. Skipping.")
                con.print_warning(f"Invalid configuration for custom DNF package '{pkg_key}'. Skipping.")
                overall_success = False 
                continue
            if not _install_custom_repo_dnf_package(pkg_key, pkg_conf_dict):
                overall_success = False
    else:
        app_logger.info("No custom repository DNF packages listed for Phase 6.")
        con.print_info("No custom repository DNF packages listed for installation in Phase 6.")

    app_logger.info("Phase 6, Step 3: Installing Flatpak applications...")
    con.print_info("\nStep 3: Installing additional Flatpak applications (system-wide)...")
    flatpak_apps_to_install = phase6_config.get("flatpak_apps", {}) # Expects Dict[app_id, friendly_name]
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