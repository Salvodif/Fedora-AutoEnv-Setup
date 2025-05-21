# Fedora-AutoEnv-Setup/scripts/phase2_basic_installation.py

import subprocess
import sys
import os 
from pathlib import Path
from typing import Optional, List 

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils 
from scripts.logger_utils import app_logger 

# _install_dnf_packages is removed (use system_utils.install_dnf_packages)
# _install_dnf_groups is removed (use system_utils.install_dnf_groups)
# _swap_dnf_package is removed (use system_utils.swap_dnf_packages)

# --- Main Phase Function ---

def run_phase2(app_config: dict) -> bool:
    con.print_step("PHASE 2: Basic System Package Configuration")
    app_logger.info("Starting Phase 2: Basic System Package Configuration.")
    overall_success = True

    phase2_config = config_loader.get_phase_data(app_config, "phase2_basic_configuration")
    if not phase2_config:
        con.print_warning("No configuration found for Phase 2. Skipping.")
        app_logger.warning("No Phase 2 configuration found. Skipping.")
        return True

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
            app_logger.error("Failed to install one or more DNF packages in Phase 2.")
        else:
            app_logger.info(f"Successfully processed DNF packages in Phase 2: {dnf_packages_from_config}")
            if "zsh" in [pkg.lower() for pkg in dnf_packages_from_config]:
                 app_logger.info("Zsh DNF package was included in the installation batch.")
    else:
        con.print_info("No general DNF packages listed for installation in Phase 2.")
        app_logger.info("No general DNF packages listed for Phase 2.")

    # 2. Handle Media Codec specific configurations
    if overall_success: 
        con.print_info("\nStep 2: Configuring Media Codecs...")
        app_logger.info("Phase 2, Step 2: Configuring Media Codecs.")

        ffmpeg_swap_config = phase2_config.get("dnf_swap_ffmpeg")
        if ffmpeg_swap_config:
            from_pkg = ffmpeg_swap_config.get("from")
            to_pkg = ffmpeg_swap_config.get("to")
            if from_pkg and to_pkg:
                # con.print_sub_step(f"Swapping DNF package '{from_pkg}' with '{to_pkg}'...") # system_utils.swap_dnf_packages handles sub_step
                if not system_utils.swap_dnf_packages(
                    from_pkg, to_pkg,
                    allow_erasing=True, # Default for swap
                    print_fn_info=con.print_info,
                    print_fn_error=con.print_error,
                    print_fn_sub_step=con.print_sub_step,
                    logger=app_logger
                ):
                    overall_success = False
                    # Error messages handled by swap_dnf_packages
            else:
                con.print_warning("Incomplete 'dnf_swap_ffmpeg' configuration. Skipping swap.")
                app_logger.warning("Incomplete 'dnf_swap_ffmpeg' config.")
        else:
            app_logger.info("No 'dnf_swap_ffmpeg' config.")

        sound_video_groups = phase2_config.get("dnf_groups_sound_video", [])
        if sound_video_groups:
            # con.print_sub_step(f"Installing DNF sound/video groups: {', '.join(sound_video_groups)}") # system_utils.install_dnf_groups handles sub_step
            if not system_utils.install_dnf_groups(
                sound_video_groups,
                allow_erasing=True, # Default for group install
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step,
                logger=app_logger
            ):
                overall_success = False
                # Error messages handled by install_dnf_groups
        else:
            app_logger.info("No 'dnf_groups_sound_video' config.")

    # 3. Install Flatpak applications (if any)
    if overall_success:
        con.print_info("\nStep 3: Installing Flatpak applications...")
        app_logger.info("Phase 2, Step 3: Installing Flatpak applications.")
        flatpak_apps_config = phase2_config.get("flatpak_apps", {})
        if flatpak_apps_config:
            if not system_utils.install_flatpak_apps(
                apps_to_install=flatpak_apps_config,
                system_wide=True, # Typically Flatpaks in early phases are system-wide utilities
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


    if overall_success:
        con.print_success("Phase 2: Basic System Package Configuration completed successfully.")
        app_logger.info("Phase 2 completed successfully.")
    else:
        con.print_error("Phase 2: Basic System Package Configuration completed with errors. Please review the output.")
        app_logger.error("Phase 2 completed with errors.")

    return overall_success