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

# --- DNS Configuration Helper Functions ---

def _is_systemd_resolved_active() -> bool:
    """Checks if systemd-resolved is active and potentially managing /etc/resolv.conf."""
    app_logger.debug("Checking if systemd-resolved is active.")
    systemd_managed_symlink = False
    if RESOLV_CONF_PATH.is_symlink():
        try:
            link_target = os.readlink(RESOLV_CONF_PATH)
            if "systemd" in link_target or "resolved" in link_target or "stub-resolv.conf" in link_target:
                systemd_managed_symlink = True
                app_logger.info(f"{RESOLV_CONF_PATH} is a symlink to a systemd-managed file: {link_target}")
        except OSError as e:
            app_logger.warning(f"Error reading symlink {RESOLV_CONF_PATH}: {e}")

    # Check systemd-resolved service status
    service_active = False
    try:
        status_proc = system_utils.run_command(
            ["systemctl", "is-active", "systemd-resolved.service"],
            capture_output=True, check=False, print_fn_info=None, logger=app_logger
        )
        if status_proc.returncode == 0 and status_proc.stdout.strip() == "active":
            service_active = True
            app_logger.info("systemd-resolved.service is active.")
        else:
            app_logger.info("systemd-resolved.service is not active or not found via systemctl.")
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        app_logger.info(f"systemctl command not found or failed for systemd-resolved check: {e}")

    # Consider systemd-resolved "active" for our purposes if either the symlink points to it
    # OR the service is explicitly active. The symlink is a strong indicator of management.
    if systemd_managed_symlink:
        # If symlinked, we should definitely try to use systemd-resolved,
        # even if the service status check had an issue (e.g. systemctl not in minimal env)
        # but we still log the service status for diagnostics.
        app_logger.info(f"Detected systemd-managed symlink for {RESOLV_CONF_PATH}. Proceeding with systemd-resolved logic.")
        return True # Prioritize symlink indication
    
    # If not symlinked, then rely on service status
    if service_active:
        app_logger.info(f"{RESOLV_CONF_PATH} not a clear systemd symlink, but service is active. Proceeding with systemd-resolved logic.")
        return True
        
    app_logger.info("systemd-resolved does not appear to be actively managing DNS.")
    return False


def _configure_systemd_resolved(dns_ipv4: list, dns_ipv6: list) -> bool:
    """Configures systemd-resolved via /etc/systemd/resolved.conf."""
    con.print_info(f"Attempting to configure DNS via {SYSTEMD_RESOLVED_CONF_PATH}.")
    
    if not SYSTEMD_RESOLVED_CONF_PATH.exists():
        con.print_info(f"{SYSTEMD_RESOLVED_CONF_PATH} does not exist. Attempting to create it.")
        try:
            system_utils.run_command(
                f"sudo mkdir -p {shlex.quote(str(SYSTEMD_RESOLVED_CONF_PATH.parent))} && "
                f"echo '[Resolve]' | sudo tee {shlex.quote(str(SYSTEMD_RESOLVED_CONF_PATH))} > /dev/null",
                shell=True, check=True, print_fn_info=con.print_info, logger=app_logger
            )
        except Exception as e_create:
            con.print_error(f"Failed to create {SYSTEMD_RESOLVED_CONF_PATH}: {e_create}")
            app_logger.error(f"Creation of {SYSTEMD_RESOLVED_CONF_PATH} failed: {e_create}", exc_info=True)
            return False

    system_utils.backup_system_file(
        SYSTEMD_RESOLVED_CONF_PATH, sudo_required=True, logger=app_logger,
        print_fn_info=con.print_info, print_fn_warning=con.print_warning
    )

    temp_resolved_conf = None # Initialize for finally block
    try:
        import configparser
        parser = configparser.ConfigParser(comment_prefixes=('#', ';'), allow_no_value=True, strict=False)
        
        read_proc = system_utils.run_command(
            ["sudo", "cat", str(SYSTEMD_RESOLVED_CONF_PATH)],
            capture_output=True, check=True, print_fn_info=None, logger=app_logger
        )
        parser.read_string(read_proc.stdout)

        if not parser.has_section("Resolve"):
            parser.add_section("Resolve")

        changes_made = False
        # Combine IPv4 and IPv6, systemd-resolved takes space-separated list for DNS=
        combined_dns_servers_list = []
        for ip in dns_ipv4 + dns_ipv6: # Prioritize IPv4 from config, then IPv6
            if ip not in combined_dns_servers_list: # Avoid duplicates
                combined_dns_servers_list.append(ip)
        dns_servers_str = " ".join(combined_dns_servers_list)
        
        if not dns_servers_str:
             app_logger.warning("No DNS servers provided to _configure_systemd_resolved. DNS field will be empty if not already set.")
             # Allow setting empty if that's what's passed, though _configure_dns usually provides defaults.

        current_dns_in_config = parser.get("Resolve", "DNS", fallback="").strip()
        if current_dns_in_config != dns_servers_str:
            parser.set("Resolve", "DNS", dns_servers_str)
            changes_made = True
            app_logger.info(f"Setting DNS in {SYSTEMD_RESOLVED_CONF_PATH} to: '{dns_servers_str}'")
        
        domains_setting = "~."
        if parser.get("Resolve", "Domains", fallback="") != domains_setting:
            parser.set("Resolve", "Domains", domains_setting)
            changes_made = True
            app_logger.info(f"Setting Domains in {SYSTEMD_RESOLVED_CONF_PATH} to: {domains_setting}")

        if changes_made:
            con.print_info(f"Updating DNS settings in {SYSTEMD_RESOLVED_CONF_PATH}...")
            temp_resolved_conf = Path(f"/tmp/resolved_conf_new_{os.getpid()}_{int(time.time())}.conf")
            with open(temp_resolved_conf, 'w', encoding='utf-8') as f_write:
                parser.write(f_write, space_around_delimiters=False)
            
            system_utils.run_command(["sudo", "cp", str(temp_resolved_conf), str(SYSTEMD_RESOLVED_CONF_PATH)], print_fn_info=con.print_info, logger=app_logger)
            system_utils.run_command(["sudo", "chown", "root:systemd-resolve", str(SYSTEMD_RESOLVED_CONF_PATH)], print_fn_info=con.print_info, logger=app_logger)
            system_utils.run_command(["sudo", "chmod", "644", str(SYSTEMD_RESOLVED_CONF_PATH)], print_fn_info=con.print_info, logger=app_logger)
            
            con.print_info("Restarting systemd-resolved to apply DNS changes...")
            system_utils.run_command(["sudo", "systemctl", "restart", "systemd-resolved.service"], print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
            system_utils.run_command(["sudo", "resolvectl", "flush-caches"], print_fn_info=con.print_info, print_fn_error=con.print_error, logger=app_logger)
            con.print_success("systemd-resolved configuration updated for DNS.")
        else:
            con.print_info(f"No changes required for systemd-resolved DNS configuration in {SYSTEMD_RESOLVED_CONF_PATH}.")
        return True
    except Exception as e:
        con.print_error(f"Failed to configure systemd-resolved via {SYSTEMD_RESOLVED_CONF_PATH}: {e}")
        app_logger.error(f"Error configuring systemd-resolved: {e}", exc_info=True)
        return False
    finally:
        if temp_resolved_conf and temp_resolved_conf.exists():
            try:
                temp_resolved_conf.unlink()
            except OSError as e_unlink:
                app_logger.warning(f"Failed to remove temporary file {temp_resolved_conf}: {e_unlink}")


def _handle_network_manager_warning(dns_ipv4_list: list, dns_ipv6_list: list) -> None:
    """Prints informational messages about NetworkManager managing /etc/resolv.conf."""
    con.print_warning(f"{RESOLV_CONF_PATH} seems to be managed by NetworkManager.")
    con.print_info("Automatic DNS configuration for NetworkManager is complex for a generic script and can be connection-specific.")
    con.print_info("If you use NetworkManager, please configure DNS manually via its settings (e.g., nm-connection-editor or nmtui),")
    con.print_info(f"or using nmcli for your active connection(s). Example for 'Wired connection 1':")
    
    # Construct example strings, handling cases where lists might be empty
    ipv4_example_dns = " ".join(dns_ipv4_list) if dns_ipv4_list else "8.8.8.8 8.8.4.4" # Default if empty
    ipv6_example_dns = " ".join(dns_ipv6_list) if dns_ipv6_list else "2001:4860:4860::8888 2001:4860:4860::8844"

    con.print_info(f"  sudo nmcli con mod \"Wired connection 1\" ipv4.dns \"{ipv4_example_dns}\"")
    con.print_info(f"  sudo nmcli con mod \"Wired connection 1\" ipv6.dns \"{ipv6_example_dns}\"")
    con.print_info(f"  sudo nmcli con mod \"Wired connection 1\" ipv4.ignore-auto-dns yes ipv6.ignore-auto-dns yes")
    con.print_info(f"  sudo nmcli con up \"Wired connection 1\"  # Reactivate to apply")
    app_logger.info("NetworkManager hint found in /etc/resolv.conf. Advised user to configure via NM tools.")


def _configure_direct_resolv_conf(dns_ipv4: list, dns_ipv6: list) -> bool:
    """Directly modifies /etc/resolv.conf."""
    con.print_warning(f"Fallback: Attempting to directly modify {RESOLV_CONF_PATH} (might be overwritten by system).")
    system_utils.backup_system_file(
        RESOLV_CONF_PATH, sudo_required=True, logger=app_logger,
        print_fn_info=con.print_info, print_fn_warning=con.print_warning
    )
    
    new_nameserver_lines = []
    for ip in dns_ipv4 + dns_ipv6: # Prioritize IPv4, then IPv6
        if ip: # Ensure IP is not empty
             new_nameserver_lines.append(f"nameserver {ip}")

    if not new_nameserver_lines:
        con.print_warning(f"No valid DNS servers provided to write to {RESOLV_CONF_PATH}. Skipping direct modification.")
        app_logger.warning(f"Direct resolv.conf modification skipped: no DNS servers to write.")
        return True # No action taken, not an error in itself.

    current_resolv_text = ""
    if RESOLV_CONF_PATH.exists():
        try:
            current_resolv_text = RESOLV_CONF_PATH.read_text(encoding='utf-8')
        except Exception as e:
            con.print_error(f"Could not read {RESOLV_CONF_PATH} for modification: {e}")
            app_logger.error(f"Failed to read {RESOLV_CONF_PATH}: {e}", exc_info=True)
            # Proceeding might overwrite, but backup was attempted.
            # If read fails, we can't preserve other settings.

    # Filter existing lines: keep non-nameserver lines and nameservers not in our new list.
    existing_lines_to_keep = []
    for line in current_resolv_text.splitlines():
        line_strip = line.strip()
        if line_strip.startswith("#"): # Keep comments
            existing_lines_to_keep.append(line_strip)
        elif "nameserver" in line_strip:
            # Check if this existing nameserver is one of the new ones we're adding
            # Avoids duplicates if script is re-run or if some were already there.
            # A simple check: if the IP part of the line is in our new combined list.
            try:
                existing_ip = line_strip.split()[1]
                if existing_ip not in (dns_ipv4 + dns_ipv6):
                    existing_lines_to_keep.append(line_strip)
            except IndexError: # Malformed nameserver line
                existing_lines_to_keep.append(line_strip) # Keep it as is
        elif line_strip: # Keep other non-empty, non-comment lines (e.g., search, options)
            existing_lines_to_keep.append(line_strip)

    # Prepend new nameservers, then add the filtered existing lines.
    # Limit total nameservers (e.g., to 6) to avoid issues.
    final_content_lines = []
    nameserver_count = 0
    for line in new_nameserver_lines: # Add our new/default DNS servers first
        if nameserver_count < 6:
            final_content_lines.append(line)
            nameserver_count +=1
    
    for line in existing_lines_to_keep: # Add other relevant lines from existing config
        if line.startswith("nameserver"):
            if nameserver_count < 6:
                final_content_lines.append(line)
                nameserver_count += 1
        else: # Non-nameserver lines (search, options, comments)
            final_content_lines.append(line)

    # Remove exact duplicate lines while preserving order (simple list comprehension)
    final_content_lines_ordered_unique = []
    for line in final_content_lines:
        if line not in final_content_lines_ordered_unique:
            final_content_lines_ordered_unique.append(line)
            
    if not any(line.startswith("nameserver") for line in final_content_lines_ordered_unique):
        con.print_warning(f"After processing, no nameserver entries would be written to {RESOLV_CONF_PATH}. Skipping modification.")
        app_logger.warning("Direct /etc/resolv.conf modification skipped: no nameservers to write after filtering.")
        return True

    try:
        new_content = "\n".join(final_content_lines_ordered_unique).strip() + "\n" # Ensure single trailing newline
        cmd_write_resolv = f"echo -e {shlex.quote(new_content)} | sudo tee {shlex.quote(str(RESOLV_CONF_PATH))} > /dev/null"
        system_utils.run_command(cmd_write_resolv, shell=True, check=True, print_fn_info=con.print_info, logger=app_logger)
        con.print_success(f"DNS entries updated in {RESOLV_CONF_PATH}. System may overwrite this if not using systemd-resolved.")
        return True
    except Exception as e_direct_write:
        con.print_error(f"Failed to directly write to {RESOLV_CONF_PATH}: {e_direct_write}")
        app_logger.error(f"Direct write to {RESOLV_CONF_PATH} failed: {e_direct_write}", exc_info=True)
        return False

# --- Main DNS Orchestrator ---
def _configure_dns(app_config: dict) -> bool: # Added app_config back
    """Configures system DNS, preferring systemd-resolved, then attempting /etc/resolv.conf."""
    con.print_sub_step("Configuring DNS...")
    app_logger.info("Starting DNS configuration.")

    # Extract DNS servers from app_config, defaulting to Google's if not provided
    # This part remains in the orchestrator as it deals with app_config.
    dns_ipv4 = app_config.get("dns_servers", {}).get("ipv4", []) + GOOGLE_DNS_IPV4 # Ensure defaults are appended if list from config
    dns_ipv6 = app_config.get("dns_servers", {}).get("ipv6", []) + GOOGLE_DNS_IPV6
    
    # Remove duplicates while preserving order (from config first, then defaults)
    dns_ipv4 = sorted(set(dns_ipv4), key=dns_ipv4.index)
    dns_ipv6 = sorted(set(dns_ipv6), key=dns_ipv6.index)
    
    if not dns_ipv4 and not dns_ipv6: # Check if, after processing, we have any DNS servers
        con.print_warning("No DNS servers specified in config and defaults are also missing/empty. Skipping DNS configuration.")
        app_logger.warning("DNS configuration skipped: no DNS servers available after processing config and defaults.")
        return True # Not an error, but a skip.
        
    app_logger.info(f"Effective DNS servers to be used - IPv4: {dns_ipv4}, IPv6: {dns_ipv6}")

    if _is_systemd_resolved_active():
        app_logger.info("systemd-resolved appears active. Attempting configuration via systemd-resolved.")
        if _configure_systemd_resolved(dns_ipv4, dns_ipv6):
            return True
        else:
            con.print_warning("systemd-resolved configuration failed. Will check for NetworkManager or attempt direct /etc/resolv.conf modification as fallback.")
            app_logger.warning("systemd-resolved configuration failed. Fallback initiated.")
    else:
        app_logger.info("systemd-resolved does not appear to be the primary DNS manager.")

    # --- Fallback or Non-systemd-resolved Path ---
    app_logger.info(f"Checking {RESOLV_CONF_PATH} for NetworkManager hints before direct modification.")
    try:
        # We only show the NetworkManager warning if /etc/resolv.conf is NOT a symlink
        # managed by systemd-resolved. If _is_systemd_resolved_active() returned false because
        # it's not a symlink (even if service was running), then it's safe to check for NM.
        # If _is_systemd_resolved_active() was true but _configure_systemd_resolved failed,
        # it's less likely NM is the primary if it's a systemd symlink.
        
        resolv_is_systemd_symlink = False
        if RESOLV_CONF_PATH.is_symlink():
            link_target = os.readlink(RESOLV_CONF_PATH)
            if "systemd" in link_target or "resolved" in link_target or "stub-resolv.conf" in link_target:
                resolv_is_systemd_symlink = True
        
        if not resolv_is_systemd_symlink: # Only proceed with NM check if not a systemd symlink
            resolv_content = RESOLV_CONF_PATH.read_text(encoding='utf-8') if RESOLV_CONF_PATH.exists() else ""
            if "NetworkManager" in resolv_content:
                _handle_network_manager_warning(dns_ipv4, dns_ipv6) # Pass DNS lists for example message
                return True # User informed, considered successful for this script's scope.
        else:
            app_logger.info(f"{RESOLV_CONF_PATH} is a systemd symlink; skipping NetworkManager check for direct modification fallback.")
            
    except Exception as e_nm_check:
        app_logger.warning(f"Error checking {RESOLV_CONF_PATH} for NetworkManager: {e_nm_check}. Proceeding with direct modification attempt.")

    # Attempt direct modification if not handled by systemd-resolved or NetworkManager hint path
    return _configure_direct_resolv_conf(dns_ipv4, dns_ipv6)


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
        if not _configure_dns(app_config):
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