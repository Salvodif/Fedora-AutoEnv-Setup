# Fedora-AutoEnv-Setup/scripts/phase1_system_preparation.py

import subprocess
import shutil # For shutil.which, though not directly used in this version
import os
import sys
from pathlib import Path
# import configparser # Moved to where it's used or keep at top if widely used
import shlex 
import time # For unique temp file name in DNF config

# Adjust import path to reach parent directory for shared modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils # Ensure system_utils is imported
from scripts.logger_utils import app_logger 

# --- Constants ---
GOOGLE_DNS_IPV4 = ["8.8.8.8", "8.8.4.4"]
GOOGLE_DNS_IPV6 = ["2001:4860:4860::8888", "2001:4860:4860::8844"]
RESOLV_CONF_PATH = Path("/etc/resolv.conf")
SYSTEMD_RESOLVED_CONF_PATH = Path("/etc/systemd/resolved.conf")
DNF_CONF_PATH = Path("/etc/dnf/dnf.conf")

# --- Helper Functions (specific to this file) ---

# _backup_file was moved to system_utils.backup_system_file

def _configure_dns() -> bool:
    """Configures system DNS, preferring systemd-resolved, then attempting /etc/resolv.conf."""
    con.print_sub_step("Configuring DNS...")
    systemd_active = False
    # Check if /etc/resolv.conf is a symlink to a systemd-resolved stub file
    if RESOLV_CONF_PATH.is_symlink():
        try:
            link_target = os.readlink(RESOLV_CONF_PATH) 
            # Common targets for systemd-resolved
            if "systemd" in link_target or "resolved" in link_target or "stub-resolv.conf" in link_target:
                systemd_active = True
                con.print_info(f"{RESOLV_CONF_PATH} is a symlink pointing to a systemd-resolved managed file: {link_target}")
        except OSError as e: # Handle potential errors reading symlink
            app_logger.warning(f"Error reading symlink {RESOLV_CONF_PATH}: {e}")
            # Continue to check service status
            pass 

    # If not a clear symlink, or if symlink read failed, check service status
    if not systemd_active: 
        try:
            status_proc = system_utils.run_command(
                ["systemctl", "is-active", "systemd-resolved.service"],
                capture_output=True, check=False, # check=False as non-zero means inactive/not found
                print_fn_info=None, # Be quiet for this check
                logger=app_logger
            )
            if status_proc.returncode == 0 and status_proc.stdout.strip() == "active":
                systemd_active = True
                con.print_info("systemd-resolved.service is active.")
            else:
                con.print_info("systemd-resolved.service is not active or not found via systemctl.")
        except (FileNotFoundError, subprocess.CalledProcessError) as e: 
            con.print_info(f"systemctl command not found or failed ({e}); assuming systemd-resolved is not managing DNS this way.")
            app_logger.info(f"systemctl check for systemd-resolved failed or command not found: {e}")
            # systemd-resolved might still be active but uncheckable this way in some minimal envs
            pass 

    if systemd_active:
        con.print_info(f"systemd-resolved appears active. Attempting to configure DNS via {SYSTEMD_RESOLVED_CONF_PATH}.")
        if not SYSTEMD_RESOLVED_CONF_PATH.exists():
            con.print_info(f"{SYSTEMD_RESOLVED_CONF_PATH} does not exist. Attempting to create it with default [Resolve] section.")
            try:
                # Ensure parent directory exists and create file with [Resolve] header
                # Using sudo for mkdir and tee
                system_utils.run_command(
                    f"sudo mkdir -p {shlex.quote(str(SYSTEMD_RESOLVED_CONF_PATH.parent))} && "
                    f"echo '[Resolve]' | sudo tee {shlex.quote(str(SYSTEMD_RESOLVED_CONF_PATH))} > /dev/null",
                    shell=True, check=True, 
                    print_fn_info=con.print_info, # Show "Executing..."
                    logger=app_logger
                )
            except Exception as e_create:
                con.print_error(f"Failed to create {SYSTEMD_RESOLVED_CONF_PATH}: {e_create}")
                app_logger.error(f"Creation of {SYSTEMD_RESOLVED_CONF_PATH} failed: {e_create}", exc_info=True)
                return False # Cannot proceed with systemd-resolved config
        
        system_utils.backup_system_file(
            SYSTEMD_RESOLVED_CONF_PATH, 
            sudo_required=True, 
            logger=app_logger,
            print_fn_info=con.print_info, # Pass console printers
            print_fn_warning=con.print_warning
        )
        
        try:
            import configparser # Import here as it's specific to this block
            parser = configparser.ConfigParser(comment_prefixes=('#',';'), allow_no_value=True, strict=False) # strict=False for dnf.conf like files
            # Read current config (sudo cat needed as resolved.conf is root-owned)
            read_proc = system_utils.run_command(
                ["sudo", "cat", str(SYSTEMD_RESOLVED_CONF_PATH)], capture_output=True, check=True,
                print_fn_info=None, logger=app_logger # Quiet read
            )
            parser.read_string(read_proc.stdout)

            if not parser.has_section("Resolve"):
                parser.add_section("Resolve") # Add [Resolve] section if missing

            changes_made = False
            all_google_dns = GOOGLE_DNS_IPV4 + GOOGLE_DNS_IPV6
            dns_servers_str = " ".join(all_google_dns) # Space-separated for systemd-resolved
            
            current_dns_in_config = parser.get("Resolve", "DNS", fallback="").strip()
            # A more robust check would split current_dns_in_config and check set equality.
            # For now, direct string comparison is simpler if we control the format.
            if current_dns_in_config != dns_servers_str:
                parser.set("Resolve", "DNS", dns_servers_str)
                changes_made = True
                app_logger.info(f"Setting DNS in {SYSTEMD_RESOLVED_CONF_PATH} to: {dns_servers_str}")
            
            domains_setting = "~." # Use these DNS servers for all domains
            if parser.get("Resolve", "Domains", fallback="") != domains_setting:
                parser.set("Resolve", "Domains", domains_setting)
                changes_made = True
                app_logger.info(f"Setting Domains in {SYSTEMD_RESOLVED_CONF_PATH} to: {domains_setting}")

            if changes_made:
                con.print_info(f"Updating DNS settings in {SYSTEMD_RESOLVED_CONF_PATH}...")
                # Use a unique temporary file name for writing the new config
                temp_resolved_conf = Path(f"/tmp/resolved_conf_new_{os.getpid()}_{int(time.time())}.conf")
                with open(temp_resolved_conf, 'w', encoding='utf-8') as f_write:
                    parser.write(f_write, space_around_delimiters=False) # Write changes to temp file
                
                # Safely replace the original file with sudo
                system_utils.run_command(["sudo", "cp", str(temp_resolved_conf), str(SYSTEMD_RESOLVED_CONF_PATH)], print_fn_info=con.print_info, logger=app_logger)
                system_utils.run_command(["sudo", "chown", "root:systemd-resolve", str(SYSTEMD_RESOLVED_CONF_PATH)], print_fn_info=con.print_info, logger=app_logger) # Correct ownership
                system_utils.run_command(["sudo", "chmod", "644", str(SYSTEMD_RESOLVED_CONF_PATH)], print_fn_info=con.print_info, logger=app_logger) # Correct permissions
                if temp_resolved_conf.exists(): temp_resolved_conf.unlink() # Remove temp file

                con.print_info("Restarting systemd-resolved to apply DNS changes...")
                system_utils.run_command(["sudo", "systemctl", "restart", "systemd-resolved.service"], print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
                system_utils.run_command(["sudo", "resolvectl", "flush-caches"], print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger) # Also flush caches
                con.print_success("systemd-resolved configuration updated for DNS.")
            else:
                 con.print_info(f"No changes required for systemd-resolved DNS configuration in {SYSTEMD_RESOLVED_CONF_PATH}.")
            return True
        except Exception as e: 
            con.print_error(f"Failed to configure systemd-resolved via {SYSTEMD_RESOLVED_CONF_PATH}: {e}")
            app_logger.error(f"Error configuring systemd-resolved: {e}", exc_info=True)
            if 'temp_resolved_conf' in locals() and temp_resolved_conf.exists(): #type: ignore
                try: temp_resolved_conf.unlink() #type: ignore
                except OSError: pass
            return False
    
    # Fallback if systemd-resolved is not clearly active or its configuration failed
    con.print_info(f"systemd-resolved not detected or its configuration failed. Checking {RESOLV_CONF_PATH} for NetworkManager hints.")
    try:
        resolv_content_fallback = ""
        if RESOLV_CONF_PATH.exists(): 
            resolv_content_fallback = RESOLV_CONF_PATH.read_text(encoding='utf-8')

        if "NetworkManager" in resolv_content_fallback: 
            con.print_warning(f"{RESOLV_CONF_PATH} seems to be managed by NetworkManager.")
            con.print_info("Automatic DNS configuration for NetworkManager is complex for a generic script and can be connection-specific.")
            con.print_info("If you use NetworkManager, please configure DNS manually via its settings (e.g., nm-connection-editor or nmtui),")
            con.print_info(f"or using nmcli for your active connection(s). Example for 'Wired connection 1':")
            con.print_info(f"  sudo nmcli con mod \"Wired connection 1\" ipv4.dns \"{GOOGLE_DNS_IPV4[0]} {GOOGLE_DNS_IPV4[1]}\"")
            con.print_info(f"  sudo nmcli con mod \"Wired connection 1\" ipv6.dns \"{GOOGLE_DNS_IPV6[0]} {GOOGLE_DNS_IPV6[1]}\"")
            con.print_info(f"  sudo nmcli con mod \"Wired connection 1\" ipv4.ignore-auto-dns yes ipv6.ignore-auto-dns yes") # Important
            con.print_info(f"  sudo nmcli con up \"Wired connection 1\"  # Reactivate to apply")
            return True # Non-fatal, user informed to take manual action.
    except Exception as e:
        app_logger.warning(f"Error checking {RESOLV_CONF_PATH} for NetworkManager: {e}")
        # Continue to direct /etc/resolv.conf modification attempt
        pass

    con.print_warning(f"Fallback: Attempting to directly modify {RESOLV_CONF_PATH} (might be overwritten by system).")
    system_utils.backup_system_file(
        RESOLV_CONF_PATH, 
        sudo_required=True, 
        logger=app_logger,
        print_fn_info=con.print_info,
        print_fn_warning=con.print_warning
    )
    
    lines_to_add_to_resolv = []
    current_resolv_text_fallback = ""
    if RESOLV_CONF_PATH.exists(): 
        try:
            # Reading /etc/resolv.conf might not need sudo, but writing does.
            # If it's a symlink to systemd, it's often readable. Direct file also.
            current_resolv_text_fallback = RESOLV_CONF_PATH.read_text(encoding='utf-8')
        except Exception as e:
            con.print_error(f"Could not read {RESOLV_CONF_PATH} for modification: {e}")
            app_logger.error(f"Failed to read {RESOLV_CONF_PATH}: {e}", exc_info=True)
            return False

    for dns_ip in GOOGLE_DNS_IPV4 + GOOGLE_DNS_IPV6:
        entry = f"nameserver {dns_ip}"
        if entry not in current_resolv_text_fallback: 
            lines_to_add_to_resolv.append(entry)
    
    if lines_to_add_to_resolv:
        try:
            content_to_add = "\n".join(lines_to_add_to_resolv) + "\n"
            
            cleaned_existing_content_lines = [
                line for line in current_resolv_text_fallback.splitlines()
                if not any(google_ip in line for google_ip in GOOGLE_DNS_IPV4 + GOOGLE_DNS_IPV6)
            ]
            # Prepend new nameservers to give them priority
            new_content = content_to_add + "\n".join(cleaned_existing_content_lines).strip() + "\n"

            # Write the new content using sudo tee (overwrite)
            cmd_write_resolv = f"echo -e {shlex.quote(new_content.strip())} | sudo tee {shlex.quote(str(RESOLV_CONF_PATH))} > /dev/null"
            system_utils.run_command(cmd_write_resolv, shell=True, check=True, print_fn_info=con.print_info, logger=app_logger)
            con.print_success(f"DNS entries updated in {RESOLV_CONF_PATH}. System may overwrite this if not using systemd-resolved.")
        except Exception as e_direct_write: 
            con.print_error(f"Failed to directly write to {RESOLV_CONF_PATH}: {e_direct_write}")
            app_logger.error(f"Direct write to {RESOLV_CONF_PATH} failed: {e_direct_write}", exc_info=True)
            return False
    else:
        con.print_info(f"Google DNS entries already seem present in {RESOLV_CONF_PATH}.")
    return True

def _configure_dnf_performance() -> bool:
    """Configures DNF settings in /etc/dnf/dnf.conf for performance."""
    con.print_sub_step("Configuring DNF for performance and behavior...")
    if not DNF_CONF_PATH.exists():
        con.print_warning(f"{DNF_CONF_PATH} does not exist. DNF performance/behavior settings cannot be configured.")
        app_logger.warning(f"{DNF_CONF_PATH} not found, skipping DNF config.")
        return True # Not a critical failure for the phase, but a warning.

    system_utils.backup_system_file(
        DNF_CONF_PATH, 
        sudo_required=True, # dnf.conf is root-owned
        logger=app_logger,
        print_fn_info=con.print_info,
        print_fn_warning=con.print_warning
    )
    
    settings_to_set = {
        "max_parallel_downloads": "10",
        "fastestmirror": "True",
        "defaultyes": "True",    # Automatically answer yes to DNF prompts
        "keepcache": "True"      # Keep downloaded packages in cache
    }
    
    import configparser # Specific to this function
    parser = configparser.ConfigParser(comment_prefixes=('#', ';'), allow_no_value=True, strict=False)
    changes_made = False
    try:
        # Reading with sudo cat as dnf.conf is root-owned
        read_proc = system_utils.run_command(
            ["sudo", "cat", str(DNF_CONF_PATH)], capture_output=True, check=True,
            print_fn_info=None, logger=app_logger # Quiet read
        )
        parser.read_string(read_proc.stdout)
        
        if not parser.has_section("main"):
            parser.add_section("main")
            changes_made = True # Section was added

        for key, value in settings_to_set.items():
            # Set option if not present or if value differs
            if not parser.has_option("main", key) or parser.get("main", key) != value:
                parser.set("main", key, value)
                changes_made = True
                app_logger.info(f"Setting DNF config: [main] {key} = {value}") # section 'main' is hardcoded here, parser.defaults() is for global defaults.
        
        if changes_made:
            con.print_info(f"Updating DNF settings in {DNF_CONF_PATH}...")
            temp_config_path = Path(f"/tmp/dnf_conf_new_{os.getpid()}_{int(time.time())}.conf")
            with open(temp_config_path, 'w', encoding='utf-8') as f_write:
                parser.write(f_write, space_around_delimiters=False) 
            
            # Replace original config file with sudo
            system_utils.run_command(["sudo", "cp", str(temp_config_path), str(DNF_CONF_PATH)], print_fn_info=con.print_info, logger=app_logger)
            system_utils.run_command(["sudo", "chown", "root:root", str(DNF_CONF_PATH)], print_fn_info=con.print_info, logger=app_logger)
            system_utils.run_command(["sudo", "chmod", "644", str(DNF_CONF_PATH)], print_fn_info=con.print_info, logger=app_logger)
            if temp_config_path.exists(): temp_config_path.unlink() # Clean up temp file
            con.print_success("DNF configuration updated successfully.")
        else:
            con.print_info("DNF configuration settings already up-to-date.")
        return True
    except configparser.Error as e: # Error during parsing
        con.print_error(f"Error parsing {DNF_CONF_PATH}: {e}. DNF configuration not updated.")
        app_logger.error(f"ConfigParser error for {DNF_CONF_PATH}: {e}", exc_info=True)
        return False
    except Exception as e: # Catch-all for other unexpected errors, including CalledProcessError from run_command
        con.print_error(f"Failed to configure DNF settings: {e}")
        app_logger.error(f"Unexpected error configuring DNF: {e}", exc_info=True)
        if 'temp_config_path' in locals() and temp_config_path.exists(): # type: ignore
            try: temp_config_path.unlink() # type: ignore
            except OSError: pass
        return False

def _setup_rpm_fusion() -> bool:
    """Sets up RPM Fusion free and non-free repositories."""
    con.print_sub_step("Setting up RPM Fusion repositories...")
    free_installed = False
    nonfree_installed = False
    
    # Check if 'rpm' command is available early. is_package_installed_rpm will raise FileNotFoundError if not.
    try:
        system_utils.run_command(["rpm", "--version"], capture_output=True, check=True, print_fn_info=None, logger=app_logger)
    except FileNotFoundError:
        con.print_error("'rpm' command not found. Cannot check for or install RPM Fusion repositories using RPM URLs.")
        app_logger.error("'rpm' command not found. RPM Fusion setup depends on it for version detection and URL construction.")
        return False # Critical failure if 'rpm' is missing for this step

    try:
        if system_utils.is_package_installed_rpm("rpmfusion-free-release", logger=app_logger, print_fn_info=None): # Be quiet
            free_installed = True
        if system_utils.is_package_installed_rpm("rpmfusion-nonfree-release", logger=app_logger, print_fn_info=None): # Be quiet
            nonfree_installed = True

        if free_installed and nonfree_installed:
            con.print_info("RPM Fusion free and non-free repositories seem to be already installed.")
            return True
        elif free_installed:
            con.print_info("RPM Fusion free repository is installed. Non-free repository will be installed.")
        elif nonfree_installed:
            con.print_info("RPM Fusion non-free repository is installed. Free repository will be installed.")
        else:
            con.print_info("RPM Fusion repositories not found. Both will be installed.")

    except Exception as e: # Catch other errors during the RPM check itself (though is_package_installed_rpm should handle most)
        con.print_warning(f"Error checking RPM Fusion status: {e}. Proceeding with install attempt.")
        app_logger.warning(f"Error during RPM Fusion status check: {e}", exc_info=True)
        # Continue with installation attempt

    try:
        # Determine Fedora version using rpm
        fedora_version_proc = system_utils.run_command(
            "rpm -E %fedora", capture_output=True, shell=True, check=True, # shell=True for %fedora expansion
            print_fn_info=None, print_fn_error=con.print_error, logger=app_logger # Be quiet on success
        )
        fedora_version = fedora_version_proc.stdout.strip()
        if not fedora_version or not fedora_version.isdigit():
            con.print_error(f"Could not determine a valid Fedora version (got: '{fedora_version}'). Cannot setup RPM Fusion.")
            app_logger.error(f"Invalid Fedora version detected via rpm -E %fedora: {fedora_version}")
            return False
        con.print_info(f"Detected Fedora version: {fedora_version}")

        rpm_fusion_base_url = "https://mirrors.rpmfusion.org"
        rpm_fusion_free_url = f"{rpm_fusion_base_url}/free/fedora/rpmfusion-free-release-{fedora_version}.noarch.rpm"
        rpm_fusion_nonfree_url = f"{rpm_fusion_base_url}/nonfree/fedora/rpmfusion-nonfree-release-{fedora_version}.noarch.rpm"
        
        packages_to_install_rpmfusion = []
        if not free_installed: 
            packages_to_install_rpmfusion.append(rpm_fusion_free_url)
            app_logger.info(f"RPM Fusion free repo will be installed from: {rpm_fusion_free_url}")
        if not nonfree_installed: 
            packages_to_install_rpmfusion.append(rpm_fusion_nonfree_url)
            app_logger.info(f"RPM Fusion non-free repo will be installed from: {rpm_fusion_nonfree_url}")

        if not packages_to_install_rpmfusion: # Should only happen if both were already installed
            con.print_info("RPM Fusion repositories are already correctly set up.") # Redundant if caught above, but safe.
            return True

        # Install the RPMs using DNF
        if system_utils.install_dnf_packages(
            packages_to_install_rpmfusion,
            allow_erasing=False, # These are repo packages, erasing not typically needed
            # No --nogpgcheck by default, DNF should handle RPM Fusion keys.
            # If GPG issues arise, this might need to be re-evaluated or keys imported first.
            print_fn_info=con.print_info, print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step,
            logger=app_logger, 
            capture_output=True # RPM install is usually quick, capture output for logging
        ):
            con.print_success("RPM Fusion repositories enabled/updated successfully.")
            return True
        else:
            con.print_error("Failed to install RPM Fusion repositories using DNF.") # install_dnf_packages also prints
            return False
            
    except Exception as e: # Catch-all for unexpected errors in this block
        con.print_error(f"An unexpected error occurred during RPM Fusion setup: {e}")
        app_logger.error(f"Unexpected error in RPM Fusion setup: {e}", exc_info=True)
        return False

def _set_hostname() -> bool:
    """Interactively sets the system hostname."""
    con.print_sub_step("Setting system hostname...")
    current_hostname = ""
    try:
        # Try hostnamectl first, as it's the modern tool
        current_hostname_proc = system_utils.run_command(
            ["hostnamectl", "status", "--static"], capture_output=True, check=False, # check=False, parse return code
            print_fn_info=None, logger=app_logger # Quiet check
        )
        if current_hostname_proc.returncode == 0 and current_hostname_proc.stdout.strip():
            current_hostname = current_hostname_proc.stdout.strip()
        else: 
            app_logger.info("hostnamectl failed or gave empty static hostname, trying 'hostname' command.")
            current_hostname_proc_fallback = system_utils.run_command(
                ["hostname"], capture_output=True, check=True, # Expect 'hostname' to succeed if present
                print_fn_info=None, logger=app_logger
            )
            current_hostname = current_hostname_proc_fallback.stdout.strip()
        
        con.print_info(f"Current system hostname: {current_hostname}")

        if con.confirm_action(f"Do you want to change the hostname from '{current_hostname}'?", default=False):
            new_hostname = ""
            while not new_hostname: # Loop until a non-empty hostname is provided or user cancels
                new_hostname = con.ask_question("Enter the new desired hostname:").strip()
                if not new_hostname:
                    con.print_warning("Hostname cannot be empty.")
                    if not con.confirm_action("Try entering hostname again?", default=True):
                        con.print_info("Hostname change cancelled by user.")
                        return True # Successfully skipped by user choice
            
            if new_hostname == current_hostname:
                con.print_info("New hostname is the same as the current one. No change will be made.")
            else:
                con.print_info(f"Attempting to change hostname to '{new_hostname}'...")
                # hostnamectl set-hostname requires sudo
                system_utils.run_command(
                    ["sudo", "hostnamectl", "set-hostname", new_hostname],
                    print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger
                )
                con.print_success(f"Hostname successfully changed to '{new_hostname}'. A reboot might be needed for all services and prompts to reflect the new name.")
        else:
            con.print_info("Hostname change skipped by user.")
        return True
    except FileNotFoundError: # If neither hostnamectl nor hostname are found
        con.print_error("'hostnamectl' or 'hostname' command not found. Cannot set hostname.")
        app_logger.error("'hostnamectl' or 'hostname' command not found, cannot set hostname.")
        return False
    except Exception as e: # Catch-all for other errors (e.g., CalledProcessError from hostname if check=True)
        con.print_error(f"An error occurred while trying to set the hostname: {e}")
        app_logger.error(f"Error setting hostname: {e}", exc_info=True)
        return False

# --- Main Phase Function ---

def run_phase1(app_config: dict) -> bool:
    """Executes Phase 1: System Preparation."""
    con.print_step("PHASE 1: System Preparation")
    app_logger.info("Starting Phase 1: System Preparation.")
    critical_success = True 
    
    phase1_config_data = config_loader.get_phase_data(app_config, "phase1_system_preparation")
    if not isinstance(phase1_config_data, dict): 
        app_logger.warning("No valid configuration data (expected a dictionary) found for Phase 1. Skipping phase.")
        con.print_warning("No Phase 1 configuration data found. Skipping system preparation.")
        return True 

    # Step 1: Install core DNF packages for this phase
    dnf_packages_for_phase1 = phase1_config_data.get("dnf_packages", [])
    con.print_info("Step 1: Installing core DNF packages for Phase 1...")
    app_logger.info("Phase 1, Step 1: Installing core DNF packages.")
    if dnf_packages_for_phase1:
        if not system_utils.install_dnf_packages(
            dnf_packages_for_phase1,
            allow_erasing=True, 
            print_fn_info=con.print_info, print_fn_error=con.print_error,
            print_fn_sub_step=con.print_sub_step, logger=app_logger
        ):
            con.print_error("Failed to install one or more core DNF packages for Phase 1. This is a critical failure.")
            app_logger.error("Core DNF package installation failed in Phase 1.")
            critical_success = False 
    else:
        con.print_info("No core DNF packages specified for installation in Phase 1.")
        app_logger.info("No core DNF packages for Phase 1.")

    if critical_success: 
        con.print_info("\nStep 2: Configuring DNF performance and behavior...")
        app_logger.info("Phase 1, Step 2: Configuring DNF performance.")
        if not _configure_dnf_performance():
            con.print_warning("DNF performance/behavior configuration encountered issues. Continuing, but DNF operations might be suboptimal.")
            app_logger.warning("DNF performance configuration failed.")
            # Not setting critical_success = False, as it's an optimization.

        con.print_info("\nStep 3: Setting up RPM Fusion repositories...")
        app_logger.info("Phase 1, Step 3: Setting up RPM Fusion.")
        if not _setup_rpm_fusion():
            con.print_error("RPM Fusion repository setup failed. This may impact availability of multimedia codecs and other software.")
            app_logger.error("RPM Fusion setup failed in Phase 1.")
            critical_success = False # RPM Fusion can be critical

    if critical_success: 
        con.print_info("\nStep 4: Configuring DNS...")
        app_logger.info("Phase 1, Step 4: Configuring DNS.")
        if not _configure_dns():
            con.print_error("DNS configuration encountered issues. Network operations might fail or be slow.")
            app_logger.error("DNS configuration failed in Phase 1.")
            critical_success = False # DNS is fairly critical

    if critical_success: 
        con.print_info("\nStep 5: Cleaning DNF metadata and updating system...")
        app_logger.info("Phase 1, Step 5: DNF clean and system upgrade.")
        if not system_utils.clean_dnf_cache( # Default is 'all'
            print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger
        ):
            con.print_warning("DNF cache cleaning ('dnf clean all') failed. Proceeding with system upgrade attempt.")
            app_logger.warning("DNF cache clean failed.")

        con.print_info("Attempting full system upgrade...")
        if not system_utils.upgrade_system_dnf(
            print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger
        ):
            con.print_error("CRITICAL: System update (dnf upgrade) failed. Subsequent phases may be unstable or fail.")
            app_logger.error("System update (dnf upgrade) failed in Phase 1.")
            critical_success = False 
    
    con.print_info("\nStep 6: Setting up Flathub repository for Flatpak...")
    app_logger.info("Phase 1, Step 6: Setting up Flathub.")
    if not system_utils.ensure_flathub_remote_exists(
        print_fn_info=con.print_info, print_fn_error=con.print_error, 
        print_fn_sub_step=con.print_sub_step, logger=app_logger
    ):
        con.print_warning("Flatpak (Flathub remote) setup encountered issues. This may affect Flatpak app installations in later phases.")
        app_logger.warning("Flathub setup failed.")
        # Not marking critical_success = False, but it's a significant warning.

    con.print_info("\nStep 7: Setting system hostname...")
    app_logger.info("Phase 1, Step 7: Setting hostname.")
    if not _set_hostname(): 
        con.print_warning("Setting system hostname encountered issues. This is non-critical for immediate phase success but should be reviewed.")
        app_logger.warning("Setting hostname failed.")

    if critical_success:
        con.print_success("Phase 1: System Preparation completed successfully.")
        app_logger.info("Phase 1: System Preparation completed successfully.")
    else:
        con.print_error("Phase 1: System Preparation completed with CRITICAL errors. Please review the output and logs.")
        app_logger.error("Phase 1: System Preparation completed with CRITICAL errors.")
    
    return critical_success