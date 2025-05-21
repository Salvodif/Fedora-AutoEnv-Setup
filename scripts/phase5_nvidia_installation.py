# Fedora-AutoEnv-Setup/scripts/phase5_nvidia_installation.py

import subprocess # Retained for type hints if needed
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

def _check_kernel_updated(pre_update_kernel_version: str) -> bool:
    """Checks if the current running kernel is different from a previous version."""
    app_logger.debug(f"Checking if kernel updated from previous version: {pre_update_kernel_version}.")
    try:
        current_kernel_proc = system_utils.run_command(
            ["uname", "-r"], capture_output=True, check=True, 
            print_fn_info=None, # Quiet check for this internal helper
            logger=app_logger
        )
        current_kernel_version = current_kernel_proc.stdout.strip()
        app_logger.info(f"Current running kernel: {current_kernel_version}, Previous kernel before update attempt: {pre_update_kernel_version}")
        return current_kernel_version != pre_update_kernel_version
    except Exception as e:
        con.print_warning(f"Could not determine current kernel version to compare: {e}")
        app_logger.warning(f"Could not determine current kernel version: {e}", exc_info=True)
        return False # Assume not updated if check fails, to be safe

def _is_nvidia_driver_installed() -> bool:
    """
    Checks if any common NVIDIA driver package (akmod-nvidia or akmod-nvidia-open) is installed.
    Uses system_utils.is_package_installed_rpm.
    """
    app_logger.debug("Checking if NVIDIA akmod drivers (standard or open) are installed.")
    
    # Check for standard proprietary drivers
    if system_utils.is_package_installed_rpm("akmod-nvidia", logger=app_logger, print_fn_info=None): # Quiet check
        con.print_info("Standard NVIDIA driver package 'akmod-nvidia' appears to be installed.")
        app_logger.info("'akmod-nvidia' RPM package found.")
        return True
        
    # Check for open kernel module drivers
    if system_utils.is_package_installed_rpm("akmod-nvidia-open", logger=app_logger, print_fn_info=None): # Quiet check
        con.print_info("Open NVIDIA driver package 'akmod-nvidia-open' appears to be installed.")
        app_logger.info("'akmod-nvidia-open' RPM package found.")
        return True
    
    # If neither is found
    con.print_info("No primary NVIDIA akmod driver packages (akmod-nvidia or akmod-nvidia-open) found.")
    app_logger.info("No primary NVIDIA akmod RPM packages found by _is_nvidia_driver_installed helper.")
    return False


def _enable_rpm_fusion_tainted_repo(phase_config: dict) -> bool:
    """Installs the RPM Fusion non-free tainted repository package if specified in phase_config."""
    tainted_repo_pkg_name = phase_config.get("dnf_package_tainted_repo")
    if not tainted_repo_pkg_name:
        con.print_info("No RPM Fusion non-free tainted repository package specified in configuration. Skipping this step.")
        app_logger.info("No 'dnf_package_tainted_repo' in Phase 5 config. Skipping tainted repo enablement.")
        return True # Successfully skipped

    app_logger.info(f"Ensuring RPM Fusion non-free tainted repository ('{tainted_repo_pkg_name}') is enabled.")
    # con.print_sub_step is handled by install_dnf_packages if installation is needed

    try:
        if system_utils.is_package_installed_rpm(tainted_repo_pkg_name, logger=app_logger, print_fn_info=None): # Quiet check
            con.print_info(f"RPM Fusion non-free tainted repository package '{tainted_repo_pkg_name}' is already installed.")
            app_logger.info(f"Tainted repo package '{tainted_repo_pkg_name}' already installed.")
            return True

        # If not installed, attempt to install it
        con.print_info(f"Attempting to install RPM Fusion non-free tainted repository package: {tainted_repo_pkg_name}")
        if system_utils.install_dnf_packages(
            [tainted_repo_pkg_name], # Must be a list
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step, 
            logger=app_logger
        ):
            # install_dnf_packages prints its own success for the batch
            app_logger.info(f"Successfully enabled RPM Fusion non-free tainted repository by installing '{tainted_repo_pkg_name}'.")
            return True
        else:
            # Error already printed by install_dnf_packages
            app_logger.error(f"Failed to enable RPM Fusion non-free tainted repository by installing '{tainted_repo_pkg_name}'.")
            return False
            
    except FileNotFoundError: # Raised by is_package_installed_rpm if 'rpm' command is missing
        con.print_error("'rpm' command not found. Cannot check or enable RPM Fusion tainted repository.")
        app_logger.error("'rpm' command not found, cannot enable tainted repo for NVIDIA drivers.")
        return False
    except Exception as e: # Catch any other unexpected errors during this process
        app_logger.error(f"Unexpected error while enabling RPM Fusion tainted repository '{tainted_repo_pkg_name}': {e}", exc_info=True)
        con.print_error(f"An unexpected error occurred while enabling RPM Fusion tainted repository '{tainted_repo_pkg_name}'.")
        return False


def _install_standard_nvidia_drivers(phase_config: dict) -> bool:
    """Installs standard NVIDIA DNF packages (e.g., akmod-nvidia, xorg-x11-drv-nvidia-cuda) if specified."""
    packages_to_install = phase_config.get("dnf_packages_standard", [])
    if not packages_to_install:
        con.print_info("No standard NVIDIA DNF packages specified in configuration. Skipping this installation step.")
        app_logger.info("No 'dnf_packages_standard' in Phase 5 config. Skipping standard NVIDIA driver install.")
        return True # Successfully skipped

    # con.print_sub_step is handled by install_dnf_packages
    app_logger.info(f"Attempting to install standard NVIDIA drivers: {', '.join(packages_to_install)}")
    if system_utils.install_dnf_packages(
        packages_to_install,
        allow_erasing=True, # NVIDIA drivers might need to erase conflicting open-source versions
        print_fn_info=con.print_info, 
        print_fn_error=con.print_error,
        print_fn_sub_step=con.print_sub_step, 
        logger=app_logger
    ):
        # install_dnf_packages prints its own success for the batch
        app_logger.info(f"Successfully installed standard NVIDIA DNF packages: {packages_to_install}")
        return True
    else:
        app_logger.error(f"Failed to install standard NVIDIA DNF packages: {packages_to_install}")
        return False

def _swap_to_nvidia_open_drivers(phase_config: dict) -> bool:
    """Swaps standard NVIDIA drivers to the open kernel module variant if specified in phase_config."""
    swap_config = phase_config.get("dnf_swap_open_drivers")
    if not swap_config or not isinstance(swap_config, dict): # Ensure it's a dict
        con.print_info("No NVIDIA open driver swap configuration found or configuration is invalid. Skipping this step.")
        app_logger.info("No 'dnf_swap_open_drivers' config or invalid format in Phase 5. Skipping swap to open drivers.")
        return True # Successfully skipped
    
    from_pkg = swap_config.get("from")
    to_pkg = swap_config.get("to")

    if not from_pkg or not to_pkg:
        con.print_error("Invalid 'from' or 'to' package specified in 'dnf_swap_open_drivers' configuration. Skipping swap.")
        app_logger.error(f"Invalid from/to package for NVIDIA open driver swap: from='{from_pkg}', to='{to_pkg}'.")
        return False # Configuration error

    # con.print_sub_step is handled by swap_dnf_packages
    app_logger.info(f"Attempting to swap DNF package '{from_pkg}' with NVIDIA open driver '{to_pkg}'.")
    if system_utils.swap_dnf_packages(
        from_pkg, to_pkg,
        allow_erasing=True, # Swapping often requires erasing
        print_fn_info=con.print_info, 
        print_fn_error=con.print_error,
        print_fn_sub_step=con.print_sub_step, 
        logger=app_logger
    ):
        # swap_dnf_packages prints its own success message
        app_logger.info(f"Successfully swapped DNF package '{from_pkg}' with '{to_pkg}'.")
        return True
    else:
        # Error handled by swap_dnf_packages
        # Adding a slightly more specific warning here as this can be a common point of failure if repos aren't right
        con.print_warning(f"Failed to swap '{from_pkg}' with '{to_pkg}'. This might be due to '{to_pkg}' not being available (check RPM Fusion repos) or conflicts.")
        app_logger.error(f"Failed to swap '{from_pkg}' with NVIDIA open driver '{to_pkg}'.")
        return False

# --- Main Phase Function ---

def run_phase5(app_config: dict) -> bool:
    """Executes Phase 5: NVIDIA Driver Installation."""
    app_logger.info("Starting Phase 5: NVIDIA Driver Installation.")
    con.print_step("PHASE 5: NVIDIA Driver Installation")
    
    phase5_config = config_loader.get_phase_data(app_config, "phase5_nvidia_installation")
    if not phase5_config: # get_phase_data returns {} if not found or error
        con.print_warning("No configuration found for Phase 5. Skipping NVIDIA driver installation.")
        app_logger.warning("No Phase 5 configuration found or configuration is invalid. Skipping.")
        return True # Successfully skipped

    con.print_panel(
        "[bold yellow]WARNING:[/] This phase will attempt to install NVIDIA proprietary drivers. \n"
        "Ensure you have a [bold]compatible NVIDIA GPU[/] (typically GT/GTX 600 series or newer, RTX series).\n"
        "Installing these drivers on unsupported hardware or in a VM without proper GPU passthrough can lead to a non-bootable system or display issues.",
        title="NVIDIA Driver Installation Notice",
        style="yellow"
    )
    if not con.confirm_action("Do you have a compatible NVIDIA GPU and wish to proceed with driver installation?", default=False):
        con.print_info("NVIDIA driver installation skipped by user confirmation.")
        app_logger.info("NVIDIA driver installation skipped by user confirmation.")
        return True 

    # Check if drivers are already installed
    try:
        if _is_nvidia_driver_installed(): # Uses the simplified helper
            if not con.confirm_action(
                "NVIDIA akmod drivers (standard or open) seem to be already installed. Do you want to attempt re-installation or configuration steps anyway?",
                default=False
            ):
                con.print_info("Skipping NVIDIA driver installation as they appear to be already installed and user chose not to proceed further.")
                app_logger.info("NVIDIA drivers already installed, user skipped further steps in Phase 5.")
                return True
    except FileNotFoundError: # Raised by is_package_installed_rpm if 'rpm' is missing
        con.print_error("'rpm' command not found. Cannot check if NVIDIA drivers are already installed. Critical for this phase.")
        app_logger.error("'rpm' command not found. Pre-check for NVIDIA drivers failed.")
        return False # Cannot safely proceed without 'rpm'
    except Exception as e_check: # Other unexpected errors during check
        con.print_warning(f"Could not reliably determine if NVIDIA drivers are installed: {e_check}. Proceeding with caution.")
        app_logger.warning(f"Error during _is_nvidia_driver_installed check: {e_check}", exc_info=True)
        # Allow user to decide if they want to proceed despite this uncertainty
        if not con.confirm_action("Could not verify current NVIDIA driver status. Proceed with installation attempts anyway?", default=False):
            con.print_info("NVIDIA driver installation skipped due to uncertainty and user choice.")
            return True


    con.print_info("\nStep 1: Ensuring system is up-to-date for kernel compatibility...")
    app_logger.info("Phase 5, Step 1: System update check for kernel compatibility.")
    kernel_before_update = ""
    try:
        kernel_before_update_proc = system_utils.run_command(
            ["uname", "-r"], capture_output=True, check=True, 
            print_fn_info=None, logger=app_logger # Quiet internal check
        )
        kernel_before_update = kernel_before_update_proc.stdout.strip()
        app_logger.info(f"Kernel version before DNF update attempt: {kernel_before_update}")

        con.print_sub_step("Running 'sudo dnf upgrade -y' to update system and potentially the kernel...")
        if not system_utils.upgrade_system_dnf(
            print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger
            # capture_output=False is default in upgrade_system_dnf to stream output
        ):
            # upgrade_system_dnf already prints error
            app_logger.error("System DNF upgrade command failed. Cannot safely proceed with NVIDIA driver installation.")
            return False
        
        app_logger.info("DNF upgrade command completed.")

        if _check_kernel_updated(kernel_before_update): # Pass the fetched kernel version
            con.print_warning(
                "The kernel was updated during the system upgrade. A system REBOOT is REQUIRED before installing NVIDIA drivers "
                "to ensure the new kernel is active and modules can be built correctly."
            )
            app_logger.warning("Kernel was updated. A reboot is strongly recommended before proceeding with NVIDIA driver installation.")
            if con.confirm_action("Do you want to stop here to reboot your system now? (Recommended)", default=True):
                con.print_info("Halting Phase 5. Please reboot your system and then re-run this script, or at least this phase.")
                app_logger.info("User chose to halt for reboot after kernel update in Phase 5.")
                # Returning False implies the phase did not complete its intended goal *yet*.
                # Caller should handle this, perhaps by exiting or prompting to rerun.
                return False 
            else:
                con.print_warning("Proceeding with NVIDIA driver installation without reboot after kernel update. This is NOT RECOMMENDED and may lead to issues.")
                app_logger.warning("User chose to proceed without reboot after kernel update (NOT RECOMMENDED).")
        else:
            con.print_info("Kernel does not appear to have been updated by the DNF upgrade. No immediate reboot necessary for kernel reasons.")
            app_logger.info("Kernel does not appear to have been updated by DNF upgrade.")

    except Exception as e_update_step: 
        con.print_error(f"The system update step encountered an unexpected issue: {e_update_step}. Cannot safely proceed with NVIDIA driver installation.")
        app_logger.error(f"System update step (Phase 5, Step 1) unexpected error: {e_update_step}", exc_info=True)
        return False

    con.print_info("\nStep 2: Enabling RPM Fusion Non-Free Tainted Repository (if configured)...")
    app_logger.info("Phase 5, Step 2: Enabling RPM Fusion non-free tainted repository.")
    if not _enable_rpm_fusion_tainted_repo(phase5_config):
        con.print_warning("Could not enable RPM Fusion non-free tainted repository. Some NVIDIA features or driver versions might be unavailable.")
        app_logger.warning("Failed to enable RPM Fusion non-free tainted repository in Phase 5. Continuing, but some features might be unavailable.")
        # Not necessarily a fatal error for all NVIDIA driver installs, so don't return False yet.
    
    con.print_info("\nStep 3: Selecting and Installing NVIDIA Driver Type...")
    app_logger.info("Phase 5, Step 3: Selecting and Installing NVIDIA driver type.")
    driver_choice = ""
    # Check if config provides options for both standard and open drivers
    has_standard_config = bool(phase5_config.get("dnf_packages_standard"))
    has_open_swap_config = bool(phase5_config.get("dnf_swap_open_drivers") and isinstance(phase5_config.get("dnf_swap_open_drivers"), dict) and phase5_config.get("dnf_swap_open_drivers", {}).get("to"))

    if has_standard_config and has_open_swap_config:
        choices = {
            "1": "Standard Proprietary Drivers (akmod-nvidia - Recommended for most users)",
            "2": "Open Kernel Module Drivers (akmod-nvidia-open - Experimental, for newer GPUs)"
        }
        con.print_info("Multiple NVIDIA driver options are configured:")
        for key, desc in choices.items():
            con.print_info(f"  {key}. {desc}")
        
        user_choice_num = con.ask_question("Select driver type to install:", choices=list(choices.keys()), default="1")
        if user_choice_num == "1":
            driver_choice = "standard"
        elif user_choice_num == "2":
            driver_choice = "open_via_swap" # Explicitly state it's a swap operation
        app_logger.info(f"User chose NVIDIA driver type: {driver_choice} (selected option: {user_choice_num})")
    elif has_standard_config:
        con.print_info("Configuration found for Standard Proprietary NVIDIA drivers (akmod-nvidia).")
        driver_choice = "standard"
        app_logger.info("Defaulting to standard proprietary NVIDIA drivers based on configuration.")
    elif has_open_swap_config: # Only open driver swap is configured (implying 'from' might not be installed)
        to_pkg_open = phase5_config.get("dnf_swap_open_drivers", {}).get("to")
        con.print_info(f"Configuration found to install/swap to NVIDIA Open Kernel Module drivers (target: '{to_pkg_open}').")
        driver_choice = "open_via_swap" # This will attempt swap, which handles direct install if 'from' isn't there
        app_logger.info(f"Defaulting to NVIDIA Open Kernel Module drivers (target: '{to_pkg_open}') via swap logic based on configuration.")
    else:
        con.print_error("No valid NVIDIA driver installation options (standard or open swap) found in Phase 5 configuration.")
        app_logger.error("No valid NVIDIA driver installation/swap options in Phase 5 config.")
        return False

    installation_successful = False
    if driver_choice == "standard":
        if _install_standard_nvidia_drivers(phase5_config):
            installation_successful = True
        else:
            # Error already printed by helper
            app_logger.error("Installation of standard NVIDIA drivers failed.")
            # No need to return False immediately, let phase summary handle overall status.
    elif driver_choice == "open_via_swap":
        if _swap_to_nvidia_open_drivers(phase5_config): 
            installation_successful = True
        else:
            # Error already printed by helper
            app_logger.error("Installation/swap to NVIDIA open kernel module drivers failed.")
    else: # Should not be reached if logic above is correct
        con.print_error("Invalid driver choice or configuration error. Aborting NVIDIA driver installation.")
        app_logger.error(f"Invalid driver_choice '{driver_choice}' determined. Aborting NVIDIA driver installation.")
        return False # This is a logic error in the script or config parsing

    if installation_successful:
        app_logger.info("NVIDIA driver DNF operations (install/swap) completed successfully.")
        con.print_info("\nStep 4: Post-installation procedures for NVIDIA drivers...")
        con.print_warning(
            "NVIDIA drivers have been installed/swapped via DNF. Kernel modules (akmods) now need to be built. "
            "This process can take 5-15 minutes, or sometimes longer, depending on your system."
        )
        con.print_info("Please WAIT for at least 5-10 minutes BEFORE rebooting to allow kmod build time.")
        
        if con.confirm_action("Do you want this script to pause for 5 minutes to allow initial kmod build time?", default=True):
            con.print_info("Pausing for 5 minutes...")
            app_logger.info("Pausing for 5 minutes for kmod build after NVIDIA driver DNF operations.")
            for i in range(5 * 60, 0, -1): # 5 minutes * 60 seconds
                mins, secs = divmod(i, 60)
                # Using console.print directly for dynamic line update
                con.console.print(f"  Waiting... {mins:02d}:{secs:02d} remaining", end="\r")
                time.sleep(1)
            con.console.print("  Pause complete.                                 ") # Clear the line
            app_logger.info("5-minute pause complete.")

        con.print_info("\nAfter waiting sufficiently, you can optionally check if the NVIDIA kernel module is built by running:")
        con.print_info("  `modinfo -F version nvidia` (or `modinfo -F version nvidia-open` if you installed open drivers)")
        con.print_info("If this command outputs a version number, the module is likely built and loaded (after reboot).")
        con.print_info("If it shows an error like 'modinfo: ERROR: Module nvidia not found.', you might need to wait longer or troubleshoot (e.g., check `akmods` status, `journalctl`).")

        con.print_step("IMPORTANT: REBOOT REQUIRED", char="!")
        con.print_warning("A system REBOOT is REQUIRED to load the new NVIDIA drivers and complete the installation.")
        con.print_info("Please save all your work and reboot your system after this script finishes.")
        
        con.print_success("Phase 5: NVIDIA Driver Installation tasks (DNF operations) completed. Please REBOOT your system.")
        app_logger.info("Phase 5 completed successfully (DNF ops done). User informed to reboot.")
        return True # Phase completed its DNF tasks. Reboot is user action.
    
    # If installation_successful is False
    app_logger.error("Phase 5: NVIDIA Driver Installation DNF operations failed.")
    con.print_error("Phase 5: NVIDIA Driver Installation DNF operations failed. Please review the logs.")
    return False