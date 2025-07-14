# Fedora-AutoEnv-Setup/scripts/phases/system_preparation.py

from scripts import console_output as con
from scripts import system_utils as util
from scripts.config import app_logger

def run(app_config):
    """
    Phase 1: System Preparation.
    This phase is responsible for installing essential packages for the system.
    """
    con.print_step("Phase 1: System Preparation")

    try:
        # Retrieve the list of packages to install from the configuration
        packages_to_install = app_config.get('phase1_system_preparation', {}).get('dnf_packages', [])

        if not packages_to_install:
            con.print_warning("No packages listed for installation in Phase 1.")
            return True

        # Check which packages are already installed
        con.print_sub_step("Checking for installed packages...")

        needed_packages = []
        for package in packages_to_install:
            if not util.is_package_installed_rpm(package, logger=app_logger):
                needed_packages.append(package)
            else:
                con.print_info(f"Package '{package}' is already installed.")

        # Install the missing packages
        if needed_packages:
            con.print_sub_step("Installing missing packages...")
            if util.install_dnf_packages(
                packages=needed_packages,
                logger=app_logger,
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step
            ):
                con.print_success("Successfully installed all required system preparation packages.")
            else:
                con.print_error("Failed to install some system preparation packages.")
                return False
        else:
            con.print_success("All system preparation packages are already installed.")

    except Exception as e:
        con.print_error(f"An unexpected error occurred during Phase 1: {e}")
        app_logger.error(f"Phase 1 failed with error: {e}", exc_info=True)
        return False

    return True
