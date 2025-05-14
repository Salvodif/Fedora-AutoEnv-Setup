# system_preparation.py
import logging
import os
import shutil

from myrich import (
    console, print_info, print_warning, print_error, print_success,
    print_step, print_header
)
from utils import run_command # Use the shared utility

DNF_CONF_PATH = "/etc/dnf/dnf.conf"
DNF_SETTINGS = {
    "max_parallel_downloads": "10",
    "fastestmirror": "True" # DNF expects True/False or 1/0
}

def check_root_privileges():
    """Checks for root privileges and exits if not found."""
    if os.geteuid() != 0:
        print_error("This operation requires superuser (root) privileges.")
        print_info("Please run the script using 'sudo python3 install.py'")
        logging.error("Attempted operation without root privileges.")
        return False
    return True

def configure_dnf():
    """Configures DNF for better performance by editing /etc/dnf/dnf.conf."""
    print_step(1, f"Configuring DNF ({DNF_CONF_PATH})")
    if not check_root_privileges(): return False

    try:
        lines = []
        if os.path.exists(DNF_CONF_PATH):
            with open(DNF_CONF_PATH, "r") as f:
                lines = f.readlines()
        else:
            print_warning(f"{DNF_CONF_PATH} not found. Will create it.")
            # Ensure [main] section exists if creating new or if it's missing
            if not any("[main]" in line for line in lines):
                lines.insert(0, "[main]\n")


        # Remove existing settings to avoid duplicates and ensure our values are used
        # and prepare to add new ones under [main]
        updated_lines = []
        in_main_section = False
        main_section_exists = any("[main]" in line for line in lines)

        # If [main] doesn't exist, add it and prepare to insert settings there
        if not main_section_exists:
            updated_lines.append("[main]\n")
            # Add settings directly
            for key, value in DNF_SETTINGS.items():
                updated_lines.append(f"{key}={value}\n")
            # Add other lines if any (though if dnf.conf didn't exist, lines is empty)
            for line in lines:
                 if not any(key_to_check in line for key_to_check in DNF_SETTINGS.keys()):
                    updated_lines.append(line)
        else: # [main] section exists, modify it
            settings_added_to_main = {key: False for key in DNF_SETTINGS}
            for line in lines:
                stripped_line = line.strip()
                if stripped_line == "[main]":
                    in_main_section = True
                    updated_lines.append(line)
                    # Add settings if they are not already there or to update them
                    for key, value in DNF_SETTINGS.items():
                        # Check if a line for this key already exists to avoid adding it again later
                        # This simple check assumes keys are unique and not commented out
                        if not any(f"{key}=" in l for l in lines):
                             updated_lines.append(f"{key}={value}\n")
                             settings_added_to_main[key] = True
                    continue
                elif stripped_line.startswith("[") and stripped_line != "[main]":
                    in_main_section = False # Exited [main]

                # Remove old versions of our target settings
                if any(f"{key_to_check}=" in stripped_line for key_to_check in DNF_SETTINGS.keys()):
                    # We'll add the correct version under [main] or ensure it's there
                    continue
                updated_lines.append(line)

            # If [main] was present, but our settings were not added (e.g., not found to be replaced)
            # ensure they are added. This typically means they were not in the file.
            # This part is a bit tricky; a simpler robust way is to ensure [main] exists,
            # then filter out old settings, then append new settings.

            # Simpler approach: Ensure [main] exists, filter old, append new under [main]
            final_lines = []
            main_section_found_for_final_pass = False
            if not any("[main]" in line for line in updated_lines):
                final_lines.append("[main]\n")
                for key, value in DNF_SETTINGS.items():
                    final_lines.append(f"{key}={value}\n")
            
            for line in updated_lines:
                if not any(f"{key_to_check}=" in line for key_to_check in DNF_SETTINGS.keys()):
                    final_lines.append(line)
                if "[main]" in line:
                    main_section_found_for_final_pass = True
                    # Add settings after [main] if not already present in subsequent lines
                    for key, value in DNF_SETTINGS.items():
                         # Check if the setting is already in final_lines to avoid re-adding
                        if not any(f"{key}={value}" in l_final.strip() for l_final in final_lines) and \
                           not any(f"{key}=" in l_final.strip() for l_final in final_lines):
                            final_lines.append(f"{key}={value}\n")
            updated_lines = final_lines


        with open(DNF_CONF_PATH, "w") as f:
            f.writelines(updated_lines)

        print_success(f"DNF configuration updated in {DNF_CONF_PATH}.")
        for key, value in DNF_SETTINGS.items():
            print_info(f"  Set: {key}={value}")
        return True

    except IOError as e:
        print_error(f"Error accessing {DNF_CONF_PATH}: {e}")
        logging.error(f"IOError for {DNF_CONF_PATH}: {e}", exc_info=True)
        return False
    except Exception as e:
        print_error(f"An unexpected error occurred during DNF configuration: {e}")
        logging.error(f"Unexpected error configuring DNF: {e}", exc_info=True)
        return False


def system_update():
    """Performs a full system update using DNF."""
    print_step(2, "Performing system update (sudo dnf update -y)")
    if not check_root_privileges(): return False

    if run_command(["dnf", "update", "-y"]):
        print_success("System update completed successfully.")
        return True
    else:
        print_error("System update failed. Check the output above and app.log.")
        logging.error("dnf update -y failed.")
        return False

def enable_dnf5():
    """Installs DNF5 and its plugins."""
    print_step(3, "Enabling DNF5 (sudo dnf install dnf5 dnf5-plugins -y)")
    if not check_root_privileges(): return False

    if run_command(["dnf", "install", "-y", "dnf5", "dnf5-plugins"]):
        print_success("DNF5 and dnf5-plugins installed successfully.")
        return True
    else:
        print_error("Failed to install DNF5. Check the output above and app.log.")
        logging.error("dnf install dnf5 dnf5-plugins failed.")
        return False

def add_rpm_fusion_repositories():
    """Adds RPM Fusion free and nonfree repositories."""
    print_step(4, "Adding RPM Fusion repositories")
    if not check_root_privileges(): return False

    success = True
    fedora_version_cmd = "rpm -E %fedora"
    print_info(f"Getting Fedora version using: {fedora_version_cmd}")
    
    # Use shell=True for rpm -E %fedora as %fedora is a shell macro
    stdout, stderr, returncode = run_command(fedora_version_cmd, capture_output=True, shell=True)

    if returncode != 0 or not stdout:
        print_error(f"Failed to get Fedora version. Cannot add RPM Fusion repos. Stderr: {stderr}")
        logging.error(f"rpm -E %fedora failed. Stdout: {stdout}, Stderr: {stderr}")
        return False
    
    fedora_version = stdout.strip()
    print_info(f"Detected Fedora version: {fedora_version}")

    repos = {
        "free": f"https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-{fedora_version}.noarch.rpm",
        "nonfree": f"https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-{fedora_version}.noarch.rpm"
    }

    for repo_name, repo_url in repos.items():
        print_info(f"Adding RPM Fusion {repo_name} repository: {repo_url}")
        # DNF can install RPMs directly from a URL
        if run_command(["dnf", "install", "-y", repo_url]):
            print_success(f"RPM Fusion {repo_name} repository added successfully.")
        else:
            print_error(f"Failed to add RPM Fusion {repo_name} repository.")
            logging.error(f"dnf install -y {repo_url} failed.")
            success = False # Mark failure but continue trying other repos

    if success:
        print_step(4.1, "Refreshing repositories after adding RPM Fusion (sudo dnf upgrade --refresh -y)")
        if run_command(["dnf", "upgrade", "--refresh", "-y"]): # Use upgrade --refresh as per user's spec
            print_success("Repositories refreshed successfully.")
        else:
            print_warning("Failed to refresh repositories after adding RPM Fusion. Manual 'dnf check-update' might be needed.")
            # This might not be a critical failure for the overall script
            logging.warning("dnf upgrade --refresh -y failed after adding RPM Fusion.")
            # success remains true if repo add was ok, this is just a refresh fail
    
    return success # Returns true if repo adding was successful, refresh failure is a warning

def run_system_preparation():
    """Runs all system preparation steps."""
    print_header("System Preparation")
    if not check_root_privileges():
        print_error("Cannot proceed with system preparation without root privileges.")
        return False # Indicate failure

    all_successful = True

    if not configure_dnf():
        all_successful = False
        print_warning("DNF configuration failed. Continuing with other steps if possible...")
    
    if not system_update():
        all_successful = False
        print_warning("System update failed. This might impact subsequent steps. Continuing...")
        # Depending on severity, you might want to 'return False' here

    if not enable_dnf5():
        all_successful = False
        print_warning("DNF5 installation failed. Continuing...")

    if not add_rpm_fusion_repositories():
        all_successful = False
        print_warning("Adding RPM Fusion repositories encountered issues. Continuing...")

    if all_successful:
        print_success("\nSystem preparation phase completed successfully.")
    else:
        print_warning("\nSystem preparation phase completed with some errors. Please check the log and output.")
    
    return all_successful

if __name__ == '__main__':
    # For testing system_preparation.py directly
    # Make sure to run as root: sudo python3 system_preparation.py
    logging.basicConfig(
        filename='app_test_system_prep.log',
        level=logging.INFO, # Log more info for direct testing
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    console.print("[yellow]Running system_preparation.py directly for testing purposes.[/yellow]")
    console.print("[yellow]This requires superuser privileges for DNF operations and file modifications.[/yellow]")
    run_system_preparation()