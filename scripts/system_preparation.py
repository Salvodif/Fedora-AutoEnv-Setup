# system_preparation.py
import logging
import os
import shutil

from rich.prompt import Prompt

from scripts.myrich import (
    console, print_info, print_warning, print_error, print_success,
    print_step, print_header
)
from scripts.utils import run_command

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
    print_step(1.1, f"Configuring DNF ({DNF_CONF_PATH})") # Adjusted step numbering

    if not check_root_privileges(): return False
    try:
        lines = []
        if os.path.exists(DNF_CONF_PATH):
            with open(DNF_CONF_PATH, "r") as f:
                lines = f.readlines()
        else:
            print_warning(f"{DNF_CONF_PATH} not found. Will create it.")
            # Ensure [main] section exists if file is new or empty
            lines.insert(0, "[main]\n") 

        # Ensure [main] section exists
        main_section_present = any("[main]" in line.strip() for line in lines)
        if not main_section_present:
            # Find a suitable place or prepend if not found.
            # Prepending is safest if not sure.
            lines.insert(0, "[main]\n")
            print_info("Added [main] section to DNF config.")


        final_lines = []
        in_main_section = False
        settings_updated_or_added = {key: False for key in DNF_SETTINGS}

        for line in lines:
            stripped_line = line.strip()
            
            if stripped_line.startswith("[") and stripped_line.endswith("]"):
                in_main_section = (stripped_line == "[main]")
                final_lines.append(line) # Keep section header
                if in_main_section: # Add our settings right after [main] if they aren't there
                    for key, value in DNF_SETTINGS.items():
                        # Check if this key is already planned to be written by a later line
                        # This simple loop doesn't check ahead, assumes we overwrite or it's not there yet.
                        # A more robust INI parser would handle this better.
                        # For now, we add them, and subsequent lines might replace if they match our key.
                        # To avoid duplicates from this initial add, we'll rely on the next check.
                        pass # Let the setting-specific check below handle it.
                continue

            if in_main_section:
                written_this_line = False
                for key, value in DNF_SETTINGS.items():
                    if stripped_line.startswith(f"{key}="):
                        if not settings_updated_or_added[key]: # Update only once
                            final_lines.append(f"{key}={value}\n")
                            print_info(f"  Updated/Set in [main]: {key}={value}")
                            settings_updated_or_added[key] = True
                        else: # Already set by a previous line (e.g. if there were duplicates)
                            print_info(f"  Skipping duplicate update for {key} in [main].")
                        written_this_line = True
                        break 
                if not written_this_line:
                    final_lines.append(line) # Keep other lines in [main]
            else:
                final_lines.append(line) # Keep lines outside [main]

        # Add any settings not found and updated under [main]
        # This requires finding the [main] section again in final_lines or ensuring it's there.
        main_idx = -1
        for i, l in enumerate(final_lines):
            if l.strip() == "[main]":
                main_idx = i
                break
        
        if main_idx != -1:
            insert_at = main_idx + 1
            for key, value in DNF_SETTINGS.items():
                if not settings_updated_or_added[key]:
                    final_lines.insert(insert_at, f"{key}={value}\n")
                    print_info(f"  Added to [main]: {key}={value}")
                    settings_updated_or_added[key] = True
                    insert_at +=1 # for subsequent additions
        else: # Should not happen if [main] was ensured earlier
            print_error("Error: [main] section somehow lost during DNF config processing.")
            return False


        with open(DNF_CONF_PATH, "w") as f:
            f.writelines(final_lines)

        print_success(f"DNF configuration updated in {DNF_CONF_PATH}.")
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
    print_step(1.2, "Changing system hostname (Optional)") # Adjusted step numbering
    if not check_root_privileges(): return False # Return immediately if not root

    current_hostname_cmd = ["hostnamectl", "status", "--static"]
    stdout, stderr, returncode = run_command(current_hostname_cmd, capture_output=True, check=False)
    
    if returncode == 0 and stdout:
        current_hostname = stdout.strip()
    elif shutil.which("hostname"): # Fallback if hostnamectl status fails but hostname exists
        stdout_hn, _, _ = run_command(["hostname"], capture_output=True, check=False)
        current_hostname = stdout_hn.strip() if stdout_hn else "N/A"
    else:
        current_hostname = "N/A (could not determine)"

    print_info(f"Current static hostname: {current_hostname}")

    if Prompt.ask(f"Do you want to change the hostname from '{current_hostname}'?", choices=["y", "n"], default="n") == "y":
        new_hostname = Prompt.ask("Enter the new hostname").strip()
        if not new_hostname:
            print_warning("No hostname entered. Skipping change.")
            return True # Not a failure of the step, just user choice

        # Basic hostname validation (RFC 1123 subset)
        if not (1 <= len(new_hostname) <= 63 and \
                new_hostname[0].isalnum() and new_hostname[-1].isalnum() and \
                all(c.isalnum() or c == '-' for c in new_hostname) and \
                "--" not in new_hostname): # avoid double hyphens, though some systems allow
            print_error(f"Invalid hostname: '{new_hostname}'. Hostnames should be 1-63 chars, start/end with alphanum, contain only alphanum/hyphens.")
            logging.error(f"Invalid hostname provided: {new_hostname}")
            return False # Failure of the step

        print_info(f"Attempting to set hostname to: {new_hostname}")
        if shutil.which("hostnamectl"):
            if run_command(["hostnamectl", "set-hostname", new_hostname]):
                print_success(f"Hostname successfully changed to '{new_hostname}'.")
                print_warning("The new hostname will be fully effective after a reboot or new terminal session for some applications (like shell prompt).")
                return True
            else:
                print_error(f"Failed to set hostname to '{new_hostname}' using hostnamectl.")
                logging.error(f"hostnamectl set-hostname {new_hostname} failed.")
                return False
        else:
            print_error("'hostnamectl' command not found. Cannot change hostname.")
            logging.error("hostnamectl not found, cannot change hostname.")
            return False # Cannot perform action
    else:
        print_info("Hostname change skipped by user.")
        return True # User skipped, not a failure
    # return True # Should be unreachable if logic above is correct


def system_initial_update(): # Renamed to avoid confusion with the final update in this phase
    """Performs an initial system update using DNF if DNF5 is not yet primary."""
    # This step might be redundant if DNF5 enabling is successful and the final upgrade --refresh covers it.
    # However, keeping it ensures system is somewhat up-to-date before DNF5 install if that's preferred.
    print_step(1.3, "Performing initial system update (dnf update -y)") # Adjusted step numbering

    if not check_root_privileges(): return False
    if run_command(["dnf", "update", "-y"]):
        print_success("Initial system update completed successfully.")
        return True
    else:
        print_error("Initial system update failed. Check the output above and app.log.")
        logging.error("Initial dnf update -y failed.")
        return False # Potentially significant failure

def enable_dnf5(config: dict):
    """Installs DNF5 and its plugins."""
    print_step(1.4, "Enabling DNF5 (dnf install dnf5 dnf5-plugins -y)") # Adjusted step numbering

    dnf5_packages = config.get('dnf_packages', [])
    if not dnf5_packages:
        print_warning("No DNF5 packages specified in configuration for system_preparation. Skipping DNF5 enablement.")
        return True # Not a failure if not specified

    if not check_root_privileges(): return False

    print_info(f"Attempting to install DNF5 packages: {', '.join(dnf5_packages)}")
    if run_command(["dnf", "install", "-y", "dnf5", "dnf5-plugins"]):
        print_success("DNF5 and dnf5-plugins installed successfully.")
        return True
    else:
        print_error("Failed to install DNF5. Check the output above and app.log.")
        logging.error("dnf install dnf5 dnf5-plugins failed.")
        # Not necessarily a fatal error for the whole phase if dnf still works
        return False # Mark as failed for this specific step

def add_rpm_fusion_repositories():
    """Adds RPM Fusion free and nonfree repositories."""
    print_step(1.5, "Adding RPM Fusion repositories") # Adjusted step numbering

    if not check_root_privileges(): return False
    success = True
    fedora_version_cmd = "rpm -E %fedora"
    print_info(f"Getting Fedora version using: {fedora_version_cmd}")
    
    # Use shell=True carefully, only when the command string itself needs shell processing like variable expansion.
    # Here, rpm -E %fedora is safe as a list or with shell=True.
    stdout, stderr, returncode = run_command([fedora_version_cmd], capture_output=True, shell=True, check=False) 
    
    if returncode != 0 or not stdout:
        print_error(f"Failed to get Fedora version. Cannot add RPM Fusion repos. Stdout: '{stdout}', Stderr: '{stderr}'")
        logging.error(f"rpm -E %fedora failed. Stdout: {stdout}, Stderr: {stderr}")
        return False
        
    fedora_version = stdout.strip()
    if not fedora_version.isdigit():
        print_error(f"Failed to parse Fedora version: '{fedora_version}'. Cannot add RPM Fusion repos.")
        logging.error(f"Invalid Fedora version detected: {fedora_version}")
        return False

    print_info(f"Detected Fedora version: {fedora_version}")
    
    repos = {
        "free": f"https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-{fedora_version}.noarch.rpm",
        "nonfree": f"https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-{fedora_version}.noarch.rpm"
    }
    
    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf" # Use dnf5 if available

    for repo_name, repo_url in repos.items():
        print_info(f"Adding RPM Fusion {repo_name} repository using {dnf_cmd}: {repo_url}")
        # Check if repo is already installed to avoid errors from dnf install on existing package
        # rpm -q package-name returns 0 if installed
        repo_package_name = f"rpmfusion-{repo_name}-release" 
        # We need to run rpm -q without sudo if just checking
        _, _, rpm_q_retcode = run_command(["rpm", "-q", repo_package_name], capture_output=True, check=False)

        if rpm_q_retcode == 0:
            print_info(f"RPM Fusion {repo_name} repository ({repo_package_name}) appears to be already installed.")
        else:
            if run_command([dnf_cmd, "install", "-y", repo_url]):
                print_success(f"RPM Fusion {repo_name} repository added successfully.")
            else:
                print_error(f"Failed to add RPM Fusion {repo_name} repository using {dnf_cmd}.")
                logging.error(f"{dnf_cmd} install -y {repo_url} failed.")
                success = False # Mark failure but continue if possible for the other repo
    return success

def final_system_upgrade_and_refresh():
    """Performs a full system upgrade with repository refresh as the last step of Phase 1."""
    print_step(1.6, "Performing final system upgrade and refresh") # New final step numbering

    if not check_root_privileges(): return False
    
    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
    print_info(f"Using {dnf_cmd} for final upgrade and refresh.")

    if run_command([dnf_cmd, "upgrade", "--refresh", "-y"]):
        print_success("System upgrade and repository refresh completed successfully.")
        return True
    else:
        print_error("System upgrade and repository refresh failed. Check the output above and app.log.")
        logging.error(f"{dnf_cmd} upgrade --refresh -y failed.")
        return False


def run_system_preparation(config: dict):
    """Runs all system preparation steps (Phase 1)."""
    print_header("Phase 1: System Preparation")
    if not check_root_privileges():
        print_error("Cannot proceed with system preparation without root privileges.")
        return False

    all_successful_so_far = True # Tracks success of critical preliminary steps

    # Step 1.1: DNF Configuration
    if not configure_dnf():
        all_successful_so_far = False
        print_warning("DNF configuration failed. This might impact subsequent DNF operations.")
        # Decide if this is fatal. For now, let's try to continue.

    # Step 1.2: Change Hostname (Optional, non-critical for subsequent DNF ops)
    if all_successful_so_far: # Only if DNF config was okay (or if we decide to proceed anyway)
        if not change_hostname():
            # This is not strictly fatal for DNF operations, so don't set all_successful_so_far to False
            print_warning("Hostname change process encountered an issue or was skipped with an error.")
    else:
        print_info("Skipping hostname change due to earlier critical failures.")

    # Step 1.3: Initial System Update (using dnf before dnf5 potentially)
    if all_successful_so_far:
        if not system_initial_update():
            all_successful_so_far = False # An update failure can be significant
            print_warning("Initial system update failed. This might impact DNF5 installation or RPM Fusion.")
    else:
        print_info("Skipping initial system update due to earlier critical failures.")

    # Step 1.4: Enable DNF5
    if all_successful_so_far:
        if not enable_dnf5(config):
            # all_successful_so_far = False # Not necessarily fatal, dnf might still work
            print_warning("DNF5 installation failed. Continuing with dnf if available for subsequent steps...")
    else:
        print_info("Skipping DNF5 installation due to earlier critical failures.")
        
    # Step 1.5: Add RPM Fusion Repositories
    if all_successful_so_far:
        if not add_rpm_fusion_repositories():
            all_successful_so_far = False # Failure to add repos can be significant
            print_warning("Adding RPM Fusion repositories encountered issues.")
    else:
        print_info("Skipping RPM Fusion repository addition due to earlier critical failures.")

    # Step 1.6: Final System Upgrade and Refresh (THE NEW MANDATORY LAST STEP)
    # This step is crucial and should run if preceding steps were mostly okay,
    # or even if some non-critical ones (like DNF5 install) failed but DNF is usable.
    phase_1_overall_success = all_successful_so_far # Start with current status

    if not final_system_upgrade_and_refresh():
        phase_1_overall_success = False # This final step failing is important
        print_error("The final system upgrade and refresh (Phase 1.6) FAILED. Phase 1 is not fully complete.")
    
    if phase_1_overall_success:
        print_success("\nPhase 1 (System Preparation) completed successfully.")
    else:
        print_warning("\nPhase 1 (System Preparation) completed with some errors or warnings. Please check the log and output.")

    return phase_1_overall_success
