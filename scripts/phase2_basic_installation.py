# Fedora-AutoEnv-Setup/scripts/phase2_basic_installation.py

import subprocess 
import sys
import os 
import shlex # For quoting paths in commands
import shutil # <--- ADD THIS LINE
import tempfile # For temporary directories/files
from pathlib import Path
from typing import Optional, List, Dict 

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils 
from scripts.logger_utils import app_logger 

# --- Helper Function for Nerd Font Installation ---

def _install_nerd_font(
    font_name: str, 
    font_url: str, 
    target_user: str, 
    target_user_home: Path
) -> bool:
    """
    Downloads, extracts, and installs a Nerd Font for the target user.
    """
    con.print_sub_step(f"Installing Nerd Font: {font_name}...")
    app_logger.info(f"Attempting to install Nerd Font '{font_name}' from {font_url} for user '{target_user}'.")

    # Define user's font directory: ~/.local/share/fonts
    user_fonts_dir = target_user_home / ".local" / "share" / "fonts"
    
    # Ensure the user's font directory exists
    if not system_utils.ensure_dir_exists(
        user_fonts_dir, 
        target_user=target_user, 
        logger=app_logger,
        print_fn_info=con.print_info,
        print_fn_error=con.print_error,
        print_fn_success=con.print_success
    ):
        con.print_error(f"Could not create or verify user font directory: {user_fonts_dir}. Skipping font '{font_name}'.")
        app_logger.error(f"Failed to ensure user font directory '{user_fonts_dir}' for user '{target_user}'. Cannot install font '{font_name}'.")
        return False

    # Create a temporary directory to download and extract the font
    # Try to create it within user's .cache for neatness, fallback to system /tmp
    temp_dir_obj: Optional[Path] = None
    try:
        user_cache_dir = target_user_home / ".cache"
        system_utils.ensure_dir_exists(user_cache_dir, target_user=target_user, logger=app_logger, print_fn_info=None) # Quiet ensure

        # Create a unique temporary directory as the target_user
        mktemp_cmd = f"mktemp -d -p {shlex.quote(str(user_cache_dir))} nerd_font_{font_name}_XXXXXX"
        try:
            proc_mktemp = system_utils.run_command(
                mktemp_cmd, run_as_user=target_user, shell=True,
                capture_output=True, check=True, logger=app_logger, print_fn_info=None
            )
            temp_dir_obj = Path(proc_mktemp.stdout.strip())
        except Exception: # Fallback to system /tmp if user .cache fails
            app_logger.warning(f"Failed to create temp dir in user's .cache for {font_name}, trying system /tmp.")
            # Still create as target_user if possible, though /tmp usually world-writable
            mktemp_cmd_sys = f"mktemp -d -t nerd_font_{font_name}_XXXXXX"
            proc_mktemp_sys = system_utils.run_command(
                mktemp_cmd_sys, run_as_user=target_user, shell=True,
                capture_output=True, check=True, logger=app_logger, print_fn_info=None
            )
            temp_dir_obj = Path(proc_mktemp_sys.stdout.strip())

        app_logger.info(f"Created temporary directory for '{font_name}': {temp_dir_obj}")

        font_zip_filename = Path(font_url).name # e.g., Hack.zip
        font_zip_path = temp_dir_obj / font_zip_filename

        # Download the font ZIP file using curl (as target_user)
        # curl -L: follow redirects, -o: output to file, -sS: silent with errors
        download_cmd = f"curl -L -sS -o {shlex.quote(str(font_zip_path))} {shlex.quote(font_url)}"
        con.print_info(f"Downloading {font_name} from {font_url} to {font_zip_path}...")
        system_utils.run_command(
            download_cmd, run_as_user=target_user, shell=True, 
            check=True, logger=app_logger, print_fn_info=con.print_info, print_fn_error=con.print_error
        )
        app_logger.info(f"Successfully downloaded '{font_name}' to {font_zip_path}.")

        # Unzip the font file into the user's font directory (as target_user)
        # unzip -o: overwrite existing files without prompting
        # -d: destination directory
        unzip_cmd = f"unzip -o {shlex.quote(str(font_zip_path))} -d {shlex.quote(str(user_fonts_dir))}"
        con.print_info(f"Unzipping {font_name} to {user_fonts_dir}...")
        system_utils.run_command(
            unzip_cmd, run_as_user=target_user, shell=True, # unzip often works better with shell for path expansion or if run in specific dir
            cwd=temp_dir_obj, # Run unzip from the temp dir, though -d makes it less critical
            check=True, logger=app_logger, print_fn_info=con.print_info, print_fn_error=con.print_error
        )
        app_logger.info(f"Successfully unzipped '{font_name}' into '{user_fonts_dir}'.")
        con.print_success(f"Nerd Font '{font_name}' installed successfully for user '{target_user}'.")
        return True

    except Exception as e:
        con.print_error(f"Failed to install Nerd Font '{font_name}': {e}")
        app_logger.error(f"Error during installation of Nerd Font '{font_name}' for user '{target_user}': {e}", exc_info=True)
        return False
    finally:
        # Clean up the temporary directory (as target_user)
        if temp_dir_obj and temp_dir_obj.exists():
            app_logger.info(f"Cleaning up temporary directory: {temp_dir_obj}")
            rm_temp_cmd = f"rm -rf {shlex.quote(str(temp_dir_obj))}"
            try:
                system_utils.run_command(
                    rm_temp_cmd, run_as_user=target_user, shell=True, 
                    check=False, logger=app_logger, print_fn_info=None # Best effort cleanup
                )
            except Exception as e_cleanup:
                app_logger.warning(f"Failed to cleanup temporary directory {temp_dir_obj}: {e_cleanup}")


# --- Main Phase Function ---

def run_phase2(app_config: dict) -> bool:
    con.print_step("PHASE 2: Basic System Package Configuration")
    app_logger.info("Starting Phase 2: Basic System Package Configuration.")
    overall_success = True

    phase2_config = config_loader.get_phase_data(app_config, "phase2_basic_configuration")
    if not phase2_config: 
        con.print_warning("No configuration found for Phase 2. Skipping.")
        app_logger.warning("No Phase 2 configuration found or configuration is invalid. Skipping.")
        return True 

    # --- Step 0: Determine Target User ---
    # Nerd Fonts are installed per-user. Other packages might also be user-specific if not system-wide.
    # For fc-cache, it needs to be run as the user for whom fonts were installed.
    target_user = system_utils.get_target_user(
        logger=app_logger, print_fn_info=con.print_info,
        print_fn_error=con.print_error, print_fn_warning=con.print_warning
    )
    if not target_user:
        app_logger.error("Cannot determine target user for Phase 2 user-specific tasks (like Nerd Fonts). Aborting phase.")
        return False 

    target_user_home = system_utils.get_user_home_dir(target_user, logger=app_logger, print_fn_error=con.print_error)
    if not target_user_home: 
        app_logger.error(f"Target user home for '{target_user}' not found. Aborting user-specific tasks in Phase 2.")
        return False
    
    app_logger.info(f"Phase 2 operations will consider target user '{target_user}' with home '{target_user_home}'.")


    # 1. Install DNF packages (includes unzip, fontconfig needed for fonts)
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
            if "zsh" in [pkg.lower() for pkg in dnf_packages_from_config if isinstance(pkg, str)]:
                 app_logger.info("Zsh DNF package was included in the installation batch.")
    else:
        con.print_info("No general DNF packages listed for installation in Phase 2.")
        app_logger.info("No general DNF packages listed for Phase 2.")

    # 2. Handle Media Codec specific configurations
    if overall_success: 
        con.print_info("\nStep 2: Configuring Media Codecs...")
        app_logger.info("Phase 2, Step 2: Configuring Media Codecs.")

        ffmpeg_swap_config = phase2_config.get("dnf_swap_ffmpeg")
        if ffmpeg_swap_config and isinstance(ffmpeg_swap_config, dict):
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
                con.print_warning("Incomplete 'dnf_swap_ffmpeg' configuration. Skipping swap.")
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

    # 3. Install Flatpak applications
    if overall_success:
        con.print_info("\nStep 3: Installing Flatpak applications...")
        app_logger.info("Phase 2, Step 3: Installing Flatpak applications.")
        flatpak_apps_config: Dict[str, str] = phase2_config.get("flatpak_apps", {})
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
            
    # 4. Install Nerd Fonts
    fonts_installed_this_run = False
    if overall_success:
        con.print_info("\nStep 4: Installing Nerd Fonts...")
        app_logger.info(f"Phase 2, Step 4: Installing Nerd Fonts for user '{target_user}'.")
        nerd_fonts_to_install: Dict[str, str] = phase2_config.get("nerd_fonts_to_install", {})
        
        # Ensure curl is available for downloading fonts
        if nerd_fonts_to_install and not shutil.which("curl"):
            con.print_error("'curl' command not found. Cannot download Nerd Fonts. Please ensure 'curl' is in DNF packages.")
            app_logger.error("'curl' command not found. Cannot download Nerd Fonts.")
            overall_success = False # Mark as failure for this step
        
        if overall_success and nerd_fonts_to_install: # Re-check overall_success after curl check
            for font_name, font_url in nerd_fonts_to_install.items():
                if _install_nerd_font(font_name, font_url, target_user, target_user_home):
                    fonts_installed_this_run = True
                else:
                    overall_success = False # If one font fails, mark phase as having errors
                    app_logger.error(f"Failed to install Nerd Font: {font_name}")
                    # _install_nerd_font already prints specific errors
            
            if fonts_installed_this_run:
                con.print_info(f"Attempting to refresh font cache for user '{target_user}'...")
                app_logger.info(f"Refreshing font cache for user '{target_user}' using 'fc-cache -fv'.")
                try:
                    # fc-cache should be run as the user whose font cache needs updating
                    system_utils.run_command(
                        ["fc-cache", "-fv"], 
                        run_as_user=target_user,
                        check=True, capture_output=True, # Capture output to log it
                        print_fn_info=con.print_info, print_fn_error=con.print_error,
                        logger=app_logger
                    )
                    con.print_success(f"Font cache refreshed successfully for user '{target_user}'.")
                    app_logger.info(f"Font cache refreshed for '{target_user}'.")
                except Exception as e_fc_cache:
                    con.print_warning(f"Failed to refresh font cache for user '{target_user}': {e_fc_cache}. You may need to run 'fc-cache -fv' manually as user '{target_user}'.")
                    app_logger.warning(f"fc-cache command failed for user '{target_user}': {e_fc_cache}", exc_info=True)
                    # Not necessarily a critical failure for overall_success of the phase if fonts installed.
            elif not nerd_fonts_to_install: # No fonts were configured
                 app_logger.info("No Nerd Fonts configured for installation.")
                 con.print_info("No Nerd Fonts listed for installation in Phase 2.")
            # If fonts_installed_this_run is False but nerd_fonts_to_install was not empty, means all font installs failed.
            # overall_success would already be False in that case.
        elif not nerd_fonts_to_install: # Explicitly log if no fonts were in config
            app_logger.info("No Nerd Fonts listed for installation in Phase 2 configuration.")
            con.print_info("No Nerd Fonts listed for installation in Phase 2.")


    # --- Phase Completion Summary ---
    if overall_success:
        con.print_success("Phase 2: Basic System Package Configuration completed successfully.")
        app_logger.info("Phase 2 completed successfully.")
    else:
        con.print_error("Phase 2: Basic System Package Configuration completed with errors. Please review the output and logs.")
        app_logger.error("Phase 2 completed with errors.")

    return overall_success