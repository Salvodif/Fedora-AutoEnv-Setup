# Fedora-AutoEnv-Setup/scripts/phase2_basic_installation.py

import subprocess # Retained for CalledProcessError if system_utils re-raises it
import sys
from pathlib import Path

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils

# --- Phase Specific Functions ---

def _install_dnf_packages(packages: list[str], allow_erasing: bool = False) -> bool:
    """
    Installs a list of DNF packages.

    Args:
        packages (list[str]): A list of package names to install.
        allow_erasing (bool): If True, adds '--allowerasing' to the DNF command.

    Returns:
        bool: True if all packages were processed successfully, False otherwise.
    """
    if not packages:
        con.print_info("No DNF packages specified for this sub-task.")
        return True

    action_verb = "Installing"
    if allow_erasing:
        action_verb = "Installing (allowing erasing)"

    con.print_sub_step(f"{action_verb} DNF packages: {', '.join(packages)}")
    try:
        cmd = ["sudo", "dnf", "install", "-y"]
        if allow_erasing:
            cmd.append("--allowerasing") # Add flag if true
        cmd.extend(packages)
        
        system_utils.run_command(
            cmd, capture_output=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"DNF packages processed: {', '.join(packages)}")
        return True
    except Exception: # Error already logged by run_command
        # run_command will have printed detailed errors.
        # This function returning False will be caught by the main phase logic.
        return False

def _install_dnf_groups(groups: list[str], group_type_name: str) -> bool:
    """
    Installs a list of DNF groups.

    Args:
        groups (list[str]): A list of group IDs or names to install.
        group_type_name (str): A descriptive name for the type of groups being installed.

    Returns:
        bool: True if all groups were processed successfully, False otherwise.
    """
    if not groups:
        con.print_info(f"No DNF {group_type_name} groups specified for installation.")
        return True

    con.print_sub_step(f"Installing DNF {group_type_name} groups: {', '.join(groups)}")
    all_successful = True
    for group_id_or_name in groups:
        try:
            # Added --allowerasing for robustness, in case group packages conflict
            # or conflict with already installed packages.
            cmd = ["sudo", "dnf", "group", "install", "-y", "--allowerasing", group_id_or_name]
            system_utils.run_command(
                cmd, capture_output=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
            )
            con.print_success(f"DNF group '{group_id_or_name}' processed successfully.")
        except Exception:
            # Error for this specific group already logged by run_command
            con.print_error(f"Failed to process DNF group '{group_id_or_name}'.")
            all_successful = False
    return all_successful

def _swap_dnf_package(from_pkg: str, to_pkg: str) -> bool:
    """
    Swaps one DNF package for another, allowing erasing of conflicting packages.

    Args:
        from_pkg (str): The package name to swap from.
        to_pkg (str): The package name to swap to.

    Returns:
        bool: True if the swap was successful or `to_pkg` was installed directly, False otherwise.
    """
    if not from_pkg or not to_pkg:
        con.print_error("Invalid 'from' or 'to' package name for DNF swap.")
        return False

    con.print_sub_step(f"Attempting to swap DNF package '{from_pkg}' with '{to_pkg}' (allowing erasing)...")
    try:
        # Check if the 'from' package is installed
        check_cmd = ["rpm", "-q", from_pkg]
        # check=False as it's okay if not installed (rpm returns non-zero)
        check_proc = system_utils.run_command(
            check_cmd, capture_output=True, check=False, print_fn_info=con.print_info
        )

        if check_proc.returncode != 0: # from_pkg is not installed
            con.print_info(f"Package '{from_pkg}' is not installed. Attempting direct install of '{to_pkg}'.")
            # When installing directly, --allowerasing is also useful
            return _install_dnf_packages([to_pkg], allow_erasing=True)

        # If 'from_pkg' is installed, proceed with swap
        # Added --allowerasing to the swap command
        swap_cmd = ["sudo", "dnf", "swap", "-y", "--allowerasing", from_pkg, to_pkg]
        system_utils.run_command(
            swap_cmd, capture_output=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"DNF package '{from_pkg}' successfully swapped with '{to_pkg}'.")
        return True
    except Exception: 
        # Error already logged by run_command or _install_dnf_packages
        con.print_warning(f"Failed to swap '{from_pkg}' with '{to_pkg}'. This might be due to '{to_pkg}' not being available or unresolved conflicts even with --allowerasing.")
        return False

# The _handle_multimedia_group_operations function was removed as its corresponding
# YAML configuration 'dnf_multimedia_upgrade_opts' was removed.

# --- Main Phase Function ---

def run_phase2(app_config: dict) -> bool:
    """Executes Phase 2: Basic System Package Configuration."""
    con.print_step("PHASE 2: Basic System Package Configuration")
    overall_success = True
    
    phase2_config = config_loader.get_phase_data(app_config, "phase2_basic_configuration")
    if not phase2_config:
        con.print_warning("No configuration found for Phase 2. Skipping.")
        # No config means nothing to do, so technically not a failure of the phase itself.
        return True 

    # 1. Install general DNF packages
    con.print_info("Step 1: Installing general DNF packages...")
    dnf_packages_to_install = phase2_config.get("dnf_packages", [])
    if dnf_packages_to_install:
        # Using allow_erasing=True for general packages as well for robustness
        if not _install_dnf_packages(dnf_packages_to_install, allow_erasing=True):
            overall_success = False
            # _install_dnf_packages already logs errors
    else:
        con.print_info("No general DNF packages listed for installation in Phase 2.")

    # 2. Handle Media Codec specific configurations
    con.print_info("\nStep 2: Configuring Media Codecs...")

    # 2a. Logic for 'dnf_groups_multimedia' was removed as the group was problematic/non-existent.
    con.print_info("Skipping 'dnf_groups_multimedia' installation as it has been removed from the configuration workflow.")
    
    # 2b. Perform dnf_swap_ffmpeg (e.g., ffmpeg-free to ffmpeg) - RETAINED
    ffmpeg_swap_config = phase2_config.get("dnf_swap_ffmpeg")
    if ffmpeg_swap_config:
        from_pkg = ffmpeg_swap_config.get("from")
        to_pkg = ffmpeg_swap_config.get("to")
        if from_pkg and to_pkg:
            if not _swap_dnf_package(from_pkg, to_pkg): # Already updated with --allowerasing
                overall_success = False 
        else:
            con.print_warning("Incomplete 'dnf_swap_ffmpeg' configuration in YAML. Skipping swap.")
    else:
        con.print_info("No 'dnf_swap_ffmpeg' configuration found. Skipping ffmpeg swap.")


    # 2c. Logic for 'dnf_multimedia_upgrade_opts' was removed.
    con.print_info("Skipping 'dnf_multimedia_upgrade_opts' as it has been removed from the configuration workflow.")
            
    # 2d. Install dnf_groups_sound_video (e.g., "sound-and-video" group) - RETAINED
    # This assumes "sound-and-video" (or its equivalent from your YAML) is a valid group ID.
    sound_video_groups = phase2_config.get("dnf_groups_sound_video", [])
    if sound_video_groups:
        if not _install_dnf_groups(sound_video_groups, "sound and video support"): # _install_dnf_groups uses --allowerasing
            overall_success = False 
    else:
        con.print_info("No 'dnf_groups_sound_video' listed for installation.")


    if overall_success:
        con.print_success("Phase 2: Basic System Package Configuration completed successfully.")
    else:
        con.print_error("Phase 2: Basic System Package Configuration completed with errors. Please review the output.")
    
    return overall_success