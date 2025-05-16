# Fedora-AutoEnv-Setup/scripts/phase5_nvidia_installation.py

import subprocess
import sys
import time
from pathlib import Path

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils

# --- Helper Functions ---

def _check_kernel_updated(pre_update_kernel: str) -> bool:
    """Checks if the current running kernel is different from a previous version."""
    try:
        current_kernel_proc = system_utils.run_command(
            ["uname", "-r"], capture_output=True, check=True, print_fn_info=con.print_info
        )
        current_kernel = current_kernel_proc.stdout.strip()
        return current_kernel != pre_update_kernel
    except Exception as e:
        con.print_warning(f"Could not determine current kernel version: {e}")
        return False # Assume not updated if check fails

def _is_nvidia_package_installed(package_name_part: str = "akmod-nvidia") -> bool:
    """Checks if any NVIDIA driver package (like akmod-nvidia or akmod-nvidia-open) is installed."""
    try:
        # rpm -qa will list all installed packages. Grep for the nvidia kernel module package.
        # We use check=False because grep returns 1 if not found, which is not an error here.
        # The command will look something like: rpm -qa | grep -E "akmod-nvidia(-open)?"
        # A more direct way is to query the specific packages we might install.
        
        # Check for standard proprietary drivers
        check_std_cmd = ["rpm", "-q", "akmod-nvidia"]
        std_proc = system_utils.run_command(check_std_cmd, capture_output=True, check=False, print_fn_info=con.print_info)
        if std_proc.returncode == 0:
            con.print_info(f"Standard NVIDIA driver package 'akmod-nvidia' seems to be installed.")
            return True

        # Check for open kernel module drivers
        check_open_cmd = ["rpm", "-q", "akmod-nvidia-open"]
        open_proc = system_utils.run_command(check_open_cmd, capture_output=True, check=False, print_fn_info=con.print_info)
        if open_proc.returncode == 0:
            con.print_info(f"Open NVIDIA driver package 'akmod-nvidia-open' seems to be installed.")
            return True
            
        # Could also add checks for xorg-x11-drv-nvidia if needed, but akmod is key.
        con.print_info("No primary NVIDIA akmod driver package (akmod-nvidia or akmod-nvidia-open) found.")
        return False
    except FileNotFoundError:
        con.print_warning("'rpm' command not found. Cannot check for existing NVIDIA drivers.")
        return False # Assume not installed if rpm is missing
    except Exception as e:
        con.print_warning(f"Error checking for NVIDIA driver packages: {e}")
        return False


def _enable_rpm_fusion_tainted_repo(phase_cfg: dict) -> bool:
    """Installs the RPM Fusion non-free tainted repository package if specified."""
    tainted_repo_pkg = phase_cfg.get("dnf_package_tainted_repo")
    if not tainted_repo_pkg:
        con.print_info("No RPM Fusion non-free tainted repository package specified in config. Skipping.")
        return True # Not an error if not specified

    con.print_sub_step(f"Ensuring RPM Fusion non-free tainted repository ('{tainted_repo_pkg}') is enabled...")
    try:
        # Check if already installed
        check_cmd = ["rpm", "-q", tainted_repo_pkg]
        check_proc = system_utils.run_command(check_cmd, capture_output=True, check=False, print_fn_info=con.print_info)
        if check_proc.returncode == 0:
            con.print_info(f"Package '{tainted_repo_pkg}' is already installed.")
            return True

        cmd = ["sudo", "dnf", "install", "-y", tainted_repo_pkg]
        system_utils.run_command(
            cmd, capture_output=True, check=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"RPM Fusion non-free tainted repository ('{tainted_repo_pkg}') enabled.")
        return True
    except FileNotFoundError:
        con.print_error("'rpm' or 'dnf' command not found. Cannot enable tainted repository.")
        return False
    except Exception: # Error already logged by run_command
        return False


def _install_standard_nvidia_drivers(phase_cfg: dict) -> bool:
    """Installs akmod-nvidia and xorg-x11-drv-nvidia-cuda if specified."""
    packages_to_install = phase_cfg.get("dnf_packages_standard", [])
    if not packages_to_install:
        con.print_info("No standard NVIDIA DNF packages specified in config. Skipping standard install.")
        return True

    # Check if a primary akmod package is already installed (e.g. -open variant)
    # to avoid conflicts or redundant operations if user switches between them.
    # For now, we rely on user choice and dnf's conflict resolution.
    # If we wanted to be smarter, we might `dnf remove akmod-nvidia-open` if installing `akmod-nvidia`.

    con.print_sub_step(f"Installing standard NVIDIA drivers: {', '.join(packages_to_install)}")
    try:
        cmd = ["sudo", "dnf", "install", "-y"] + packages_to_install
        system_utils.run_command(
            cmd, capture_output=True, check=True, # Use capture_output=False for long installs if preferred
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"Standard NVIDIA DNF packages ({', '.join(packages_to_install)}) installed.")
        return True
    except Exception: # Error already logged by run_command
        return False

def _swap_to_nvidia_open_drivers(phase_cfg: dict) -> bool:
    """Swaps standard NVIDIA drivers to open kernel module variant if specified."""
    swap_config = phase_cfg.get("dnf_swap_open_drivers")
    if not swap_config:
        con.print_info("No NVIDIA open driver swap configuration found. Skipping.")
        return True
    
    from_pkg = swap_config.get("from")
    to_pkg = swap_config.get("to")

    if not from_pkg or not to_pkg:
        con.print_error("Invalid 'from' or 'to' package in 'dnf_swap_open_drivers' config. Skipping.")
        return False

    con.print_sub_step(f"Attempting to swap DNF package '{from_pkg}' with NVIDIA open driver '{to_pkg}'...")
    try:
        # Check if the 'from_pkg' (e.g., akmod-nvidia) is installed.
        # If not, 'dnf swap' might fail or do something unexpected.
        # A direct install of 'to_pkg' might be better if 'from_pkg' isn't present.
        check_cmd = ["rpm", "-q", from_pkg]
        check_proc = system_utils.run_command(check_cmd, capture_output=True, check=False, print_fn_info=con.print_info)

        if check_proc.returncode != 0: # from_pkg is not installed
            con.print_info(f"Package '{from_pkg}' is not installed. Attempting direct install of '{to_pkg}'.")
            install_cmd = ["sudo", "dnf", "install", "-y", to_pkg]
            # If xorg-x11-drv-nvidia-cuda-open (or similar) is also desired, it should be part of 'to_pkg' definition or handled separately.
            # The config currently lists 'akmod-nvidia-open' as the target.
            system_utils.run_command(install_cmd, capture_output=True, check=True, print_fn_info=con.print_info, print_fn_error=con.print_error)
            con.print_success(f"NVIDIA open driver '{to_pkg}' installed directly.")
            return True

        # If 'from_pkg' is installed, proceed with swap
        swap_cmd = ["sudo", "dnf", "swap", "-y", from_pkg, to_pkg]
        system_utils.run_command(
            swap_cmd, capture_output=True, check=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success(f"DNF package '{from_pkg}' successfully swapped with '{to_pkg}'.")
        return True
    except Exception: 
        con.print_warning(f"Failed to swap '{from_pkg}' with '{to_pkg}'. This might be due to '{to_pkg}' not being available or conflicts.")
        return False

# --- Main Phase Function ---

def run_phase5(app_config: dict) -> bool:
    """Executes Phase 5: NVIDIA Driver Installation."""
    con.print_step("PHASE 5: NVIDIA Driver Installation")
    
    phase5_config = config_loader.get_phase_data(app_config, "phase5_nvidia_installation")
    if not phase5_config:
        con.print_warning("No configuration found for Phase 5. Skipping NVIDIA driver installation.")
        return True # No config means nothing to do, technically success.

    # 0. User Confirmation
    con.print_panel(
        "[bold yellow]WARNING:[/] This phase will attempt to install NVIDIA proprietary drivers. \n"
        "Ensure you have a [bold]compatible NVIDIA GPU[/] (GT/GTX 600 series or newer, RTX series).\n"
        "Installing these drivers on unsupported hardware or in a VM without GPU passthrough can lead to a non-bootable system or display issues.",
        title="NVIDIA Driver Installation Notice",
        style="yellow"
    )
    if not con.confirm_action("Do you have a compatible NVIDIA GPU and wish to proceed with driver installation?", default=False):
        con.print_info("NVIDIA driver installation skipped by user.")
        return True # User chose not to proceed, not a script failure.

    # Check if NVIDIA drivers (akmod) seem to be already installed
    if _is_nvidia_package_installed():
        if not con.confirm_action(
            "NVIDIA akmod drivers seem to be already installed. Do you want to attempt re-installation or configuration steps anyway?",
            default=False
        ):
            con.print_info("Skipping NVIDIA driver installation as they appear to be already installed and user chose not to proceed further.")
            return True

    # 1. System Update and Reboot Check
    con.print_info("\nStep 1: Ensuring system is up-to-date for kernel compatibility...")
    try:
        kernel_before_update_proc = system_utils.run_command(
            ["uname", "-r"], capture_output=True, check=True, print_fn_info=con.print_info
        )
        kernel_before_update = kernel_before_update_proc.stdout.strip()

        con.print_sub_step("Running 'sudo dnf update -y' to update system and kernel...")
        system_utils.run_command(
            ["sudo", "dnf", "update", "-y"], # 'dnf upgrade' is alias for 'dnf update --obsoletes'
            capture_output=False, # Let user see DNF output
            check=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error
        )
        con.print_success("System update command completed.")

        if _check_kernel_updated(kernel_before_update):
            con.print_warning(
                "The kernel was updated. A system REBOOT is REQUIRED before installing NVIDIA drivers "
                "to ensure the new kernel is active."
            )
            if con.confirm_action("Do you want to stop here to reboot your system now?", default=True):
                con.print_info("Halting Phase 5. Please reboot your system and then re-run this phase.")
                return False # Indicate phase did not complete, needs user action (reboot)
            else:
                con.print_warning("Proceeding without reboot after kernel update. This is NOT RECOMMENDED and may lead to issues.")
        else:
            con.print_info("Kernel does not appear to have been updated. No immediate reboot necessary for kernel reasons.")

    except Exception as e:
        con.print_error(f"System update step failed: {e}. Cannot safely proceed with NVIDIA driver installation.")
        return False

    # 2. Enable RPM Fusion Non-Free Tainted Repo (if specified)
    con.print_info("\nStep 2: Enabling RPM Fusion Non-Free Tainted Repository (if configured)...")
    if not _enable_rpm_fusion_tainted_repo(phase5_config):
        # This might not be strictly critical if the main drivers don't need it,
        # but some features (like CUDA in some cases, or specific firmware) might.
        con.print_warning("Could not enable RPM Fusion non-free tainted repository. Some NVIDIA features might be unavailable.")
        # overall_success might be set to False here if tainted repo is deemed critical
    
    # 3. Choose driver type: Standard Proprietary or Open Kernel Modules
    con.print_info("\nStep 3: Selecting NVIDIA Driver Type...")
    driver_choice = ""
    if phase5_config.get("dnf_packages_standard") and phase5_config.get("dnf_swap_open_drivers"):
        choices = {
            "1": "Standard Proprietary Drivers (Recommended for most users)",
            "2": "Open Kernel Module Drivers (Experimental, newer GPUs)"
        }
        con.print_info("Multiple NVIDIA driver options available:")
        for key, desc in choices.items():
            con.print_info(f"  {key}. {desc}")
        
        user_choice_num = con.ask_question("Select driver type to install:", choices=list(choices.keys()), default="1")
        if user_choice_num == "1":
            driver_choice = "standard"
        elif user_choice_num == "2":
            driver_choice = "open"
    elif phase5_config.get("dnf_packages_standard"):
        con.print_info("Configured to install Standard Proprietary NVIDIA drivers.")
        driver_choice = "standard"
    elif phase5_config.get("dnf_swap_open_drivers") and phase5_config.get("dnf_swap_open_drivers").get("to"):
        # If only open drivers are configured (e.g., by having a 'to' package for swap, implying 'open')
        con.print_info(f"Configured to install/swap to NVIDIA Open Kernel Module drivers ('{phase5_config['dnf_swap_open_drivers'].get('to')}').")
        driver_choice = "open_direct_install_or_swap" # Special handling for this case
    else:
        con.print_error("No valid NVIDIA driver installation options found in configuration.")
        return False

    installation_done = False
    if driver_choice == "standard":
        if _install_standard_nvidia_drivers(phase5_config):
            installation_done = True
        else:
            con.print_error("Failed to install standard NVIDIA drivers.")
            return False
    elif driver_choice == "open":
        if _swap_to_nvidia_open_drivers(phase5_config): # This handles swap or direct install of open
            installation_done = True
        else:
            con.print_error("Failed to install/swap to NVIDIA open kernel module drivers.")
            return False
    elif driver_choice == "open_direct_install_or_swap":
        # This case implies only 'dnf_swap_open_drivers' was configured, primarily its 'to' field.
        # The _swap_to_nvidia_open_drivers function will handle direct install if 'from' is not present.
        if _swap_to_nvidia_open_drivers(phase5_config):
             installation_done = True
        else:
            con.print_error("Failed to install NVIDIA open kernel module drivers (direct/swap).")
            return False
    else:
        con.print_error("Invalid driver choice or configuration. Aborting NVIDIA driver installation.")
        return False

    # 4. Post-installation steps
    if installation_done:
        con.print_info("\nStep 4: Post-installation procedures...")
        con.print_warning(
            "NVIDIA drivers have been installed. Kernel modules now need to be built. "
            "This process can take 5-15 minutes."
        )
        con.print_info("Please WAIT for at least 5-10 minutes before rebooting.")
        
        # Simulate a short wait or give user option to wait here
        if con.confirm_action("Do you want this script to pause for 5 minutes to allow kmod build time?", default=True):
            con.print_info("Pausing for 5 minutes...")
            for i in range(5 * 60, 0, -1):
                mins, secs = divmod(i, 60)
                con.console.print(f"  Waiting... {mins:02d}:{secs:02d} remaining", end="\r")
                time.sleep(1)
            con.console.print("  Pause complete.                                 ")


        con.print_info("\nAfter waiting, you can optionally check if the kernel module is built by running:")
        con.print_info("  modinfo -F version nvidia")
        con.print_info("If this command outputs a version number, the module is likely built.")
        con.print_info("If it shows an error, you might need to wait longer or troubleshoot.")

        con.print_step("IMPORTANT: REBOOT REQUIRED", char="!")
        con.print_warning("A system REBOOT is REQUIRED to load the new NVIDIA drivers and complete the installation.")
        con.print_info("Please save all your work and reboot your system.")
        
        # We don't actually reboot here, just inform.
        # The phase is "successful" in terms of script execution up to this point.
        # The user is responsible for the reboot.
        con.print_success("Phase 5: NVIDIA Driver Installation tasks completed. Please REBOOT your system.")
        return True # Phase considered "complete" from script's perspective
    
    # Should not be reached if installation_done is False and returns were hit
    con.print_error("Phase 5: NVIDIA Driver Installation failed at an unexpected point.")
    return False