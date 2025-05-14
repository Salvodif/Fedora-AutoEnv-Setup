# nvidia_installation.py
import shutil
import os
import logging

from rich.prompt import Prompt

from myrich import (
    console, print_info, print_error, print_success,
    print_step, print_header, print_warning
)
from utils import run_command

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

def _install_standard_nvidia_drivers():
    """Installs akmod-nvidia and xorg-x11-drv-nvidia-cuda."""
    print_info("Attempting to install standard NVIDIA drivers (akmod-nvidia) and CUDA drivers...")
    
    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
    packages_to_install = ["akmod-nvidia", "xorg-x11-drv-nvidia-cuda"]
    
    print_info(f"Running: sudo {dnf_cmd} install -y {' '.join(packages_to_install)}")
    if run_command([dnf_cmd, "install", "-y"] + packages_to_install):
        print_success("Standard NVIDIA drivers (akmod-nvidia) and CUDA drivers installed successfully.")
        print_warning("A reboot is required for the drivers to load.")
        print_warning("After reboot, it might take a few minutes for akmod to build and load the kernel module.")
        return True
    else:
        print_error("Failed to install standard NVIDIA drivers and/or CUDA drivers.")
        logging.error(f"Failed to install {' '.join(packages_to_install)}")
        return False

def _enable_rpm_fusion_tainted_repo():
    """Installs the RPM Fusion nonfree tainted repository."""
    print_info("Attempting to enable RPM Fusion 'nonfree-tainted' repository...")
    # Check if already installed
    tainted_installed_retcode = run_command(["rpm", "-q", "rpmfusion-nonfree-release-tainted"], capture_output=True, check=False)[2]
    if tainted_installed_retcode == 0:
        print_info("RPM Fusion 'nonfree-tainted' repository already enabled.")
        return True

    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
    package_name = "rpmfusion-nonfree-release-tainted" # This is the correct package name generally

    # The URL method is less common for this specific sub-repo, usually it's a dnf install of the package name
    # However, if you want to ensure it via a URL if the package name fails (e.g. on a fresh system
    # where metadata isn't updated yet for 'tainted'). The package should be in rpmfusion-nonfree.
    # For simplicity, we'll rely on `dnf install rpmfusion-nonfree-release-tainted`
    # assuming rpmfusion-nonfree is already configured from Phase 1 or the check.
    
    print_info(f"Running: sudo {dnf_cmd} install -y {package_name}")
    if run_command([dnf_cmd, "install", "-y", package_name]):
        print_success("RPM Fusion 'nonfree-tainted' repository enabled successfully.")
        return True
    else:
        print_error(f"Failed to enable RPM Fusion 'nonfree-tainted' repository by installing '{package_name}'.")
        logging.error(f"Failed to install {package_name}")
        return False

def _swap_to_nvidia_open_drivers():
    """Swaps standard NVIDIA drivers for the open kernel module variant."""
    print_info("Attempting to swap to NVIDIA open kernel module drivers (akmod-nvidia-open)...")
    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"

    # Ensure tainted repo is enabled first, as -open drivers are often there.
    if not _enable_rpm_fusion_tainted_repo():
        print_error("Cannot proceed with swapping to open drivers as tainted repo could not be enabled.")
        return False
        
    # The dnf swap command
    # sudo dnf swap akmod-nvidia akmod-nvidia-open -y (add -y if sure)
    print_info(f"Running: sudo {dnf_cmd} swap akmod-nvidia akmod-nvidia-open --allowerasing -y")
    # --allowerasing might be needed if there are conflicts or to remove old packages cleanly.
    if run_command([dnf_cmd, "swap", "akmod-nvidia", "akmod-nvidia-open", "--allowerasing", "-y"]):
        print_success("Successfully swapped to NVIDIA open kernel module drivers (akmod-nvidia-open).")
        print_warning("A reboot is required for the new drivers to load.")
        print_warning("After reboot, it might take a few minutes for akmod to build and load the kernel module.")
        return True
    else:
        print_error("Failed to swap to NVIDIA open kernel module drivers.")
        logging.error("dnf swap akmod-nvidia akmod-nvidia-open failed.")
        print_info("This could be because the open drivers are not available for your hardware/kernel,")
        print_info("or due to other package conflicts. Standard drivers might still be installed if the swap failed midway.")
        return False

def run_nvidia_driver_installation():
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
    if _install_standard_nvidia_drivers():
        drivers_installed_successfully = True # At least base drivers are on
        reboot_needed = True
    else:
        print_error("Failed to install base NVIDIA drivers. Aborting further NVIDIA setup for this phase.")
        return False # Critical failure

    # Step 2: Option to swap to Open Kernel Modules
    print_step(5.2, "Optionally swapping to NVIDIA Open Kernel Modules")
    if Prompt.ask("Do you want to attempt to swap the proprietary NVIDIA drivers for the 'Open Kernel Module' variant (akmod-nvidia-open)? This requires the 'tainted' RPM Fusion repo.", choices=["y", "n"], default="n") == "y":
        if _swap_to_nvidia_open_drivers():
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