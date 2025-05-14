# system_preparation.py
import logging
import os
import shutil

from rich.prompt import Prompt

from myrich import (
    console, print_info, print_warning, print_error, print_success,
    print_step, print_header
)
from utils import run_command

DNF_CONF_PATH = "/etc/dnf/dnf.conf"
DNF_SETTINGS = {
    "max_parallel_downloads": "10",
    "fastestmirror": "True"
}

def check_root_privileges():
    if os.geteuid() != 0:
        print_error("This operation requires superuser (root) privileges.")
        print_info("Please run the script using 'sudo python3 install.py'")
        logging.error("Attempted operation without root privileges.")
        return False
    return True

def configure_dnf():
    print_step(1, f"Configuring DNF ({DNF_CONF_PATH})")

    if not check_root_privileges(): return False
    try:
        lines = []
        if os.path.exists(DNF_CONF_PATH):
            with open(DNF_CONF_PATH, "r") as f:
                lines = f.readlines()
        else:
            print_warning(f"{DNF_CONF_PATH} not found. Will create it.")
            if not any("[main]" in line for line in lines): # Ensure [main] section exists
                lines.insert(0, "[main]\n")

        # Process lines to update/add DNF_SETTINGS under [main]
        # This logic can be complex to ensure correctness without a proper INI parser
        # A simplified approach: remove old settings, then add new ones if [main] exists or add [main] and then settings.
        
        final_lines = []
        main_section_found = False
        settings_added = {key: False for key in DNF_SETTINGS}

        temp_lines = []
        if not any("[main]" in line.strip() for line in lines):
            temp_lines.append("[main]\n") # Add [main] if not present
            main_section_found = True # Consider it found as we added it

        for line in lines:
            stripped_line = line.strip()
            if stripped_line == "[main]":
                main_section_found = True

            # Check if the line is one of our settings
            is_our_setting = False
            for key in DNF_SETTINGS.keys():
                if stripped_line.startswith(f"{key}="):
                    is_our_setting = True
                    break
            if not is_our_setting:
                temp_lines.append(line) # Keep lines that are not our settings

        if not main_section_found and "[main]\n" not in temp_lines : # Should be caught by initial check, but double check
             temp_lines.insert(0,"[main]\n")


        # Second pass: construct final_lines, adding our settings under [main]
        main_section_processed_for_adding = False
        for line in temp_lines:
            final_lines.append(line)
            if line.strip() == "[main]" and not main_section_processed_for_adding:
                for key, value in DNF_SETTINGS.items():
                    final_lines.append(f"{key}={value}\n")
                main_section_processed_for_adding = True

        # If [main] was added at the start and temp_lines was empty initially
        if not main_section_processed_for_adding and any("[main]\n" in line for line in final_lines):
             idx_main = -1
             for i, line_in_final in enumerate(final_lines):
                 if line_in_final.strip() == "[main]":
                     idx_main = i
                     break
             if idx_main != -1:
                 insert_idx = idx_main + 1
                 for key, value in reversed(DNF_SETTINGS.items()): # Insert in order
                     final_lines.insert(insert_idx, f"{key}={value}\n")


        with open(DNF_CONF_PATH, "w") as f:
            f.writelines(final_lines)

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


def change_hostname():
    """Allows the user to change the system hostname."""
    print_step(2, "Changing system hostname (Optional)")
    if not check_root_privileges(): return False

    current_hostname_cmd = ["hostnamectl", "status", "--static"]
    stdout, stderr, returncode = run_command(current_hostname_cmd, capture_output=True, check=False)
    current_hostname = stdout.strip() if returncode == 0 and stdout else "N/A"
    print_info(f"Current static hostname: {current_hostname}")

    if Prompt.ask(f"Do you want to change the hostname from '{current_hostname}'?", choices=["y", "n"], default="n") == "y":
        new_hostname = Prompt.ask("Enter the new hostname").strip()
        if not new_hostname:
            print_warning("No hostname entered. Skipping change.")
            return True

        if not all(c.isalnum() or c == '-' for c in new_hostname) or \
           new_hostname.startswith('-') or new_hostname.endswith('-') or \
           len(new_hostname) > 63 or len(new_hostname) == 0:
            print_error(f"Invalid hostname: '{new_hostname}'. Hostnames should contain only letters, numbers, and hyphens, not start/end with a hyphen, and be 1-63 characters long.")
            logging.error(f"Invalid hostname provided: {new_hostname}")
            return False

        print_info(f"Attempting to set hostname to: {new_hostname}")
        if run_command(["hostnamectl", "set-hostname", new_hostname]):
            print_success(f"Hostname successfully changed to '{new_hostname}'.")
            print_warning("The new hostname will be fully effective after a reboot or new terminal session for some applications (like shell prompt).")
            return True
        else:
            print_error(f"Failed to set hostname to '{new_hostname}'.")
            logging.error(f"hostnamectl set-hostname {new_hostname} failed.")
            return False
    else:
        print_info("Hostname change skipped by user.")
        return True
    return True

def system_update():
    """Performs a full system update using DNF."""
    print_step(3, "Performing system update (sudo dnf update -y)")

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
    print_step(4, "Enabling DNF5 (sudo dnf install dnf5 dnf5-plugins -y)")

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
    print_step(5, "Adding RPM Fusion repositories")

    if not check_root_privileges(): return False
    success = True
    fedora_version_cmd = "rpm -E %fedora"
    print_info(f"Getting Fedora version using: {fedora_version_cmd}")
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
        if run_command(["dnf", "install", "-y", repo_url]):
            print_success(f"RPM Fusion {repo_name} repository added successfully.")
        else:
            print_error(f"Failed to add RPM Fusion {repo_name} repository.")
            logging.error(f"dnf install -y {repo_url} failed.")
            success = False 
    if success:
        print_step(5.1, "Refreshing repositories after adding RPM Fusion (sudo dnf upgrade --refresh -y)")
        if run_command(["dnf", "upgrade", "--refresh", "-y"]):
            print_success("Repositories refreshed successfully.")
        else:
            print_warning("Failed to refresh repositories after adding RPM Fusion. Manual 'dnf check-update' might be needed.")
            logging.warning("dnf upgrade --refresh -y failed after adding RPM Fusion.")
    return success


def run_system_preparation():
    """Runs all system preparation steps (Phase 1)."""
    print_header("Phase 1: System Preparation")
    if not check_root_privileges():
        print_error("Cannot proceed with system preparation without root privileges.")
        return False

    all_successful = True

    if not configure_dnf(): # Step 1
        all_successful = False
        print_warning("DNF configuration failed. Continuing if possible...")

    if all_successful:
        if not change_hostname(): # Step 2
            print_warning("Hostname change process encountered an issue or was skipped with an error.")

    if all_successful:
        if not system_update(): # Step 3
            all_successful = False
            print_warning("System update failed. This might impact subsequent steps. Continuing...")

    if all_successful:
        if not enable_dnf5(): # Step 4
            all_successful = False
            print_warning("DNF5 installation failed. Continuing with dnf (if available)...")

    if all_successful:
        if not add_rpm_fusion_repositories(): # Step 5
            all_successful = False
            print_warning("Adding RPM Fusion repositories encountered issues. Continuing...")

    if all_successful:
        print_success("\nPhase 1 (System Preparation) completed successfully.")
    else:
        print_warning("\nPhase 1 (System Preparation) completed with some errors or warnings. Please check the log and output.")

    return all_successful

if __name__ == '__main__':
    # ... (codice di test invariato) ...
    logging.basicConfig(
        filename='app_test_system_prep.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    console.print("[yellow]Running system_preparation.py directly for testing purposes.[/yellow]")
    console.print("[yellow]This requires superuser privileges for DNF operations and file modifications.[/yellow]")
    run_system_preparation()