# Fedora-AutoEnv-Setup/scripts/phase6_additional_packages.py

import sys
import shlex 
from pathlib import Path
from typing import List, Dict, Any 
import subprocess # For CalledProcessError type hint if needed, though run_command handles

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils
from scripts.logger_utils import app_logger

# --- Helper Functions ---

# _is_package_already_installed was moved to system_utils.is_package_installed_rpm

def _install_custom_repo_dnf_package(pkg_key: str, pkg_config_data: Dict[str, Any]) -> bool:
    """
    Handles the installation of a DNF package that requires custom repository setup.
    Uses system_utils.is_package_installed_rpm for checks.
    """
    friendly_name = pkg_config_data.get("name", pkg_key) # Use key as fallback name
    # Package name to check with 'rpm -q' if it's already installed
    pkg_name_for_rpm_check = pkg_config_data.get("check_if_installed_pkg")
    repo_setup_commands_list = pkg_config_data.get("repo_setup_commands", [])
    # Actual package name to pass to 'dnf install'
    dnf_pkg_to_install_name = pkg_config_data.get("dnf_package_to_install")

    app_logger.info(f"Processing custom DNF package: {friendly_name} (Config Key: {pkg_key})")
    con.print_sub_step(f"Processing custom DNF package: {friendly_name}")

    if not dnf_pkg_to_install_name:
        app_logger.error(f"Missing 'dnf_package_to_install' for '{friendly_name}' in configuration. Skipping this package.")
        con.print_error(f"Configuration error for '{friendly_name}': Missing 'dnf_package_to_install'. Skipping.")
        return False # Critical config error for this package

    # Check if the package (or its indicator) is already installed
    if pkg_name_for_rpm_check:
        try:
            if system_utils.is_package_installed_rpm(
                pkg_name_for_rpm_check, 
                logger=app_logger, 
                print_fn_info=None # Be quiet for this internal check
            ):
                app_logger.info(f"Package '{friendly_name}' (checked as '{pkg_name_for_rpm_check}') seems to be already installed. Skipping setup and installation.")
                con.print_info(f"Package '{friendly_name}' (checked via '{pkg_name_for_rpm_check}') appears to be already installed. Skipping.")
                return True # Successfully skipped as already present
        except FileNotFoundError: # rpm command itself not found
            con.print_error("'rpm' command not found. Cannot check if custom DNF package is already installed. Attempting installation.")
            app_logger.error("'rpm' command not found. Cannot perform pre-check for custom DNF package.")
            # Proceed with installation attempt, as we can't verify.
        except Exception as e_rpm_check: # Other errors during rpm check
            con.print_warning(f"Could not verify if '{pkg_name_for_rpm_check}' is installed: {e_rpm_check}. Proceeding with installation attempt.")
            app_logger.warning(f"Error checking RPM status for '{pkg_name_for_rpm_check}': {e_rpm_check}", exc_info=True)
            # Proceed with installation attempt.

    # Run repository setup commands if any
    if repo_setup_commands_list:
        app_logger.info(f"Running repository setup commands for {friendly_name}...")
        con.print_info(f"Configuring repository for {friendly_name}...") # More user-friendly than "running commands"
        all_repo_cmds_ok = True
        for cmd_str_from_config in repo_setup_commands_list:
            app_logger.debug(f"Executing repo setup command for {friendly_name}: {cmd_str_from_config}")
            try:
                # These commands often need sudo and shell (e.g., tee, rpm --import)
                system_utils.run_command(
                    cmd_str_from_config, 
                    shell=True, # Assume commands from config might need shell
                    check=True, # Fail if a repo command fails
                    print_fn_info=con.print_info, # Show "Executing..."
                    print_fn_error=con.print_error,
                    logger=app_logger
                )
            except Exception: # Error already logged by run_command
                app_logger.error(f"Failed to execute repository setup command for {friendly_name}: '{cmd_str_from_config}'. Aborting installation for this package.")
                # con.print_error already called by run_command
                all_repo_cmds_ok = False
                break # Stop processing repo commands for this package if one fails
        
        if not all_repo_cmds_ok:
            return False # Repo setup failed for this package
        
        app_logger.info(f"Repository setup commands for {friendly_name} completed successfully.")
        con.print_success(f"Repository for {friendly_name} configured successfully.")
    
    # Install the DNF package
    app_logger.info(f"Attempting to install '{dnf_pkg_to_install_name}' for {friendly_name} via DNF...")
    # con.print_info is handled by install_dnf_packages sub-step
    
    if system_utils.install_dnf_packages(
        [dnf_pkg_to_install_name], # Must be a list
        allow_erasing=True, # Good default for custom packages that might replace things or resolve conflicts
        print_fn_info=con.print_info,
        print_fn_error=con.print_error,
        print_fn_sub_step=con.print_sub_step,
        logger=app_logger
    ):
        app_logger.info(f"Successfully installed DNF package '{dnf_pkg_to_install_name}' for {friendly_name}.")
        # install_dnf_packages prints its own success for the batch
        return True
    else:
        app_logger.error(f"Failed to install DNF package '{dnf_pkg_to_install_name}' for {friendly_name}.")
        # con.print_error already called by install_dnf_packages
        return False

# --- Main Phase Function ---

def run_phase6(app_config: dict) -> bool:
    """Executes Phase 6: Additional User Packages Installation."""
    app_logger.info("Starting Phase 6: Additional User Packages.")
    con.print_step("PHASE 6: Additional User Packages")
    overall_success = True
    dnf_step_success = True
    custom_dnf_step_success = True
    flatpak_step_success = True
    
    phase6_config = config_loader.get_phase_data(app_config, "phase6_additional_packages")
    if not phase6_config: # get_phase_data returns {} if not found or error
        app_logger.warning("No configuration found for Phase 6 or configuration is invalid. Skipping phase.")
        con.print_warning("No configuration found for Phase 6. Skipping additional package installation.")
        return True # Successfully skipped

    # --- Step 1: Standard DNF Packages ---
    app_logger.info("Phase 6, Step 1: Installing standard DNF packages...")
    con.print_info("\nStep 1: Installing standard DNF packages from Phase 6 configuration...")
    dnf_packages_to_install_ph6 = phase6_config.get("dnf_packages", [])
    if dnf_packages_to_install_ph6:
        if not system_utils.install_dnf_packages(
            dnf_packages_to_install_ph6,
            allow_erasing=True, # Safe default for additional packages
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step,
            logger=app_logger
        ):
            overall_success = False
            dnf_step_success = False
            app_logger.error("Failed to install one or more standard DNF packages in Phase 6.")
        else:
            app_logger.info(f"Successfully processed standard DNF packages in Phase 6: {dnf_packages_to_install_ph6}")
    else:
        app_logger.info("No standard DNF packages listed for Phase 6.")
        con.print_info("No standard DNF packages listed for installation in Phase 6.")

    # --- Step 2: Custom Repository DNF Packages ---
    app_logger.info("Phase 6, Step 2: Installing DNF packages requiring custom repository setup...")
    con.print_info("\nStep 2: Installing DNF packages requiring custom repository setup from Phase 6 configuration...")
    custom_repo_pkgs_map: Dict[str, Dict] = phase6_config.get("custom_repo_dnf_packages", {})
    if custom_repo_pkgs_map:
        for pkg_key, pkg_config_dict in custom_repo_pkgs_map.items():
            if not isinstance(pkg_config_dict, dict): # Validate config structure
                app_logger.warning(f"Invalid configuration for custom DNF package '{pkg_key}' in Phase 6 config (not a dictionary). Skipping.")
                con.print_warning(f"Invalid configuration for custom DNF package '{pkg_key}'. Skipping.")
                overall_success = False
                custom_dnf_step_success = False
                continue
            if not _install_custom_repo_dnf_package(pkg_key, pkg_config_dict):
                overall_success = False
                custom_dnf_step_success = False
                # _install_custom_repo_dnf_package logs its own errors
                app_logger.error(f"Installation failed for custom DNF package: {pkg_config_dict.get('name', pkg_key)}")
    else:
        app_logger.info("No custom repository DNF packages listed for Phase 6.")
        con.print_info("No custom repository DNF packages listed for installation in Phase 6.")

    # --- Step 3: Flatpak Applications ---
    app_logger.info("Phase 6, Step 3: Installing Flatpak applications...")
    con.print_info("\nStep 3: Installing additional Flatpak applications (system-wide) from Phase 6 configuration...")
    flatpak_apps_to_install_ph6: Dict[str, str] = phase6_config.get("flatpak_apps", {}) 
    if flatpak_apps_to_install_ph6:
        if not system_utils.install_flatpak_apps(
            apps_to_install=flatpak_apps_to_install_ph6,
            system_wide=True, # Typically system-wide for this phase
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step,
            logger=app_logger
        ):
            overall_success = False
            flatpak_step_success = False
            app_logger.error("Failed to install one or more Flatpak applications in Phase 6.")
        else:
            app_logger.info(f"Successfully processed Flatpak applications in Phase 6: {list(flatpak_apps_to_install_ph6.keys())}")

    else:
        app_logger.info("No Flatpak applications listed for Phase 6.")
        con.print_info("No additional Flatpak applications listed for installation in Phase 6.")
    
    # --- Phase Completion Summary ---
    if overall_success:
        app_logger.info("Phase 6: Additional User Packages completed successfully.")
        con.print_success("Phase 6: Additional User Packages completed successfully.")
    else:
        failed_stages = []
        if not dnf_step_success:
            failed_stages.append("Standard DNF Packages")
        if not custom_dnf_step_success:
            failed_stages.append("Custom Repository DNF Packages")
        if not flatpak_step_success:
            failed_stages.append("Flatpak Applications")

        error_details = "Failures occurred in: " + ", ".join(failed_stages) + "." if failed_stages else "An unspecified step failed."

        app_logger.error(f"Phase 6: Additional User Packages completed with errors. {error_details}")
        con.print_error(f"Phase 6: Additional User Packages completed with errors. {error_details} Please review the output and log file.")
    
    return overall_success