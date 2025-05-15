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

def _install_dnf_packages(packages: list[str]) -> bool:
    """Installs a list of DNF packages."""
    if not packages:
        con.print_info("No DNF packages specified for this sub-task.")
        return True

    con.print_sub_step(f"Installing DNF packages: {', '.join(packages)}")
    try:
        cmd = ["sudo", "dnf", "install", "-y"] + packages
        system_utils.run_command(
            cmd, capture_output=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"DNF packages installed: {', '.join(packages)}")
        return True
    except Exception: # Error already logged by run_command
        return False

def _install_dnf_groups(groups: list[str], group_type_name: str) -> bool:
    """Installs a list of DNF groups."""
    if not groups:
        con.print_info(f"No DNF {group_type_name} groups specified for installation.")
        return True

    con.print_sub_step(f"Installing DNF {group_type_name} groups: {', '.join(groups)}")
    all_successful = True
    for group in groups:
        try:
            cmd = ["sudo", "dnf", "group", "install", "-y", group]
            system_utils.run_command(
                cmd, capture_output=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
            )
            con.print_success(f"DNF group '{group}' installed successfully.")
        except Exception:
            # Error for this specific group already logged by run_command
            all_successful = False
    return all_successful

def _swap_dnf_package(from_pkg: str, to_pkg: str) -> bool:
    """Swaps one DNF package for another."""
    if not from_pkg or not to_pkg:
        con.print_error("Invalid 'from' or 'to' package name for DNF swap.")
        return False

    con.print_sub_step(f"Attempting to swap DNF package '{from_pkg}' with '{to_pkg}'...")
    try:
        # Check if the 'from' package is installed
        check_cmd = ["rpm", "-q", from_pkg]
        # check=False as it's okay if not installed (rpm returns non-zero)
        check_proc = system_utils.run_command(
            check_cmd, capture_output=True, check=False, print_fn_info=con.print_info
        )

        if check_proc.returncode != 0: # from_pkg is not installed
            con.print_info(f"Package '{from_pkg}' is not installed. Attempting direct install of '{to_pkg}'.")
            return _install_dnf_packages([to_pkg]) # Try to install the target package directly

        # If 'from_pkg' is installed, proceed with swap
        swap_cmd = ["sudo", "dnf", "swap", "-y", from_pkg, to_pkg]
        system_utils.run_command(
            swap_cmd, capture_output=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"DNF package '{from_pkg}' successfully swapped with '{to_pkg}'.")
        return True
    except Exception: 
        # Error already logged by run_command or _install_dnf_packages
        con.print_warning(f"Failed to swap '{from_pkg}' with '{to_pkg}'. This might be due to '{to_pkg}' not being available in the currently configured repositories.")
        return False

def _handle_multimedia_group_operations(opts: dict, group_name_key: str = "group", operation: str = "upgrade") -> bool:
    """Handles DNF group operations (e.g., upgrade) with specific options from config."""
    group_name = opts.get(group_name_key)
    if not group_name:
        con.print_error(f"Missing '{group_name_key}' in DNF multimedia options configuration.")
        return False

    con.print_sub_step(f"Performing DNF group {operation} on '{group_name}' with custom options...")
    cmd = ["sudo", "dnf", "group", operation, "-y"]

    setopt_val = opts.get("setopt")
    if setopt_val:
        # Ensure it's correctly formatted as --setopt=key=value
        if not str(setopt_val).startswith("--setopt="):
            setopt_val = f"--setopt={setopt_val}"
        cmd.append(str(setopt_val))

    exclude_val = opts.get("exclude")
    if exclude_val:
        # Ensure it's correctly formatted as --exclude=PackageName
        if not str(exclude_val).startswith("--exclude="):
            exclude_val = f"--exclude={exclude_val}"
        cmd.append(str(exclude_val))
    
    cmd.append(group_name) # The group name itself (e.g., "@multimedia")

    try:
        system_utils.run_command(
            cmd, capture_output=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"DNF group {operation} on '{group_name}' completed successfully.")
        return True
    except Exception: # Error already logged by run_command
        return False

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
        if not _install_dnf_packages(dnf_packages_to_install):
            overall_success = False
            con.print_error("Failed to install some general DNF packages. See details above.")
    else:
        con.print_info("No general DNF packages listed for installation in Phase 2.")

    # 2. Handle Media Codec specific configurations
    con.print_info("\nStep 2: Configuring Media Codecs...")

    # 2a. Install dnf_groups_multimedia (e.g., "multimedia" group)
    multimedia_groups = phase2_config.get("dnf_groups_multimedia", [])
    if multimedia_groups:
        if not _install_dnf_groups(multimedia_groups, "multimedia support"):
            overall_success = False # Mark failure if any group install fails
    
    # 2b. Perform dnf_swap_ffmpeg (e.g., ffmpeg-free to ffmpeg)
    ffmpeg_swap_config = phase2_config.get("dnf_swap_ffmpeg")
    if ffmpeg_swap_config:
        from_pkg = ffmpeg_swap_config.get("from")
        to_pkg = ffmpeg_swap_config.get("to")
        if from_pkg and to_pkg:
            if not _swap_dnf_package(from_pkg, to_pkg):
                overall_success = False # Mark failure if swap fails
        else:
            con.print_warning("Incomplete 'dnf_swap_ffmpeg' configuration in YAML. Skipping swap.")
            # overall_success = False # Consider if this is a critical config error

    # 2c. Handle dnf_multimedia_upgrade_opts (e.g., upgrade @multimedia with options)
    multimedia_opts_config = phase2_config.get("dnf_multimedia_upgrade_opts")
    if multimedia_opts_config:
        if not _handle_multimedia_group_operations(multimedia_opts_config, operation="upgrade"):
            overall_success = False # Mark failure if this operation fails
            
    # 2d. Install dnf_groups_sound_video (e.g., "sound-and-video" group)
    sound_video_groups = phase2_config.get("dnf_groups_sound_video", [])
    if sound_video_groups:
        if not _install_dnf_groups(sound_video_groups, "sound and video support"):
            overall_success = False # Mark failure if any group install fails

    if overall_success:
        con.print_success("Phase 2: Basic System Package Configuration completed successfully.")
    else:
        con.print_error("Phase 2: Basic System Package Configuration completed with errors. Please review the output.")
    
    return overall_success