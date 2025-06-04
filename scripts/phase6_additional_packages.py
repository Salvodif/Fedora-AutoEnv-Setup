# Fedora-AutoEnv-Setup/scripts/phase6_additional_packages.py

import sys
import shlex
import os
import stat
import subprocess # For CalledProcessError type hint if needed, though run_command handles
from pathlib import Path
from typing import List, Dict, Any, Optional # Added Optional

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils
from scripts.logger_utils import app_logger

# --- Helper Functions ---

def _generate_desktop_file_name(appimage_name: str) -> str:
    """
    Generates a .desktop file name from an AppImage file name.
    Example: "lala.AppImage" -> "lala.desktop"
             "MyApplication" -> "MyApplication.desktop"
    """
    if appimage_name.lower().endswith(".appimage"):
        return appimage_name[:-len(".AppImage")] + ".desktop"
    return appimage_name + ".desktop"

def _install_custom_app_images(custom_app_images_config: Dict[str, Dict[str, Any]], logger: 'logging.Logger') -> bool: # type: ignore
    """
    Installs custom AppImages specified in the configuration.
    Downloads, sets permissions, and creates .desktop files.
    """
    all_appimages_successful = True
    if not custom_app_images_config: # Early exit if no config
        logger.info("No custom AppImages to install.")
        # con.print_info("No custom AppImages listed in configuration.") # Handled in run_phase6
        return True

    home_dir = Path.home()
    apps_dir = home_dir / "Applications"
    desktop_entries_dir = home_dir / ".local" / "share" / "applications"

    try:
        os.makedirs(apps_dir, exist_ok=True)
        os.makedirs(desktop_entries_dir, exist_ok=True)
        logger.debug(f"Ensured AppImage directories exist: {apps_dir}, {desktop_entries_dir}")
    except OSError as e:
        logger.error(f"Could not create required directories for AppImages: {e}", exc_info=True)
        con.print_error(f"Error creating directories for AppImages: {e}")
        return False # Cannot proceed without these directories

    for app_key, app_data in custom_app_images_config.items():
        logger.info(f"Processing custom AppImage: {app_key}")
        con.print_sub_step(f"Processing custom AppImage: {app_data.get('name', app_key)}")

        url = app_data.get('url')
        rename_to = app_data.get('rename_to')

        if not url or not rename_to:
            logger.error(f"Missing 'url' or 'rename_to' for AppImage '{app_key}'. Skipping.")
            con.print_error(f"Configuration error for AppImage '{app_key}': Missing 'url' or 'rename_to'. Skipping.")
            all_appimages_successful = False
            continue

        app_image_path = apps_dir / rename_to
        icon_path_str_from_config = app_data.get('icon_path', '') # Might be empty
        icon_full_path_str = "" # Default to empty string for .desktop file if not provided/processed

        if icon_path_str_from_config:
            # Expanduser for potential ~ in icon_path
            icon_full_path_str = os.path.expanduser(icon_path_str_from_config)
            icon_dir = Path(icon_full_path_str).parent
            if not icon_dir.exists():
                logger.info(f"Creating icon directory: {icon_dir} for AppImage {app_key}")
                try:
                    os.makedirs(icon_dir, exist_ok=True)
                except OSError as e_icon_dir:
                    logger.warning(f"Could not create icon directory {icon_dir} for {app_key}: {e_icon_dir}. Icon might not be available.", exc_info=True)
                    con.print_warning(f"Could not create icon directory {icon_dir} for {app_key}. Icon might not be available.")
                    # Not critical enough to fail the whole appimage install, icon might be optional or pre-existing elsewhere

        # --- Download AppImage ---
        logger.info(f"Downloading AppImage {app_key} from {url} to {app_image_path}...")
        # Use a more descriptive message for the user for the command itself
        download_cmd_list = ['curl', '-L', '-o', str(app_image_path), url]
        if not system_utils.run_command(
            download_cmd_list,
            logger=logger,
            print_fn_info=con.print_info, # Shows "Executing command..."
            print_fn_error=con.print_error,
            custom_log_messages={
                "start": f"Downloading {app_data.get('name', app_key)} AppImage...",
                "success": f"Successfully downloaded {app_data.get('name', app_key)} AppImage.",
                "failure": f"Failed to download {app_data.get('name', app_key)} AppImage."
            }
        ):
            all_appimages_successful = False
            # Error already logged by run_command
            continue # Next AppImage

        # --- Set Executable Permission ---
        logger.info(f"Setting execute permission for {app_image_path}...")
        try:
            current_permissions = os.stat(app_image_path).st_mode
            new_permissions = current_permissions | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
            os.chmod(app_image_path, new_permissions)
            logger.debug(f"Set {app_image_path} to be executable.")
            con.print_info(f"Made {rename_to} executable.")
        except OSError as e_chmod:
            logger.error(f"Failed to set execute permission for {app_image_path}: {e_chmod}", exc_info=True)
            con.print_error(f"Error setting execute permission for {rename_to}: {e_chmod}")
            all_appimages_successful = False
            continue # Next AppImage

        # --- Create .desktop file ---
        desktop_file_name = _generate_desktop_file_name(rename_to)
        desktop_file_path = desktop_entries_dir / desktop_file_name
        logger.info(f"Generating .desktop file at {desktop_file_path} for {app_key}...")

        desktop_content = f"""[Desktop Entry]
Version={app_data.get('version', '1.0')}
Name={app_data.get('name', app_key)}
Comment={app_data.get('comment', '')}
Exec={shlex.quote(str(app_image_path))}
Icon={shlex.quote(icon_full_path_str) if icon_full_path_str else ""}
Type=Application
Terminal=false
Categories={app_data.get('categories', 'Utility;')}
"""
        # Using shlex.quote for Exec and Icon paths for safety

        try:
            with open(desktop_file_path, 'w', encoding='utf-8') as f_desktop:
                f_desktop.write(desktop_content)
            logger.info(f"Successfully created .desktop file: {desktop_file_path}")
            con.print_info(f"Created desktop entry: {desktop_file_name}")
        except IOError as e_desktop:
            logger.error(f"Failed to write .desktop file {desktop_file_path}: {e_desktop}", exc_info=True)
            con.print_error(f"Error creating .desktop file for {app_key}: {e_desktop}")
            all_appimages_successful = False
            # No need to continue to next appimage, this specific one failed at .desktop creation

    # --- Update Desktop Database ---
    # Only run if there were AppImages defined and all previous steps for them were successful (or handled)
    # The all_appimages_successful flag might be false due to individual app failures,
    # but we should still try to update the database if at least one app was processed and some config existed.
    if custom_app_images_config: # Check if there was anything to process
        logger.info("Attempting to update desktop database...")
        update_db_cmd = ['update-desktop-database', str(desktop_entries_dir)]
        if system_utils.run_command(
            update_db_cmd,
            logger=logger,
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            custom_log_messages={
                "start": f"Updating desktop database for directory: {desktop_entries_dir}...",
                "success": "Successfully updated desktop database.",
                "failure": "Failed to update desktop database."
            }
        ):
            logger.info("Desktop database updated successfully.")
            # con.print_success("Desktop database updated.") # run_command prints this
        else:
            # If this fails, it's not necessarily a failure of all appimages,
            # but it's a failure of this step.
            # Individual appimages might still work but might not appear in menus immediately.
            logger.warning("Failed to update desktop database. Desktop entries might not be immediately visible.")
            # con.print_warning("Failed to update desktop database. Manual update might be needed or a restart.")
            # We don't set all_appimages_successful to False here, as some might have installed correctly.
            # This is a system-level post-processing step.
            # However, if the task is to ensure they are *integrated*, this could be a failure point.
            # For now, treat as a warning for this function's return.
            # Let's decide that if this fails, the overall process for appimages is not fully successful.
            all_appimages_successful = False

    return all_appimages_successful

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
    appimage_step_success = True # New step
    
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

    # --- Step 4: Custom AppImages ---
    app_logger.info("Phase 6, Step 4: Installing custom AppImages...")
    con.print_info("\nStep 4: Installing custom AppImages from Phase 6 configuration...")
    custom_app_images_config = phase6_config.get("custom_app_images", {})
    if custom_app_images_config:
        if not _install_custom_app_images(custom_app_images_config, app_logger):
            overall_success = False
            appimage_step_success = False
            app_logger.error("Failed to install one or more custom AppImages in Phase 6.")
            # _install_custom_app_images logs its own detailed errors and prints user feedback
        else:
            app_logger.info("Successfully processed custom AppImages in Phase 6.")
            # _install_custom_app_images logs its own detailed success and prints user feedback
    else:
        app_logger.info("No custom AppImages listed for Phase 6.")
        con.print_info("No custom AppImages listed for installation in Phase 6.")

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
        if not appimage_step_success: # New
            failed_stages.append("Custom AppImages")

        error_details = "Failures occurred in: " + ", ".join(failed_stages) + "." if failed_stages else "An unspecified step failed."

        app_logger.error(f"Phase 6: Additional User Packages completed with errors. {error_details}")
        con.print_error(f"Phase 6: Additional User Packages completed with errors. {error_details} Please review the output and log file.")
    
    return overall_success