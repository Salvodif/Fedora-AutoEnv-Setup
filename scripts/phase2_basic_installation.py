# Fedora-AutoEnv-Setup/scripts/phase2_basic_installation.py

import subprocess # Retained for type hints if complex subprocess logic were here
import sys
import os 
from pathlib import Path
from typing import Optional, List, Dict # Added Dict for flatpak_apps typing

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils 
from scripts.logger_utils import app_logger 

# Helper functions like _install_dnf_packages, _install_dnf_groups, _swap_dnf_package
# were already removed in prior refactoring and their logic is in system_utils.

# --- Main Phase Function ---

def run_phase2(app_config: dict) -> bool:
    con.print_step("PHASE 2: Basic System Package Configuration")
    app_logger.info("Starting Phase 2: Basic System Package Configuration.")
    overall_success = True

    phase2_config = config_loader.get_phase_data(app_config, "phase2_basic_configuration")
    if not phase2_config: # get_phase_data returns {} if not found or error
        con.print_warning("No configuration found for Phase 2. Skipping.")
        app_logger.warning("No Phase 2 configuration found or configuration is invalid. Skipping.")
        return True # Successfully skipped

    # 1. Install DNF packages
    con.print_info("Step 1: Installing general DNF packages...")
    app_logger.info("Phase 2, Step 1: Installing general DNF packages.")
    dnf_packages_from_config = phase2_config.get("dnf_packages", [])

    if dnf_packages_from_config:
        if not system_utils.install_dnf_packages(
            dnf_packages_from_config,
            allow_erasing=True,
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step,
            logger=app_logger
        ):
            overall_success = False
            # Error message already printed by install_dnf_packages / run_command
            app_logger.error("Failed to install one or more DNF packages in Phase 2.")
        else:
            app_logger.info(f"Successfully processed DNF packages in Phase 2: {dnf_packages_from_config}")
            # Example of checking a specific package within the list
            if "zsh" in [pkg.lower() for pkg in dnf_packages_from_config if isinstance(pkg, str)]:
                 app_logger.info("Zsh DNF package was included in the installation batch.")
    else:
        con.print_info("No general DNF packages listed for installation in Phase 2.")
        app_logger.info("No general DNF packages listed for Phase 2.")

    # 2. Handle Media Codec specific configurations
    if overall_success: # Only proceed if previous steps were successful
        con.print_info("\nStep 2: Configuring Media Codecs...")
        app_logger.info("Phase 2, Step 2: Configuring Media Codecs.")

        ffmpeg_swap_config = phase2_config.get("dnf_swap_ffmpeg")
        if ffmpeg_swap_config and isinstance(ffmpeg_swap_config, dict): # Ensure it's a dict
            from_pkg = ffmpeg_swap_config.get("from")
            to_pkg = ffmpeg_swap_config.get("to")
            if from_pkg and to_pkg:
                if not system_utils.swap_dnf_packages(
                    from_pkg, to_pkg,
                    allow_erasing=True, 
                    print_fn_info=con.print_info,
                    print_fn_error=con.print_error,
                    print_fn_sub_step=con.print_sub_step,
                    logger=app_logger
                ):
                    overall_success = False
                    app_logger.error(f"Failed to swap DNF package '{from_pkg}' with '{to_pkg}'.")
                else:
                    app_logger.info(f"Successfully swapped DNF package '{from_pkg}' with '{to_pkg}'.")
            else:
                con.print_warning("Incomplete 'dnf_swap_ffmpeg' configuration (missing 'from' or 'to'). Skipping swap.")
                app_logger.warning("Incomplete 'dnf_swap_ffmpeg' config in Phase 2.")
        else:
            app_logger.info("No 'dnf_swap_ffmpeg' configuration found or it's invalid in Phase 2.")

        sound_video_groups = phase2_config.get("dnf_groups_sound_video", [])
        if sound_video_groups:
            if not system_utils.install_dnf_groups(
                sound_video_groups,
                allow_erasing=True, 
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step,
                logger=app_logger
            ):
                overall_success = False
                app_logger.error(f"Failed to install DNF sound/video groups: {sound_video_groups}.")
            else:
                app_logger.info(f"Successfully processed DNF sound/video groups: {sound_video_groups}.")

        else:
            app_logger.info("No 'dnf_groups_sound_video' configuration found in Phase 2.")

    # 3. Install Flatpak applications (if any)
    if overall_success: # Only proceed if previous steps were successful
        con.print_info("\nStep 3: Installing Flatpak applications...")
        app_logger.info("Phase 2, Step 3: Installing Flatpak applications.")
        flatpak_apps_config: Dict[str, str] = phase2_config.get("flatpak_apps", {}) # Type hint for clarity
        if flatpak_apps_config:
            if not system_utils.install_flatpak_apps(
                apps_to_install=flatpak_apps_config,
                system_wide=True, 
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step,
                logger=app_logger
            ):
                overall_success = False
                app_logger.error("Failed to install one or more Flatpak applications in Phase 2.")
            else:
                app_logger.info(f"Successfully processed Flatpak applications in Phase 2: {list(flatpak_apps_config.keys())}")
        else:
            con.print_info("No Flatpak applications listed for installation in Phase 2.")
            app_logger.info("No Flatpak applications listed for Phase 2.")


    # --- Phase Completion Summary ---
    if overall_success:
        con.print_success("Phase 2: Basic System Package Configuration completed successfully.")
        app_logger.info("Phase 2 completed successfully.")
    else:
        con.print_error("Phase 2: Basic System Package Configuration completed with errors. Please review the output and logs.")
        app_logger.error("Phase 2 completed with errors.")

    return overall_success