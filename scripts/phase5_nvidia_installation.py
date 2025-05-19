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
from scripts.logger_utils import app_logger

# --- Helper Functions ---

def _check_kernel_updated(pre_update_kernel: str) -> bool:
    """Checks if the current running kernel is different from a previous version."""
    app_logger.debug(f"Checking if kernel updated from {pre_update_kernel}.")
    try:
        current_kernel_proc = system_utils.run_command(
            ["uname", "-r"], capture_output=True, check=True, 
            print_fn_info=con.print_info, logger=app_logger
        )
        current_kernel = current_kernel_proc.stdout.strip()
        app_logger.info(f"Current kernel: {current_kernel}, Previous: {pre_update_kernel}")
        return current_kernel != pre_update_kernel
    except Exception as e:
        con.print_warning(f"Could not determine current kernel version: {e}")
        app_logger.warning(f"Could not determine current kernel: {e}", exc_info=True)
        return False 

def _is_nvidia_package_installed(package_name_part: str = "akmod-nvidia") -> bool:
    """Checks if any NVIDIA driver package (like akmod-nvidia or akmod-nvidia-open) is installed."""
    app_logger.debug(f"Checking if NVIDIA package like '{package_name_part}' is installed.")
    try:
        # Check for standard akmod-nvidia
        std_proc = system_utils.run_command(
            ["rpm", "-q", "akmod-nvidia"], capture_output=True, check=False, 
            print_fn_info=None, logger=app_logger 
        )
        if std_proc.returncode == 0:
            con.print_info("Standard NVIDIA driver package 'akmod-nvidia' seems to be installed.")
            app_logger.info("'akmod-nvidia' found.")
            return True

        # Check for open akmod-nvidia
        open_proc = system_utils.run_command(
            ["rpm", "-q", "akmod-nvidia-open"], capture_output=True, check=False, 
            print_fn_info=None, logger=app_logger
        )
        if open_proc.returncode == 0:
            con.print_info("Open NVIDIA driver package 'akmod-nvidia-open' seems to be installed.")
            app_logger.info("'akmod-nvidia-open' found.")
            return True
            
        con.print_info("No primary NVIDIA akmod driver package (akmod-nvidia or akmod-nvidia-open) found.")
        app_logger.info("No primary NVIDIA akmod packages found.")
        return False
    except FileNotFoundError:
        con.print_warning("'rpm' command not found. Cannot check for existing NVIDIA drivers.")
        app_logger.warning("'rpm' not found, cannot check NVIDIA drivers.")
        return False 
    except Exception as e:
        con.print_warning(f"Error checking for NVIDIA driver packages: {e}")
        app_logger.warning(f"Error checking NVIDIA drivers: {e}", exc_info=True)
        return False


def _enable_rpm_fusion_tainted_repo(phase_cfg: dict) -> bool:
    """Installs the RPM Fusion non-free tainted repository package if specified."""
    tainted_repo_pkg = phase_cfg.get("dnf_package_tainted_repo")
    if not tainted_repo_pkg:
        con.print_info("No RPM Fusion non-free tainted repository package specified in config. Skipping.")
        app_logger.info("No tainted repo package in config. Skipping.")
        return True 

    app_logger.info(f"Ensuring RPM Fusion tainted repo '{tainted_repo_pkg}' is enabled.")
    # con.print_sub_step(f"Ensuring RPM Fusion non-free tainted repository ('{tainted_repo_pkg}') is enabled...") # Handled by install_dnf_packages

    try:
        check_proc = system_utils.run_command(
            ["rpm", "-q", tainted_repo_pkg], capture_output=True, check=False, 
            print_fn_info=None, logger=app_logger
        )
        if check_proc.returncode == 0:
            con.print_info(f"Package '{tainted_repo_pkg}' is already installed.")
            app_logger.info(f"Tainted repo package '{tainted_repo_pkg}' already installed.")
            return True

        if system_utils.install_dnf_packages(
            [tainted_repo_pkg],
            print_fn_info=con.print_info, print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step, logger=app_logger
        ):
            con.print_success(f"RPM Fusion non-free tainted repository ('{tainted_repo_pkg}') enabled.")
            app_logger.info(f"Enabled RPM Fusion tainted repo '{tainted_repo_pkg}'.")
            return True
        else:
            # Error already printed by install_dnf_packages
            app_logger.error(f"Failed to enable tainted repo '{tainted_repo_pkg}'.")
            return False
            
    except FileNotFoundError:
        con.print_error("'rpm' command not found. Cannot check or enable tainted repository.")
        app_logger.error("'rpm' not found, cannot enable tainted repo.")
        return False
    except Exception as e: # Catch any other unexpected errors
        app_logger.error(f"Unexpected error enabling tainted repo '{tainted_repo_pkg}': {e}", exc_info=True)
        con.print_error(f"Unexpected error enabling tainted repo '{tainted_repo_pkg}'.")
        return False


def _install_standard_nvidia_drivers(phase_cfg: dict) -> bool:
    """Installs akmod-nvidia and xorg-x11-drv-nvidia-cuda if specified."""
    packages_to_install = phase_cfg.get("dnf_packages_standard", [])
    if not packages_to_install:
        con.print_info("No standard NVIDIA DNF packages specified in config. Skipping standard install.")
        app_logger.info("No standard NVIDIA packages in config. Skipping.")
        return True

    # con.print_sub_step(f"Installing standard NVIDIA drivers: {', '.join(packages_to_install)}") # Handled by install_dnf_packages
    if system_utils.install_dnf_packages(
        packages_to_install,
        print_fn_info=con.print_info, print_fn_error=con.print_error,
        print_fn_sub_step=con.print_sub_step, logger=app_logger
    ):
        # con.print_success(f"Standard NVIDIA DNF packages ({', '.join(packages_to_install)}) installed.") # Handled by install_dnf_packages
        app_logger.info(f"Installed standard NVIDIA packages: {packages_to_install}")
        return True
    else:
        app_logger.error(f"Failed to install standard NVIDIA packages: {packages_to_install}")
        return False

def _swap_to_nvidia_open_drivers(phase_cfg: dict) -> bool:
    """Swaps standard NVIDIA drivers to open kernel module variant if specified."""
    swap_config = phase_cfg.get("dnf_swap_open_drivers")
    if not swap_config:
        con.print_info("No NVIDIA open driver swap configuration found. Skipping.")
        app_logger.info("No NVIDIA open driver swap config. Skipping.")
        return True
    
    from_pkg = swap_config.get("from")
    to_pkg = swap_config.get("to")

    if not from_pkg or not to_pkg:
        con.print_error("Invalid 'from' or 'to' package in 'dnf_swap_open_drivers' config. Skipping.")
        app_logger.error(f"Invalid from/to for open driver swap: from='{from_pkg}', to='{to_pkg}'.")
        return False

    # con.print_sub_step(f"Attempting to swap DNF package '{from_pkg}' with NVIDIA open driver '{to_pkg}'...") # Handled by swap_dnf_packages
    if system_utils.swap_dnf_packages(
        from_pkg, to_pkg,
        print_fn_info=con.print_info, print_fn_error=con.print_error,
        print_fn_sub_step=con.print_sub_step, logger=app_logger
    ):
        # con.print_success(f"DNF package '{from_pkg}' successfully swapped with '{to_pkg}'.") # Handled by swap_dnf_packages
        app_logger.info(f"Swapped '{from_pkg}' with '{to_pkg}'.")
        return True
    else:
        # Error handled by swap_dnf_packages
        con.print_warning(f"Failed to swap '{from_pkg}' with '{to_pkg}'. This might be due to '{to_pkg}' not being available or conflicts.")
        app_logger.error(f"Failed to swap '{from_pkg}' with '{to_pkg}'.")
        return False

# --- Main Phase Function ---

def run_phase5(app_config: dict) -> bool:
    """Executes Phase 5: NVIDIA Driver Installation."""
    app_logger.info("Starting Phase 5: NVIDIA Driver Installation.")
    con.print_step("PHASE 5: NVIDIA Driver Installation")
    
    phase5_config = config_loader.get_phase_data(app_config, "phase5_nvidia_installation")
    if not phase5_config:
        con.print_warning("No configuration found for Phase 5. Skipping NVIDIA driver installation.")
        app_logger.warning("No Phase 5 config. Skipping.")
        return True 

    con.print_panel(
        "[bold yellow]WARNING:[/] This phase will attempt to install NVIDIA proprietary drivers. \n"
        "Ensure you have a [bold]compatible NVIDIA GPU[/] (GT/GTX 600 series or newer, RTX series).\n"
        "Installing these drivers on unsupported hardware or in a VM without GPU passthrough can lead to a non-bootable system or display issues.",
        title="NVIDIA Driver Installation Notice",
        style="yellow"
    )
    if not con.confirm_action("Do you have a compatible NVIDIA GPU and wish to proceed with driver installation?", default=False):
        con.print_info("NVIDIA driver installation skipped by user.")
        app_logger.info("NVIDIA driver installation skipped by user confirmation.")
        return True 

    if _is_nvidia_package_installed():
        if not con.confirm_action(
            "NVIDIA akmod drivers seem to be already installed. Do you want to attempt re-installation or configuration steps anyway?",
            default=False
        ):
            con.print_info("Skipping NVIDIA driver installation as they appear to be already installed and user chose not to proceed further.")
            app_logger.info("NVIDIA drivers already installed, user skipped further steps.")
            return True

    con.print_info("\nStep 1: Ensuring system is up-to-date for kernel compatibility...")
    app_logger.info("Phase 5, Step 1: System update check.")
    try:
        kernel_before_update_proc = system_utils.run_command(
            ["uname", "-r"], capture_output=True, check=True, 
            print_fn_info=con.print_info, logger=app_logger
        )
        kernel_before_update = kernel_before_update_proc.stdout.strip()
        app_logger.info(f"Kernel before update attempt: {kernel_before_update}")

        con.print_sub_step("Running 'sudo dnf update -y' to update system and kernel...")
        if not system_utils.upgrade_system_dnf(
            print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger
            # capture_output=False is default in upgrade_system_dnf
        ):
            con.print_error("System update command failed. Cannot safely proceed.") # upgrade_system_dnf also prints error
            return False
        
        # con.print_success("System update command completed.") # upgrade_system_dnf handles success message
        app_logger.info("DNF update command completed.")

        if _check_kernel_updated(kernel_before_update):
            con.print_warning(
                "The kernel was updated. A system REBOOT is REQUIRED before installing NVIDIA drivers "
                "to ensure the new kernel is active."
            )
            app_logger.warning("Kernel was updated. Reboot required.")
            if con.confirm_action("Do you want to stop here to reboot your system now?", default=True):
                con.print_info("Halting Phase 5. Please reboot your system and then re-run this phase.")
                app_logger.info("User chose to halt for reboot after kernel update.")
                return False 
            else:
                con.print_warning("Proceeding without reboot after kernel update. This is NOT RECOMMENDED and may lead to issues.")
                app_logger.warning("User chose to proceed without reboot after kernel update (NOT RECOMMENDED).")
        else:
            con.print_info("Kernel does not appear to have been updated. No immediate reboot necessary for kernel reasons.")
            app_logger.info("Kernel does not appear to have been updated.")

    except Exception as e: # Catch unexpected errors during the update check logic itself
        con.print_error(f"System update step encountered an unexpected issue: {e}. Cannot safely proceed with NVIDIA driver installation.")
        app_logger.error(f"System update step unexpected error: {e}", exc_info=True)
        return False

    con.print_info("\nStep 2: Enabling RPM Fusion Non-Free Tainted Repository (if configured)...")
    app_logger.info("Phase 5, Step 2: Enabling RPM Fusion tainted repo.")
    if not _enable_rpm_fusion_tainted_repo(phase5_config):
        con.print_warning("Could not enable RPM Fusion non-free tainted repository. Some NVIDIA features might be unavailable.")
        app_logger.warning("Failed to enable RPM Fusion tainted repo. Continuing, but some features might be unavailable.")
    
    con.print_info("\nStep 3: Selecting NVIDIA Driver Type...")
    app_logger.info("Phase 5, Step 3: Selecting NVIDIA driver type.")
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
        app_logger.info(f"User chose driver type: {driver_choice} ({user_choice_num})")
    elif phase5_config.get("dnf_packages_standard"):
        con.print_info("Configured to install Standard Proprietary NVIDIA drivers.")
        driver_choice = "standard"
        app_logger.info("Defaulting to standard proprietary drivers based on config.")
    elif phase5_config.get("dnf_swap_open_drivers") and phase5_config.get("dnf_swap_open_drivers").get("to"):
        to_pkg_open = phase5_config['dnf_swap_open_drivers'].get('to')
        con.print_info(f"Configured to install/swap to NVIDIA Open Kernel Module drivers ('{to_pkg_open}').")
        driver_choice = "open_direct_install_or_swap" 
        app_logger.info(f"Defaulting to open kernel module drivers ('{to_pkg_open}') based on config.")
    else:
        con.print_error("No valid NVIDIA driver installation options found in configuration.")
        app_logger.error("No valid NVIDIA driver installation options in config.")
        return False

    installation_done = False
    if driver_choice == "standard":
        if _install_standard_nvidia_drivers(phase5_config):
            installation_done = True
        else:
            con.print_error("Failed to install standard NVIDIA drivers.")
            app_logger.error("Standard NVIDIA driver installation failed.")
            return False
    elif driver_choice == "open":
        if _swap_to_nvidia_open_drivers(phase5_config): 
            installation_done = True
        else:
            con.print_error("Failed to install/swap to NVIDIA open kernel module drivers.")
            app_logger.error("NVIDIA open kernel module driver swap/install failed.")
            return False
    elif driver_choice == "open_direct_install_or_swap":
        if _swap_to_nvidia_open_drivers(phase5_config):
             installation_done = True
        else:
            con.print_error("Failed to install NVIDIA open kernel module drivers (direct/swap).")
            app_logger.error("NVIDIA open kernel module driver (direct/swap) failed.")
            return False
    else:
        con.print_error("Invalid driver choice or configuration. Aborting NVIDIA driver installation.")
        app_logger.error(f"Invalid driver_choice '{driver_choice}'. Aborting.")
        return False

    if installation_done:
        app_logger.info("NVIDIA driver DNF operations completed.")
        con.print_info("\nStep 4: Post-installation procedures...")
        con.print_warning(
            "NVIDIA drivers have been installed. Kernel modules now need to be built. "
            "This process can take 5-15 minutes."
        )
        con.print_info("Please WAIT for at least 5-10 minutes before rebooting.")
        
        if con.confirm_action("Do you want this script to pause for 5 minutes to allow kmod build time?", default=True):
            con.print_info("Pausing for 5 minutes...")
            app_logger.info("Pausing for 5 minutes for kmod build.")
            for i in range(5 * 60, 0, -1):
                mins, secs = divmod(i, 60)
                con.console.print(f"  Waiting... {mins:02d}:{secs:02d} remaining", end="\r")
                time.sleep(1)
            con.console.print("  Pause complete.                                 ")
            app_logger.info("Pause complete.")


        con.print_info("\nAfter waiting, you can optionally check if the kernel module is built by running:")
        con.print_info("  modinfo -F version nvidia")
        con.print_info("If this command outputs a version number, the module is likely built.")
        con.print_info("If it shows an error, you might need to wait longer or troubleshoot.")

        con.print_step("IMPORTANT: REBOOT REQUIRED", char="!")
        con.print_warning("A system REBOOT is REQUIRED to load the new NVIDIA drivers and complete the installation.")
        con.print_info("Please save all your work and reboot your system.")
        
        con.print_success("Phase 5: NVIDIA Driver Installation tasks completed. Please REBOOT your system.")
        app_logger.info("Phase 5 completed successfully. User informed to reboot.")
        return True 
    
    app_logger.error("Phase 5 failed at an unexpected point (installation_done is False).")
    con.print_error("Phase 5: NVIDIA Driver Installation failed at an unexpected point.")
    return False