# Fedora-AutoEnv-Setup/scripts/phase1_system_preparation.py

import subprocess
import shutil
import os
import sys
from pathlib import Path
import configparser # For DNF configuration
import shlex 
import time # For unique temp file name in DNF config

# Adjust import path to reach parent directory for shared modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader
from scripts import system_utils

# --- Constants ---
GOOGLE_DNS_IPV4 = ["8.8.8.8", "8.8.4.4"]
GOOGLE_DNS_IPV6 = ["2001:4860:4860::8888", "2001:4860:4860::8844"]
RESOLV_CONF_PATH = Path("/etc/resolv.conf")
SYSTEMD_RESOLVED_CONF_PATH = Path("/etc/systemd/resolved.conf")
DNF_CONF_PATH = Path("/etc/dnf/dnf.conf")

# --- Helper Functions (specific to this file) ---

def _backup_file(filepath: Path, sudo: bool = True) -> bool:
    """Creates a backup of a file, typically needing sudo for /etc files."""
    if not filepath.exists():
        con.print_info(f"File {filepath} does not exist, no backup needed.")
        return False 
    
    timestamp_suffix = f"{Path.cwd().name.replace(' ','_')}_{int(time.time())}"
    backup_path = filepath.with_name(f"{filepath.name}.backup_{timestamp_suffix}")
    # No loop for unique backup needed if timestamp is granular enough for a single script run.
    # If rerunning phase quickly, a counter might be better or more specific timestamp.

    con.print_info(f"Backing up {filepath} to {backup_path}...")
    try:
        if not sudo: 
            con.print_warning(f"Attempting non-sudo backup for {filepath}, may fail.")
        
        system_utils.run_command(
            ["sudo", "cp", "-pf", str(filepath), str(backup_path)],
            print_fn_info=con.print_info, print_fn_error=con.print_error
        )
        return True
    except Exception as e:
        con.print_warning(f"Could not back up {filepath}. Error: {e}")
        return False

def _append_to_file_sudo(filepath: Path, content_to_append: str):
    """Appends content to a file using sudo tee -a. Best for privileged files."""
    con.print_info(f"Ensuring content is appended to {filepath} (sudo):\n{content_to_append.strip()}")
    command_str = f"echo -e {shlex.quote(content_to_append)} | sudo tee -a {shlex.quote(str(filepath))} > /dev/null"
    system_utils.run_command(
        command_str,
        shell=True, 
        print_fn_info=con.print_info,
        print_fn_error=con.print_error
    )

# --- Phase Specific Functions ---

def _install_phase_packages(phase_cfg: dict) -> bool:
    """Installs DNF packages specified in the phase configuration."""
    dnf_packages = phase_cfg.get("dnf_packages", [])
    if not dnf_packages:
        con.print_info("No DNF packages specified for this sub-phase.")
        return True

    con.print_sub_step(f"Installing DNF packages: {', '.join(dnf_packages)}")
    try:
        cmd = ["sudo", "dnf", "install", "-y"] + dnf_packages
        system_utils.run_command(
            cmd, capture_output=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success("Specified DNF packages installed successfully.")
        return True
    except Exception: 
        return False

def _configure_dns() -> bool:
    """Configures system DNS, preferring systemd-resolved, then attempting /etc/resolv.conf."""
    con.print_sub_step("Configuring DNS...")
    systemd_active = False
    if RESOLV_CONF_PATH.is_symlink():
        try:
            link_target = os.readlink(RESOLV_CONF_PATH) 
            if "systemd" in link_target or "resolved" in link_target or "stub-resolv.conf" in link_target:
                systemd_active = True
                con.print_info(f"{RESOLV_CONF_PATH} is a symlink pointing to a systemd-resolved managed file: {link_target}")
        except OSError: pass 

    if not systemd_active: # If not a known symlink, check the service status
        try:
            # Check if systemd-resolved service is active and running
            status_proc = system_utils.run_command(
                ["systemctl", "is-active", "systemd-resolved.service"],
                capture_output=True, check=False, 
                print_fn_info=con.print_info 
            )
            if status_proc.returncode == 0 and status_proc.stdout.strip() == "active":
                systemd_active = True
                con.print_info("systemd-resolved.service is active.")
            else:
                con.print_info("systemd-resolved.service is not active or not found.")
        except (FileNotFoundError, subprocess.CalledProcessError): 
            con.print_info("systemctl command not found or failed; assuming systemd-resolved is not managing DNS.")
            pass 

    if systemd_active:
        con.print_info(f"systemd-resolved detected. Attempting to configure DNS via {SYSTEMD_RESOLVED_CONF_PATH}.")
        if not SYSTEMD_RESOLVED_CONF_PATH.exists():
            con.print_info(f"{SYSTEMD_RESOLVED_CONF_PATH} does not exist. Creating with default [Resolve] section.")
            # Create the file with sudo if it doesn't exist, with a [Resolve] header
            try:
                system_utils.run_command(
                    f"sudo mkdir -p {SYSTEMD_RESOLVED_CONF_PATH.parent} && "
                    f"echo '[Resolve]' | sudo tee {SYSTEMD_RESOLVED_CONF_PATH} > /dev/null",
                    shell=True, check=True, print_fn_info=con.print_info
                )
            except Exception as e_create:
                con.print_error(f"Failed to create {SYSTEMD_RESOLVED_CONF_PATH}: {e_create}")
                return False
        
        _backup_file(SYSTEMD_RESOLVED_CONF_PATH) 
        
        try:
            # Use ConfigParser to manage resolved.conf (it's an INI-like file)
            parser = configparser.ConfigParser(comment_prefixes=('#',';'), allow_no_value=True, strict=False)
            # Read current config (sudo cat needed as resolved.conf is root-owned)
            read_proc = system_utils.run_command(
                ["sudo", "cat", str(SYSTEMD_RESOLVED_CONF_PATH)], capture_output=True, check=True,
                print_fn_info=con.print_info
            )
            parser.read_string(read_proc.stdout)

            if not parser.has_section("Resolve"):
                parser.add_section("Resolve")

            changes_made = False
            # Combine IPv4 and IPv6 DNS servers into a single space-separated string for systemd-resolved
            all_google_dns = GOOGLE_DNS_IPV4 + GOOGLE_DNS_IPV6
            dns_servers_str = " ".join(all_google_dns)
            
            current_dns = parser.get("Resolve", "DNS", fallback="").strip()
            # Check if all our DNS servers are already present (order might differ)
            all_present = True
            current_dns_list = current_dns.split()
            for dns_ip in all_google_dns:
                if dns_ip not in current_dns_list:
                    all_present = False
                    break
            
            if not all_present or current_dns != dns_servers_str: # If not all present or string differs (e.g. order)
                parser.set("Resolve", "DNS", dns_servers_str)
                changes_made = True
            
            domains_setting = "~." # Use these DNS servers for all domains
            if parser.get("Resolve", "Domains", fallback="") != domains_setting:
                parser.set("Resolve", "Domains", domains_setting)
                changes_made = True

            if changes_made:
                con.print_info(f"Updating DNS settings in {SYSTEMD_RESOLVED_CONF_PATH}...")
                temp_resolved_conf = Path(f"/tmp/resolved_conf_new_{os.getpid()}_{int(time.time())}.conf")
                with open(temp_resolved_conf, 'w', encoding='utf-8') as f_write:
                    parser.write(f_write, space_around_delimiters=False)
                
                system_utils.run_command(["sudo", "cp", str(temp_resolved_conf), str(SYSTEMD_RESOLVED_CONF_PATH)], print_fn_info=con.print_info)
                system_utils.run_command(["sudo", "chown", "root:systemd-resolve", str(SYSTEMD_RESOLVED_CONF_PATH)], print_fn_info=con.print_info) # Correct ownership
                system_utils.run_command(["sudo", "chmod", "644", str(SYSTEMD_RESOLVED_CONF_PATH)], print_fn_info=con.print_info)
                temp_resolved_conf.unlink()

                con.print_info("Restarting systemd-resolved to apply DNS changes...")
                system_utils.run_command(["sudo", "systemctl", "restart", "systemd-resolved.service"], print_fn_info=con.print_info, print_fn_error=con.print_error)
                system_utils.run_command(["sudo", "resolvectl", "flush-caches"], print_fn_info=con.print_info, print_fn_error=con.print_error) # Also flush caches
                con.print_success("systemd-resolved configuration updated for DNS.")
            else:
                 con.print_info(f"No changes required for systemd-resolved DNS configuration in {SYSTEMD_RESOLVED_CONF_PATH}.")
            return True
        except Exception as e: 
            con.print_error(f"Failed to configure systemd-resolved via {SYSTEMD_RESOLVED_CONF_PATH}: {e}")
            return False
    
    # Fallback if systemd-resolved is not clearly active or configuration failed
    con.print_info(f"systemd-resolved not detected or configuration failed. Checking {RESOLV_CONF_PATH} for NetworkManager.")
    try:
        resolv_content_fallback = ""
        if RESOLV_CONF_PATH.exists(): 
            resolv_content_fallback = RESOLV_CONF_PATH.read_text()

        if "NetworkManager" in resolv_content_fallback: 
            con.print_warning(f"{RESOLV_CONF_PATH} seems to be managed by NetworkManager.")
            con.print_info("Automatic DNS configuration for NetworkManager is complex for a generic script and can be connection-specific.")
            con.print_info(f"If you use NetworkManager, please configure DNS manually via its settings (e.g., nm-connection-editor or nmtui),")
            con.print_info(f"or using nmcli for your active connection(s). Example for 'Wired connection 1':")
            con.print_info(f"  sudo nmcli con mod \"Wired connection 1\" ipv4.dns \"{GOOGLE_DNS_IPV4[0]} {GOOGLE_DNS_IPV4[1]}\"")
            con.print_info(f"  sudo nmcli con mod \"Wired connection 1\" ipv6.dns \"{GOOGLE_DNS_IPV6[0]} {GOOGLE_DNS_IPV6[1]}\"")
            con.print_info(f"  sudo nmcli con mod \"Wired connection 1\" ipv4.ignore-auto-dns yes ipv6.ignore-auto-dns yes") # Important
            con.print_info(f"  sudo nmcli con up \"Wired connection 1\"  # Reactivate to apply")
            return True # Non-fatal, user informed to take manual action.
    except Exception: pass 

    con.print_warning(f"Fallback: Attempting to directly append to {RESOLV_CONF_PATH} (might be overwritten by system).")
    _backup_file(RESOLV_CONF_PATH) 
    
    lines_to_add_to_resolv = []
    current_resolv_text_fallback = ""
    if RESOLV_CONF_PATH.exists(): 
        current_resolv_text_fallback = RESOLV_CONF_PATH.read_text()

    for dns_ip in GOOGLE_DNS_IPV4 + GOOGLE_DNS_IPV6:
        entry = f"nameserver {dns_ip}"
        if entry not in current_resolv_text_fallback: 
            lines_to_add_to_resolv.append(entry)
    
    if lines_to_add_to_resolv:
        try:
            # Prepend new nameservers to give them priority if file is read top-down
            content_to_add = "\n".join(lines_to_add_to_resolv) + "\n"
            if current_resolv_text_fallback: # If file had content, prepend to existing
                 # Remove any existing Google DNS to avoid duplicates before prepending
                cleaned_existing_content_lines = [
                    line for line in current_resolv_text_fallback.splitlines()
                    if not any(google_ip in line for google_ip in GOOGLE_DNS_IPV4 + GOOGLE_DNS_IPV6)
                ]
                new_content = content_to_add + "\n".join(cleaned_existing_content_lines)
            else:
                new_content = content_to_add

            # Write the new content using sudo tee (overwrite)
            cmd_write_resolv = f"echo -e {shlex.quote(new_content.strip())} | sudo tee {shlex.quote(str(RESOLV_CONF_PATH))} > /dev/null"
            system_utils.run_command(cmd_write_resolv, shell=True, check=True)
            con.print_success(f"DNS entries updated in {RESOLV_CONF_PATH}. System may overwrite this if not using systemd-resolved.")
        except Exception as e_direct_write: 
            con.print_error(f"Failed to directly write to {RESOLV_CONF_PATH}: {e_direct_write}")
            return False
    else:
        con.print_info(f"Google DNS entries already seem present in {RESOLV_CONF_PATH}.")
    return True

def _configure_dnf_performance() -> bool:
    con.print_sub_step("Configuring DNF for performance and behavior...")
    if not DNF_CONF_PATH.exists():
        con.print_warning(f"{DNF_CONF_PATH} does not exist. Cannot configure DNF.")
        return True 

    _backup_file(DNF_CONF_PATH) 
    
    settings_to_set = {
        "max_parallel_downloads": "10",
        "fastestmirror": "True",
        "defaultyes": "True",    # Added
        "keepcache": "True"      # Added
    }
    
    parser = configparser.ConfigParser(comment_prefixes=('#'), allow_no_value=True, strict=False)
    changes_made = False
    try:
        with open(DNF_CONF_PATH, 'r', encoding='utf-8') as f_read:
            parser.read_file(f_read) 
        
        if not parser.has_section("main"):
            parser.add_section("main")
            changes_made = True 

        for key, value in settings_to_set.items():
            if not parser.has_option("main", key) or parser.get("main", key) != value:
                parser.set("main", key, value)
                changes_made = True
        
        if changes_made:
            con.print_info(f"Updating DNF settings in {DNF_CONF_PATH}...")
            temp_config_path = Path(f"/tmp/dnf_conf_new_{os.getpid()}_{int(time.time())}.conf")
            with open(temp_config_path, 'w', encoding='utf-8') as f_write:
                parser.write(f_write, space_around_delimiters=False) 
            
            system_utils.run_command(["sudo", "cp", str(temp_config_path), str(DNF_CONF_PATH)], print_fn_info=con.print_info, print_fn_error=con.print_error)
            system_utils.run_command(["sudo", "chown", "root:root", str(DNF_CONF_PATH)], print_fn_info=con.print_info, print_fn_error=con.print_error)
            system_utils.run_command(["sudo", "chmod", "644", str(DNF_CONF_PATH)], print_fn_info=con.print_info, print_fn_error=con.print_error)
            temp_config_path.unlink() 
            con.print_success("DNF configuration updated successfully.")
        else:
            con.print_info("DNF configuration settings already up-to-date.")
        return True
    except configparser.Error as e:
        con.print_error(f"Error parsing {DNF_CONF_PATH}: {e}. DNF config not updated.")
        return False
    except IOError as e:
        con.print_error(f"I/O error with DNF configuration: {e}. DNF config not updated.")
        return False
    except Exception as e:
        con.print_error(f"Failed to configure DNF: {e}")
        # Attempt to clean up temp file if it exists
        temp_file_to_check_on_error = Path(f"/tmp/dnf_conf_new_{os.getpid()}_{int(time.time())}.conf")
        if temp_file_to_check_on_error.exists():
            try:
                temp_file_to_check_on_error.unlink()
            except OSError:
                pass # Ignore if unlink fails during error handling
        return False

def _setup_rpm_fusion() -> bool:
    """Sets up RPM Fusion free and non-free repositories."""
    con.print_sub_step("Setting up RPM Fusion repositories...")
    try:
        # Check if already installed to be somewhat idempotent
        # rpm -q returns 0 if all packages are found, 1 if any are not or other error.
        # We check them individually to give more specific feedback if one is missing.
        free_installed = system_utils.run_command(
            ["rpm", "-q", "rpmfusion-free-release"], capture_output=True, check=False
        ).returncode == 0
        nonfree_installed = system_utils.run_command(
            ["rpm", "-q", "rpmfusion-nonfree-release"], capture_output=True, check=False
        ).returncode == 0

        if free_installed and nonfree_installed:
            con.print_info("RPM Fusion free and non-free repositories seem to be already installed.")
            return True
        elif free_installed:
            con.print_info("RPM Fusion free repository is installed, but non-free is missing. Will install non-free.")
        elif nonfree_installed:
            con.print_info("RPM Fusion non-free repository is installed, but free is missing. Will install free.")
        else:
            con.print_info("RPM Fusion repositories not found. Will install both.")

    except FileNotFoundError: 
        con.print_warning("'rpm' command not found. Cannot check for existing RPM Fusion. Proceeding with install attempt.")
    # If CalledProcessError with check=False, it means the command ran but failed (e.g. rpm db issue).
    # system_utils.run_command would log this. We proceed with install attempt.

    try:
        fedora_version_proc = system_utils.run_command(
            "rpm -E %fedora", capture_output=True, shell=True, check=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error
        )
        fedora_version = fedora_version_proc.stdout.strip()
        if not fedora_version or not fedora_version.isdigit():
            con.print_error(f"Could not determine a valid Fedora version (got: '{fedora_version}'). Cannot setup RPM Fusion.")
            return False

        rpm_fusion_free_url = f"https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-{fedora_version}.noarch.rpm"
        rpm_fusion_nonfree_url = f"https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-{fedora_version}.noarch.rpm"
        
        packages_to_install_rpmfusion = []
        if not free_installed: packages_to_install_rpmfusion.append(rpm_fusion_free_url)
        if not nonfree_installed: packages_to_install_rpmfusion.append(rpm_fusion_nonfree_url)

        if not packages_to_install_rpmfusion: # Should not happen if logic above is correct, but defensive
            con.print_info("RPM Fusion repositories are already set up.")
            return True

        cmd_install_rpmfusion = ["sudo", "dnf", "install", "-y"] + packages_to_install_rpmfusion
        system_utils.run_command(
            cmd_install_rpmfusion, capture_output=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success("RPM Fusion repositories enabled/updated.")
        return True
    except Exception: # Error already logged by run_command
        return False

def _update_system() -> bool:
    """Updates all system packages using 'dnf upgrade'."""
    con.print_sub_step("Updating system (sudo dnf upgrade -y)...")
    try:
        # This is a long-running command, capture_output=False lets output stream to console
        system_utils.run_command(
            ["sudo", "dnf", "upgrade", "-y"], capture_output=False, # Stream output
            print_fn_info=con.print_info, print_fn_error=con.print_error
        )
        con.print_success("System updated successfully.")
        return True
    except Exception: # Error already logged by run_command
        return False

def _setup_flatpak() -> bool:
    """Sets up the Flathub repository for Flatpak system-wide."""
    con.print_sub_step("Setting up Flathub repository for Flatpak...")
    try:
        check_cmd = ["flatpak", "remotes", "--system"]
        remotes_process = system_utils.run_command(
            check_cmd, capture_output=True, check=False, print_fn_info=con.print_info
        )
        
        flathub_found = False
        if remotes_process.returncode == 0 and remotes_process.stdout:
            for line in remotes_process.stdout.strip().splitlines():
                if line.strip().startswith("flathub"): # Check if 'flathub' is listed as a remote name
                    flathub_found = True
                    break
        
        if flathub_found:
            con.print_info("Flathub remote 'flathub' already exists (system-wide).")
            return True
        
        con.print_info("Flathub remote not found or not configured. Attempting to add system-wide...")
        cmd_add_flathub = [
            "sudo", "flatpak", "remote-add", "--if-not-exists", 
            "flathub", "https://dl.flathub.org/repo/flathub.flatpakrepo"
        ]
        system_utils.run_command(
            cmd_add_flathub, capture_output=True, check=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success("Flathub repository added for Flatpak (system-wide).")
        return True
    except FileNotFoundError: 
        con.print_warning("'flatpak' command not found. Is Flatpak installed?")
        con.print_info("Consider adding 'flatpak' to 'phase1_system_preparation.dnf_packages' in your packages.yaml.")
        return False 
    except subprocess.CalledProcessError as e: 
        con.print_error(f"Failed to setup Flathub repository. Error: {e}")
        if e.stdout: con.print_error(f"STDOUT: {e.stdout.strip()}")
        if e.stderr: con.print_error(f"STDERR: {e.stderr.strip()}")
        return False
    except Exception as e: 
        con.print_error(f"An unexpected error occurred during Flathub setup: {e}")
        return False

def _set_hostname() -> bool:
    """Interactively sets the system hostname."""
    con.print_sub_step("Setting system hostname...")
    try:
        current_hostname_proc = system_utils.run_command(
            ["hostnamectl", "status", "--static"], capture_output=True, check=False, 
            print_fn_info=con.print_info
        )
        if current_hostname_proc.returncode != 0: # hostnamectl failed or not present
            # Fallback to 'hostname' command
            current_hostname_proc = system_utils.run_command(
                ["hostname"], capture_output=True, check=True, 
                print_fn_info=con.print_info
            )
        current_hostname = current_hostname_proc.stdout.strip()
        con.print_info(f"Current hostname: {current_hostname}")

        if con.confirm_action(f"Do you want to change the hostname from '{current_hostname}'?", default=False):
            new_hostname = ""
            while not new_hostname: 
                new_hostname = con.ask_question("Enter the new hostname:").strip()
                if not new_hostname:
                    con.print_warning("Hostname cannot be empty. Please try again or cancel.")
                    if not con.confirm_action("Try entering hostname again?", default=True):
                        con.print_info("Hostname change cancelled by user.")
                        return True 

            if new_hostname != current_hostname:
                system_utils.run_command(
                    ["sudo", "hostnamectl", "set-hostname", new_hostname],
                    print_fn_info=con.print_info, print_fn_error=con.print_error
                )
                con.print_success(f"Hostname changed to '{new_hostname}'. A reboot might be needed for all services to see the change.")
            else:
                con.print_info("New hostname is the same as current. Hostname unchanged.")
        else:
            con.print_info("Hostname change skipped by user.")
        return True
    except FileNotFoundError: 
        con.print_error("'hostnamectl' or 'hostname' command not found. Cannot set hostname.")
        return False
    except Exception: # Other errors, already logged by run_command
        return False

# --- Main Phase Function ---

def run_phase1(app_config: dict) -> bool:
    """Executes Phase 1: System Preparation."""
    con.print_step("PHASE 1: System Preparation")
    critical_success = True 
    
    phase1_config_data = config_loader.get_phase_data(app_config, "phase1_system_preparation")

    # Task sequence:
    con.print_info("Step 1: Installing core packages for Phase 1 (e.g., dnf5, flatpak if specified)...")
    if not _install_phase_packages(phase1_config_data):
        con.print_error("Failed to install core DNF packages for Phase 1. This is critical.")
        critical_success = False

    if critical_success: 
        con.print_info("Step 2: Configuring DNF performance and behavior...")
        if not _configure_dnf_performance(): # Updated with new settings
            con.print_warning("DNF configuration encountered issues. Continuing...")

        con.print_info("Step 3: Setting up RPM Fusion repositories...")
        if not _setup_rpm_fusion():
            con.print_error("RPM Fusion setup failed. This may impact package availability.")
            critical_success = False 

    if critical_success: 
        con.print_info("Step 4: Configuring DNS...")
        if not _configure_dns():
            con.print_error("DNS configuration encountered issues. Network operations might fail or be slow.")
            critical_success = False # DNS is fairly critical

    if critical_success: 
        con.print_info("Step 5: Cleaning DNF metadata and updating system...")
        try:
            system_utils.run_command(
                ["sudo", "dnf", "clean", "all"], capture_output=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error
            )
        except Exception as e: # Error already logged
            con.print_warning(f"DNF clean all failed: {e}. Proceeding with upgrade attempt.")

        if not _update_system():
            con.print_error("CRITICAL: System update failed. Subsequent phases may be unstable.")
            critical_success = False
    
    # These are less critical for the system's core operation but important for user setup
    con.print_info("Step 6: Setting up Flathub repository for Flatpak...")
    if not _setup_flatpak():
        con.print_warning("Flatpak (Flathub) setup encountered issues. This may affect Flatpak app installations in later phases.")
        # Not marking critical_success = False, but it's a significant warning.

    con.print_info("Step 7: Setting system hostname...")
    if not _set_hostname():
        con.print_warning("Setting hostname encountered issues. Non-critical for phase success.")

    if critical_success:
        con.print_success("Phase 1: System Preparation completed successfully.")
    else:
        con.print_error("Phase 1: System Preparation completed with CRITICAL errors. Please review the output.")
    
    return critical_success