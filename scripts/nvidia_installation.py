# nvidia_installation.py
import shutil
import os
import logging

from rich.prompt import Prompt

from scripts.myrich import (
    console, print_info, print_error, print_success,
    print_step, print_header, print_warning
)
from scripts.utils import run_command

def _check_root_privileges():
    if os.geteuid() != 0:
        print_error("This operation requires superuser (root) privileges.")
        return False
    return True

def _is_rpm_fusion_available():
    """Checks if RPM Fusion repositories seem to be configured."""
    # A simple check: see if the release packages are installed.
    # This relies on Phase 1 having installed them.
    free_installed = run_command(["rpm", "-q", "rpmfusion-free-release"], capture_output=True, check=False)[2] == 0
    nonfree_installed = run_command(["rpm", "-q", "rpmfusion-nonfree-release"], capture_output=True, check=False)[2] == 0
    
    if free_installed and nonfree_installed:
        print_info("RPM Fusion free and nonfree releases appear to be installed.")
        return True
    else:
        if not free_installed: print_warning("RPM Fusion free release package not found.")
        if not nonfree_installed: print_warning("RPM Fusion nonfree release package not found.")
        print_error("RPM Fusion repositories are required for NVIDIA drivers.")
        print_info("Please ensure Phase 1 (System Preparation) was completed successfully, or install them manually:")
        fedora_version_cmd = "rpm -E %fedora"
        stdout, _, retcode = run_command([fedora_version_cmd], capture_output=True, shell=True, check=False)
        if retcode == 0 and stdout.strip().isdigit():
            ver = stdout.strip()
            print_info(f"  sudo dnf install -y https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-{ver}.noarch.rpm")
            print_info(f"  sudo dnf install -y https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-{ver}.noarch.rpm")
        return False

def _install_standard_nvidia_drivers(config: dict):
    """Installs akmod-nvidia and xorg-x11-drv-nvidia-cuda."""
    print_info("Attempting to install standard NVIDIA drivers (akmod-nvidia) and CUDA drivers...")

    packages_to_install = config.get('dnf_packages_standard', [])
    if not packages_to_install:
        print_warning("No standard NVIDIA DNF packages specified in configuration. Skipping.")
        return True # Not a failure if not specified

    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
    print_info(f"Running: sudo {dnf_cmd} install -y {' '.join(packages_to_install)}")
    if run_command([dnf_cmd, "install", "-y"] + packages_to_install):
        print_success("Standard NVIDIA drivers and CUDA drivers installed successfully.")
        print_warning("A reboot is required for the drivers to load.")
        return True
    else:
        print_error("Failed to install standard NVIDIA drivers and/or CUDA drivers.")
        return False

def _enable_rpm_fusion_tainted_repo(config: dict):
    """Installs the RPM Fusion nonfree tainted repository."""
    print_info("Attempting to enable RPM Fusion 'nonfree-tainted' repository...")

    package_name = config.get('dnf_package_tainted_repo', "")
    if not package_name:
        print_warning("No RPM Fusion tainted repository package specified in configuration. Skipping.")
        return True # Not a failure if not specified

    tainted_installed_retcode = run_command(["rpm", "-q", "rpmfusion-nonfree-release-tainted"], capture_output=True, check=False)[2]
    if tainted_installed_retcode == 0:
        print_info("RPM Fusion 'nonfree-tainted' repository already enabled.")
        return True

    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"

    print_info(f"Running: sudo {dnf_cmd} install -y {package_name}")
    if run_command([dnf_cmd, "install", "-y", package_name]):
        print_success(f"RPM Fusion '{package_name}' repository enabled successfully.")
        return True
    else:
        print_error(f"Failed to enable RPM Fusion 'nonfree-tainted' repository by installing '{package_name}'.")
        return False

def _swap_to_nvidia_open_drivers(config: dict):
    """Swaps standard NVIDIA drivers for the open kernel module variant."""
    print_info("Attempting to swap to NVIDIA open kernel module drivers (akmod-nvidia-open)...")

    swap_details = config.get('dnf_swap_open_drivers', {})
    if not swap_details or 'from' not in swap_details or 'to' not in swap_details:
        print_warning("NVIDIA open driver swap details not correctly specified in configuration. Skipping swap.")
        return False # Indicate that swap wasn't attempted or failed prerequisite

    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"

    # Ensure tainted repo is enabled first, as -open drivers are often there.
    if not _enable_rpm_fusion_tainted_repo(config):
        print_error("Cannot proceed with swapping to open drivers as tainted repo could not be enabled.")
        return False

    pkg_from = swap_details['from']
    pkg_to = swap_details['to']

    print_info(f"Running: sudo {dnf_cmd} swap {pkg_from} {pkg_to} --allowerasing -y")
    if run_command([dnf_cmd, "swap", pkg_from, pkg_to, "--allowerasing", "-y"]):
        print_success(f"Successfully swapped to NVIDIA open kernel module drivers ({pkg_to}).")
        print_warning("A reboot is required for the new drivers to load.")
        return True
    else:
        print_error("Failed to swap to NVIDIA open kernel module drivers.")
        return False

def run_nvidia_driver_installation(config: dict):
    print_header("Phase 5: NVIDIA Driver Installation")
    if not _check_root_privileges():
        return False

    console.print("[bold red]WARNING: Installing NVIDIA drivers can be risky and might lead to boot issues if not compatible.[/bold red]")
    console.print("Ensure you have backups or know how to troubleshoot if problems arise (e.g., booting to a previous kernel, uninstalling drivers from a TTY).")
    
    if not Prompt.ask("Do you want to proceed with NVIDIA driver installation?", choices=["y", "n"], default="n") == "y":
        print_info("NVIDIA driver installation skipped by user.")
        return True # User skipped, not a failure of the phase itself.

    if not _is_rpm_fusion_available():
        print_error("RPM Fusion repositories are not properly set up. Cannot continue with NVIDIA driver installation.")
        return False

    print_warning("If you have Secure Boot enabled, you may need to enroll a new MOK (Machine Owner Key) after this process and before rebooting fully into the graphical environment. Follow your distribution's specific instructions for NVIDIA drivers and Secure Boot.")

    drivers_installed_successfully = False
    reboot_needed = False

    # Step 1: Install standard proprietary drivers (akmod-nvidia) and CUDA support
    print_step(5.1, "Installing standard NVIDIA proprietary drivers and CUDA support")
    if _install_standard_nvidia_drivers(config):
        drivers_installed_successfully = True # At least base drivers are on
        reboot_needed = True
    else:
        print_error("Failed to install base NVIDIA drivers. Aborting further NVIDIA setup for this phase.")
        return False # Critical failure

    # Step 2: Option to swap to Open Kernel Modules
    print_step(5.2, "Optionally swapping to NVIDIA Open Kernel Modules")
    if Prompt.ask("Do you want to attempt to swap the proprietary NVIDIA drivers for the 'Open Kernel Module' variant (akmod-nvidia-open)? This requires the 'tainted' RPM Fusion repo.", choices=["y", "n"], default="n") == "y":
        if _swap_to_nvidia_open_drivers(config):
            print_success("Swap to NVIDIA Open Kernel Modules seems successful.")
            # reboot_needed is already true
        else:
            print_warning("Failed to swap to NVIDIA Open Kernel Modules. The standard proprietary drivers should still be active if their installation was successful.")
            # Not necessarily a failure of the *entire* phase if standard drivers are okay.
    else:
        print_info("Skipped swapping to NVIDIA Open Kernel Modules.")

    if drivers_installed_successfully:
        print_success("\nNVIDIA driver installation phase completed.")
        if reboot_needed:
            print_warning("[bold yellow on_black]A system reboot is REQUIRED to load the new NVIDIA drivers.[/bold yellow on_black]")
            if Prompt.ask("Do you want to reboot now?", choices=["y", "n"], default="n") == "y":
                print_info("Rebooting system...")
                logging.info("User initiated reboot after NVIDIA driver installation.")
                os.system("sudo reboot now") # This will halt script execution
            else:
                print_info("Please reboot your system manually as soon as possible.")
    else:
        print_error("\nNVIDIA driver installation phase encountered errors.")
    
    return drivers_installed_successfully