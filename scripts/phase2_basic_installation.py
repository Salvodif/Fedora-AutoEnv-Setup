# Fedora-AutoEnv-Setup/scripts/phase2_basic_installation.py

import subprocess
import sys
import os # Added
from pathlib import Path
from typing import Optional, List # Added Optional, List

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils # Keep this general import
from scripts.logger_utils import app_logger # Added for specific logging

# --- Phase Specific Functions ---

def _install_dnf_packages(packages: list[str], allow_erasing: bool = False) -> bool:
    if not packages:
        con.print_info("No DNF packages specified for this sub-task.")
        app_logger.info("No DNF packages for this sub-task in _install_dnf_packages.")
        return True

    action_verb = "Installing"
    if allow_erasing:
        action_verb = "Installing (allowing erasing)"

    con.print_sub_step(f"{action_verb} DNF packages: {', '.join(packages)}")
    app_logger.info(f"{action_verb} DNF packages: {', '.join(packages)}")
    try:
        cmd = ["sudo", "dnf", "install", "-y"]
        if allow_erasing:
            cmd.append("--allowerasing")
        cmd.extend(packages)

        system_utils.run_command(
            cmd, capture_output=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step,
            logger=app_logger
        )
        con.print_success(f"DNF packages processed: {', '.join(packages)}")
        app_logger.info(f"DNF packages processed: {', '.join(packages)}")
        return True
    except Exception as e:
        app_logger.error(f"Failed to process DNF packages: {packages}. Error: {e}", exc_info=True)
        # Error already logged by run_command to console
        return False

def _run_zsh_newuser_install(target_user: str) -> bool:
    """Runs the zsh-newuser-install script for the target user."""
    con.print_sub_step(f"Running zsh-newuser-install for user '{target_user}'...")
    app_logger.info(f"Running zsh-newuser-install for user '{target_user}'.")

    # Command to be executed by zsh: autoload -U zsh-newuser-install, then zsh-newuser-install -f
    zsh_script_commands = "autoload -U zsh-newuser-install && zsh-newuser-install -f"
    # Wrap these commands to be executed by zsh itself
    full_command_for_user = f"zsh -c '{zsh_script_commands}'"

    try:
        system_utils.run_command(
            full_command_for_user,
            run_as_user=target_user,
            shell=True, # sudo -u user bash -c "zsh -c '...'"
            capture_output=True, # Capture output to check for errors
            check=True, # Raise exception on failure
            print_fn_info=con.print_info,
            print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step, # Can show output from zsh script
            logger=app_logger
        )
        con.print_success(f"zsh-newuser-install completed successfully for user '{target_user}'.")
        app_logger.info(f"zsh-newuser-install completed for user '{target_user}'.")
        return True
    except subprocess.CalledProcessError as e:
        # run_command already logs details
        con.print_error(f"zsh-newuser-install script failed for user '{target_user}'. Exit code: {e.returncode}.")
        app_logger.error(f"zsh-newuser-install script failed for '{target_user}'. Output: {e.output}, Stderr: {e.stderr}", exc_info=False)
        return False
    except Exception as e:
        con.print_error(f"An unexpected error occurred while running zsh-newuser-install for '{target_user}': {e}")
        app_logger.error(f"Unexpected error in zsh-newuser-install for '{target_user}'.", exc_info=True)
        return False

def _install_dnf_groups(groups: list[str], group_type_name: str) -> bool:
    if not groups:
        con.print_info(f"No DNF {group_type_name} groups specified for installation.")
        app_logger.info(f"No DNF {group_type_name} groups for installation.")
        return True

    con.print_sub_step(f"Installing DNF {group_type_name} groups: {', '.join(groups)}")
    app_logger.info(f"Installing DNF {group_type_name} groups: {', '.join(groups)}")
    all_successful = True
    for group_id_or_name in groups:
        try:
            cmd = ["sudo", "dnf", "group", "install", "-y", "--allowerasing", group_id_or_name]
            system_utils.run_command(
                cmd, capture_output=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step,
                logger=app_logger
            )
            con.print_success(f"DNF group '{group_id_or_name}' processed successfully.")
            app_logger.info(f"DNF group '{group_id_or_name}' processed successfully.")
        except Exception as e:
            app_logger.error(f"Failed to process DNF group '{group_id_or_name}'. Error: {e}", exc_info=True)
            all_successful = False
    return all_successful

def _swap_dnf_package(from_pkg: str, to_pkg: str) -> bool:
    if not from_pkg or not to_pkg:
        con.print_error("Invalid 'from' or 'to' package name for DNF swap.")
        app_logger.error(f"Invalid DNF swap params: from='{from_pkg}', to='{to_pkg}'")
        return False

    con.print_sub_step(f"Attempting to swap DNF package '{from_pkg}' with '{to_pkg}' (allowing erasing)...")
    app_logger.info(f"Attempting DNF swap: from '{from_pkg}' to '{to_pkg}'")
    try:
        check_cmd = ["rpm", "-q", from_pkg]
        check_proc = system_utils.run_command(
            check_cmd, capture_output=True, check=False, print_fn_info=con.print_info, logger=app_logger
        )

        if check_proc.returncode != 0:
            con.print_info(f"Package '{from_pkg}' is not installed. Attempting direct install of '{to_pkg}'.")
            app_logger.info(f"'{from_pkg}' not installed. Directly installing '{to_pkg}'.")
            return _install_dnf_packages([to_pkg], allow_erasing=True)

        swap_cmd = ["sudo", "dnf", "swap", "-y", "--allowerasing", from_pkg, to_pkg]
        system_utils.run_command(
            swap_cmd, capture_output=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step,
            logger=app_logger
        )
        con.print_success(f"DNF package '{from_pkg}' successfully swapped with '{to_pkg}'.")
        app_logger.info(f"Successfully swapped '{from_pkg}' with '{to_pkg}'.")
        return True
    except Exception as e:
        app_logger.error(f"Failed DNF swap from '{from_pkg}' to '{to_pkg}'. Error: {e}", exc_info=True)
        con.print_warning(f"Failed to swap '{from_pkg}' with '{to_pkg}'.")
        return False

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

    # 1. Install DNF packages, handling zsh specially
    con.print_info("Step 1: Installing general DNF packages...")
    app_logger.info("Phase 2, Step 1: Installing general DNF packages.")
    dnf_packages_from_config = phase2_config.get("dnf_packages", [])

    if dnf_packages_from_config:
        # Separate zsh from other packages
        packages_to_install_first = [pkg for pkg in dnf_packages_from_config if pkg.lower() != "zsh"]
        zsh_in_config = "zsh" in [pkg.lower() for pkg in dnf_packages_from_config]

        if packages_to_install_first:
            app_logger.info(f"Installing DNF packages (excluding zsh if present): {packages_to_install_first}")
            if not _install_dnf_packages(packages_to_install_first, allow_erasing=True):
                overall_success = False
                app_logger.error("Failed to install some initial DNF packages in Phase 2.")
        
        if zsh_in_config:
            if overall_success: # Only attempt zsh install if previous packages (if any) succeeded
                app_logger.info("Installing zsh separately.")
                if _install_dnf_packages(["zsh"], allow_erasing=True):
                    app_logger.info("zsh DNF package installed successfully.")
                    # Attempt to run zsh-newuser-install
                    target_user = system_utils.get_target_user(
                        logger=app_logger,
                        print_fn_info=con.print_info,
                        print_fn_error=con.print_error,
                        print_fn_warning=con.print_warning
                    )
                    if target_user:
                        if not _run_zsh_newuser_install(target_user):
                            # This is not critical enough to fail the whole phase, but good to warn.
                            con.print_warning("zsh-newuser-install script encountered issues. Zsh might prompt on first login.")
                            app_logger.warning("zsh-newuser-install script encountered issues for Phase 2.")
                    else:
                        con.print_warning("Could not determine target user for zsh-newuser-install in Phase 2. Skipping this step.")
                        app_logger.warning("Target user not found for zsh-newuser-install in Phase 2.")
                else:
                    overall_success = False # zsh DNF install failed
                    app_logger.error("Failed to install zsh DNF package in Phase 2.")
            else:
                con.print_warning("Skipping zsh installation and setup due to previous errors in Phase 2.")
                app_logger.warning("Skipping zsh installation and setup due to previous errors in Phase 2.")
    else:
        con.print_info("No general DNF packages listed for installation in Phase 2.")
        app_logger.info("No general DNF packages listed for Phase 2.")

    # 2. Handle Media Codec specific configurations
    con.print_info("\nStep 2: Configuring Media Codecs...")
    app_logger.info("Phase 2, Step 2: Configuring Media Codecs.")

    ffmpeg_swap_config = phase2_config.get("dnf_swap_ffmpeg")
    if ffmpeg_swap_config:
        from_pkg = ffmpeg_swap_config.get("from")
        to_pkg = ffmpeg_swap_config.get("to")
        if from_pkg and to_pkg:
            if not _swap_dnf_package(from_pkg, to_pkg):
                overall_success = False
        else:
            con.print_warning("Incomplete 'dnf_swap_ffmpeg' configuration. Skipping swap.")
            app_logger.warning("Incomplete 'dnf_swap_ffmpeg' config.")
    else:
        con.print_info("No 'dnf_swap_ffmpeg' configuration found. Skipping ffmpeg swap.")
        app_logger.info("No 'dnf_swap_ffmpeg' config.")

    sound_video_groups = phase2_config.get("dnf_groups_sound_video", [])
    if sound_video_groups:
        if not _install_dnf_groups(sound_video_groups, "sound and video support"):
            overall_success = False
    else:
        con.print_info("No 'dnf_groups_sound_video' listed for installation.")
        app_logger.info("No 'dnf_groups_sound_video' config.")

    if overall_success:
        con.print_success("Phase 2: Basic System Package Configuration completed successfully.")
        app_logger.info("Phase 2 completed successfully.")
    else:
        con.print_error("Phase 2: Basic System Package Configuration completed with errors. Please review the output.")
        app_logger.error("Phase 2 completed with errors.")

    return overall_success