# Fedora-AutoEnv-Setup/scripts/phase1_system_preparation.py

import subprocess
import shutil
import os
import sys
from pathlib import Path

# Adjust import path to reach parent directory for console_output and config_loader
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import config_loader # To get dnf_packages for this phase

# --- Constants ---
GOOGLE_DNS_IPV4 = ["8.8.8.8", "8.8.4.4"]
GOOGLE_DNS_IPV6 = ["2001:4860:4860::8888", "2001:4860:4860::8844"]
RESOLV_CONF_PATH = Path("/etc/resolv.conf")
SYSTEMD_RESOLVED_CONF_PATH = Path("/etc/systemd/resolved.conf")
DNF_CONF_PATH = Path("/etc/dnf/dnf.conf")

# --- Helper Functions ---

def _run_command(command: list[str], capture_output: bool = False, check: bool = True, shell: bool = False) -> subprocess.CompletedProcess:
    """Runs a shell command."""
    command_str = ' '.join(command) if not shell else command[0]
    con.print_info(f"Executing: {command_str}")
    try:
        process = subprocess.run(
            command if not shell else command_str,
            check=check,
            capture_output=capture_output,
            text=True,
            shell=shell
        )
        if process.stdout and capture_output:
            stdout_summary = (process.stdout[:200] + '...') if len(process.stdout) > 200 else process.stdout
            con.print_sub_step(f"STDOUT: {stdout_summary.strip()}")
        if process.stderr and capture_output:
            stderr_summary = (process.stderr[:200] + '...') if len(process.stderr) > 200 else process.stderr
            con.print_sub_step(f"STDERR: {stderr_summary.strip()}")
        return process
    except subprocess.CalledProcessError as e:
        con.print_error(f"Command failed with exit code {e.returncode}: {command_str}")
        if e.stdout:
            con.print_error(f"STDOUT: {e.stdout.strip()}")
        if e.stderr:
            con.print_error(f"STDERR: {e.stderr.strip()}")
        raise
    except FileNotFoundError:
        con.print_error(f"Command not found: {command[0]}")
        raise

def _file_contains_text(filepath: Path, text: str, sudo_read: bool = False) -> bool:
    """Checks if a file contains a specific text, optionally reading with sudo."""
    if not filepath.exists():
        return False
    try:
        content = ""
        if sudo_read:
            # This assumes `cat` is available and sudo is configured.
            # It's a workaround for reading privileged files without changing script's own UID.
            proc = _run_command(["sudo", "cat", str(filepath)], capture_output=True, check=True)
            content = proc.stdout
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        return text in content
    except IOError: # For non-sudo read
        return False
    except subprocess.CalledProcessError: # For sudo_read failure
        con.print_warning(f"Could not sudo read {filepath} to check content.")
        return False


def _append_to_file(filepath: Path, content: str, sudo: bool = True):
    """Appends content to a file, using sudo tee -a if necessary."""
    con.print_info(f"Ensuring content in {filepath}:\n{content.strip()}")
    if sudo:
        # Use shell process substitution with tee for atomicity and permissions
        # This is complex to make truly safe with arbitrary content.
        # A simpler echo | sudo tee -a is more common.
        # Ensure content doesn't break the shell command.
        # Python's shlex.quote could be useful here if content was more variable.
        # For fixed strings, it's usually okay.
        
        # Create a temporary script for sudo to execute
        # This avoids complex quoting issues with echo and special characters in `content`
        temp_script_path = Path(f"/tmp/append_script_{os.getpid()}.sh")
        script_content = f"""#!/bin/bash
echo -e "{content.replace('"', '\\"')}" >> "{filepath}"
""" # Basic escaping for double quotes within content, assuming content is simple.
        # A more robust solution for arbitrary content would involve base64 encoding/decoding
        # or writing content to a temp file and using `sudo dd if=temp_file of=filepath conv=notrunc oflag=append`

        try:
            with open(temp_script_path, "w") as f:
                f.write(script_content)
            os.chmod(temp_script_path, 0o700)
            _run_command(["sudo", str(temp_script_path)])
        finally:
            if temp_script_path.exists():
                temp_script_path.unlink()

    else: # Non-sudo append
        try:
            with open(filepath, 'a', encoding='utf-8') as f: # Changed encoding
                f.write(content)
        except IOError as e:
            con.print_error(f"Failed to append to {filepath}: {e}")
            raise

def _backup_file(filepath: Path, sudo: bool = True) -> bool:
    """Creates a backup of a file."""
    if filepath.exists():
        # Try to make backup name more unique to avoid collisions if script runs multiple times
        # or if other .backup files exist.
        timestamp = Path.cwd().name # Using project dir name as pseudo-timestamp for this example.
                                   # A real timestamp would be `datetime.now().strftime("%Y%m%d%H%M%S")`
        backup_path = filepath.with_name(f"{filepath.name}.backup_{timestamp}")
        counter = 0
        while backup_path.exists(): # Avoid overwriting previous backups from same "session"
            counter += 1
            backup_path = filepath.with_name(f"{filepath.name}.backup_{timestamp}_{counter}")

        con.print_info(f"Backing up {filepath} to {backup_path}...")
        try:
            if sudo:
                _run_command(["sudo", "cp", "-pf", str(filepath), str(backup_path)]) # -p to preserve mode, ownership, timestamps
            else:
                shutil.copy2(filepath, backup_path) # copy2 also preserves metadata
            return True
        except Exception as e:
            con.print_warning(f"Could not back up {filepath}: {e}")
    return False

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
        _run_command(cmd, capture_output=True)
        con.print_success("Specified DNF packages installed successfully.")
        return True
    except Exception as e:
        con.print_error(f"Failed to install DNF packages: {e}")
        return False

def _configure_dns() -> bool:
    con.print_sub_step("Configuring DNS...")
    # Check if systemd-resolved is active and managing resolv.conf
    systemd_active = False
    if RESOLV_CONF_PATH.is_symlink():
        try:
            link_target = os.readlink(RESOLV_CONF_PATH)
            if "systemd" in link_target or "resolved" in link_target:
                systemd_active = True
        except OSError:
            pass # Could not read link, proceed with other checks

    if not systemd_active and SYSTEMD_RESOLVED_CONF_PATH.exists():
        # Check if systemd-resolved service is active even if symlink is different
        try:
            status_proc = _run_command(["systemctl", "is-active", "systemd-resolved.service"], capture_output=True, check=False)
            if status_proc.stdout.strip() == "active":
                systemd_active = True
        except FileNotFoundError: # systemctl not found (unlikely on Fedora)
            pass
        except subprocess.CalledProcessError: # service might not exist or other error
            pass


    if systemd_active:
        con.print_info(f"systemd-resolved detected. Attempting to configure via {SYSTEMD_RESOLVED_CONF_PATH}.")
        _backup_file(SYSTEMD_RESOLVED_CONF_PATH)
        
        try:
            current_config_content = ""
            if SYSTEMD_RESOLVED_CONF_PATH.exists(): # File might not exist if never configured
                 # Read with sudo as it's /etc/systemd/resolved.conf
                read_proc = _run_command(["sudo", "cat", str(SYSTEMD_RESOLVED_CONF_PATH)], capture_output=True, check=False)
                if read_proc.returncode == 0:
                    current_config_content = read_proc.stdout

            # Use a list to build new config lines or modifications
            config_changes_made = False
            new_lines_to_add = []

            if "[Resolve]" not in current_config_content:
                new_lines_to_add.append("[Resolve]")
                config_changes_made = True # Will need to add section header

            # Desired DNS settings
            dns_v4_str = ' '.join(GOOGLE_DNS_IPV4)
            dns_v6_str = ' '.join(GOOGLE_DNS_IPV6) # Using separate DNS line for IPv6

            # Check/add DNS for IPv4
            if not (f"DNS={dns_v4_str}" in current_config_content.replace(" ", "")): # Normalize spaces for check
                if "DNS=" in current_config_content: # If DNS line exists but is different
                     con.print_warning(f"Existing DNS setting found in {SYSTEMD_RESOLVED_CONF_PATH}. Overwriting with Google DNS for IPv4.")
                     # This part would require modifying existing lines, complex without INI parser
                     # For simplicity, we'll just append our desired line. Multiple DNS lines are allowed.
                new_lines_to_add.append(f"DNS={dns_v4_str}")
                config_changes_made = True
            else:
                con.print_info("Google DNS IPv4 already configured in systemd-resolved.")

            # Check/add DNS for IPv6 (as another DNS= line or FallbackDNS=)
            # systemd-resolved handles multiple DNS= lines.
            if not (f"DNS={dns_v6_str}" in current_config_content.replace(" ", "")):
                new_lines_to_add.append(f"DNS={dns_v6_str}") # Add IPv6 as another primary DNS
                config_changes_made = True
            else:
                con.print_info("Google DNS IPv6 already configured in systemd-resolved.")
            
            # Add Domains=~. to ensure these servers are used for all lookups
            if "Domains=~." not in current_config_content:
                new_lines_to_add.append("Domains=~.")
                config_changes_made = True
            else:
                con.print_info("Domains=~. already configured in systemd-resolved.")


            if config_changes_made and new_lines_to_add:
                # Append the new lines. If [Resolve] was added, it's first.
                # This assumes that if [Resolve] exists, it's correctly formatted.
                # A proper INI parser is safer.
                content_to_append = "\n" + "\n".join(new_lines_to_add) + "\n"
                _append_to_file(SYSTEMD_RESOLVED_CONF_PATH, content_to_append, sudo=True)
                con.print_info("Restarting systemd-resolved to apply DNS changes...")
                _run_command(["sudo", "systemctl", "restart", "systemd-resolved.service"])
                _run_command(["sudo", "resolvectl", "flush-caches"]) # May or may not be needed after restart
                con.print_success("systemd-resolved configuration updated for DNS.")
            elif not new_lines_to_add:
                 con.print_info("No changes required for systemd-resolved DNS configuration.")
            
            return True

        except Exception as e:
            con.print_error(f"Failed to configure systemd-resolved: {e}")
            con.print_warning("Manual DNS configuration might be required.")
            return False
    
    # Fallback for NetworkManager or direct edit (less ideal)
    try:
        resolv_content = RESOLV_CONF_PATH.read_text() if RESOLV_CONF_PATH.exists() else ""
        if "NetworkManager" in resolv_content:
            con.print_warning(f"{RESOLV_CONF_PATH} seems to be managed by NetworkManager.")
            # (Instructions from previous version are good here)
            con.print_info("Automatic DNS configuration for NetworkManager is complex and not implemented.")
            con.print_info(f"Please configure DNS manually, e.g., using nmcli for a connection 'CONNECTION_NAME':")
            con.print_info(f"  sudo nmcli con mod CONNECTION_NAME ipv4.dns \"{GOOGLE_DNS_IPV4[0]} {GOOGLE_DNS_IPV4[1]}\"")
            con.print_info(f"  sudo nmcli con mod CONNECTION_NAME +ipv4.dns \"{GOOGLE_DNS_IPV6[0]} {GOOGLE_DNS_IPV6[1]}\"") # Add IPv6
            con.print_info(f"  sudo nmcli con up CONNECTION_NAME")
            return True # Non-fatal, user informed
    except Exception: # Issue reading resolv.conf, perhaps permissions
        pass # Fall through to direct edit attempt if systemd-resolved not detected

    con.print_warning(f"Could not confirm systemd-resolved or NetworkManager. Attempting to append to {RESOLV_CONF_PATH} (might be overwritten).")
    _backup_file(RESOLV_CONF_PATH)
    dns_entries_to_add = []
    current_resolv_text = ""
    if RESOLV_CONF_PATH.exists():
        current_resolv_text = _run_command(["sudo", "cat", str(RESOLV_CONF_PATH)], capture_output=True).stdout

    for dns_ip in GOOGLE_DNS_IPV4 + GOOGLE_DNS_IPV6:
        entry = f"nameserver {dns_ip}"
        if entry not in current_resolv_text:
            dns_entries_to_add.append(entry)
    
    if dns_entries_to_add:
        try:
            _append_to_file(RESOLV_CONF_PATH, "\n" + "\n".join(dns_entries_to_add) + "\n", sudo=True)
            con.print_success(f"DNS entries added to {RESOLV_CONF_PATH}. System may overwrite this.")
        except Exception as e:
            con.print_error(f"Failed to write to {RESOLV_CONF_PATH}: {e}")
            return False
    else:
        con.print_info(f"Google DNS entries already seem present in {RESOLV_CONF_PATH}.")
    return True


def _configure_dnf_performance() -> bool:
    con.print_sub_step("Configuring DNF for performance...")
    _backup_file(DNF_CONF_PATH)
    
    settings = {
        "max_parallel_downloads": "10",
        "fastestmirror": "True"
    }
    
    # Using configparser for safer INI manipulation
    import configparser
    parser = configparser.ConfigParser(comment_prefixes=('#'), allow_no_value=True) # allow_no_value for comments
    
    try:
        # Read existing config with sudo if necessary
        if DNF_CONF_PATH.exists():
            read_proc = _run_command(["sudo", "cat", str(DNF_CONF_PATH)], capture_output=True, check=False)
            if read_proc.returncode == 0:
                parser.read_string(read_proc.stdout)
            else: # File might be empty or unreadable even by sudo cat (very unlikely)
                con.print_warning(f"Could not read {DNF_CONF_PATH} for DNF performance config. Starting fresh.")
        
        if not parser.has_section("main"):
            parser.add_section("main")
            con.print_info("Added [main] section to DNF config.")

        changes_made = False
        for key, value in settings.items():
            if not parser.has_option("main", key) or parser.get("main", key) != value:
                parser.set("main", key, value)
                changes_made = True
        
        if changes_made:
            # Write changes using sudo tee
            temp_config_content_path = Path(f"/tmp/dnf_conf_new_{os.getpid()}.conf")
            with open(temp_config_content_path, 'w', encoding='utf-8') as f:
                parser.write(f, space_around_delimiters=False) # Keep it compact like dnf.conf often is
            
            # Replace the file using sudo
            _run_command(["sudo", "cp", str(temp_config_content_path), str(DNF_CONF_PATH)])
            _run_command(["sudo", "chown", "root:root", str(DNF_CONF_PATH)]) # Ensure ownership
            _run_command(["sudo", "chmod", "644", str(DNF_CONF_PATH)])      # Ensure permissions
            
            temp_config_content_path.unlink() # Clean up temp file
            con.print_success("DNF performance settings updated.")
        else:
            con.print_info("DNF performance settings already up-to-date.")
            
        return True
    except Exception as e:
        con.print_error(f"Failed to configure DNF performance: {e}")
        # Clean up temp file in case of error during write process
        temp_file_to_check = Path(f"/tmp/dnf_conf_new_{os.getpid()}.conf")
        if temp_file_to_check.exists():
            temp_file_to_check.unlink()
        return False


def _setup_rpm_fusion() -> bool:
    con.print_sub_step("Setting up RPM Fusion repositories...")
    try:
        # Check if already installed
        rpm_check_cmd = ["rpm", "-q", "rpmfusion-free-release", "rpmfusion-nonfree-release"]
        process = _run_command(rpm_check_cmd, capture_output=True, check=False) # check=False as non-zero means not installed
        if process.returncode == 0 and "is not installed" not in process.stdout and "is not installed" not in process.stderr:
            con.print_info("RPM Fusion repositories seem to be already installed.")
            return True
    except FileNotFoundError: # rpm command not found
        con.print_warning("'rpm' command not found. Cannot check for existing RPM Fusion.")
    except subprocess.CalledProcessError: # Should not happen with check=False, but defensively
        pass # Proceed with installation attempt

    try:
        fedora_version_cmd = "rpm -E %fedora"
        fedora_version = _run_command([fedora_version_cmd], capture_output=True, shell=True, check=True).stdout.strip()
        if not fedora_version:
            con.print_error("Could not determine Fedora version using 'rpm -E %fedora'.")
            return False

        rpm_fusion_free_url = f"https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-{fedora_version}.noarch.rpm"
        rpm_fusion_nonfree_url = f"https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-{fedora_version}.noarch.rpm"

        cmd_install_rpmfusion = ["sudo", "dnf", "install", "-y", rpm_fusion_free_url, rpm_fusion_nonfree_url]
        _run_command(cmd_install_rpmfusion, capture_output=True)
        con.print_success("RPM Fusion repositories enabled.")
        return True
    except Exception as e:
        con.print_error(f"Failed to set up RPM Fusion: {e}")
        return False

def _update_system() -> bool:
    con.print_sub_step("Updating system (sudo dnf upgrade -y)...")
    try:
        _run_command(["sudo", "dnf", "upgrade", "-y"], capture_output=False) # Long running, no need to capture all output
        con.print_success("System updated successfully.")
        return True
    except Exception as e:
        con.print_error(f"System update failed: {e}")
        return False

def _setup_flatpak() -> bool:
    con.print_sub_step("Setting up Flathub repository for Flatpak...")
    try:
        check_cmd = ["flatpak", "remotes", "--system"]
        # Allow check to fail if no remotes or flatpak not fully set up
        remotes_process = _run_command(check_cmd, capture_output=True, check=False)
        if remotes_process.returncode == 0 and "flathub" in remotes_process.stdout:
            con.print_info("Flathub remote already exists (system-wide).")
            return True
        
        # Also check user remotes, though system is preferred for this script
        check_user_cmd = ["flatpak", "remotes", "--user"]
        user_remotes_process = _run_command(check_user_cmd, capture_output=True, check=False)
        if user_remotes_process.returncode == 0 and "flathub" in user_remotes_process.stdout:
            con.print_info("Flathub remote already exists (user). Consider adding system-wide if needed.")
            # Still attempt to add system-wide if not present there
            if not (remotes_process.returncode == 0 and "flathub" in remotes_process.stdout):
                 con.print_info("Attempting to add Flathub system-wide.")
            else: # Already system-wide
                 return True


        cmd = ["sudo", "flatpak", "remote-add", "--if-not-exists", "flathub", "https://dl.flathub.org/repo/flathub.flatpakrepo"]
        _run_command(cmd, capture_output=True)
        con.print_success("Flathub repository added for Flatpak (system-wide).")
        return True
    except FileNotFoundError:
        con.print_warning("'flatpak' command not found. Is Flatpak installed?")
        return False # Flatpak command itself is missing
    except Exception as e:
        con.print_error(f"Failed to set up Flathub: {e}")
        return False

def _set_hostname() -> bool:
    con.print_sub_step("Setting system hostname...")
    try:
        # hostnamectl might not be available on minimal installs, but generally is on Fedora Workstation/Server
        current_hostname_proc = _run_command(["hostnamectl", "status", "--static"], capture_output=True, check=False)
        if current_hostname_proc.returncode != 0: # Fallback if hostnamectl fails or not present
            current_hostname_proc = _run_command(["hostname"], capture_output=True, check=True)

        current_hostname = current_hostname_proc.stdout.strip()
        con.print_info(f"Current hostname: {current_hostname}")

        if con.confirm_action(f"Do you want to change the hostname from '{current_hostname}'?", default=False):
            new_hostname = ""
            while not new_hostname: # Loop until a non-empty hostname is provided
                new_hostname = con.ask_question("Enter the new hostname:").strip()
                if not new_hostname:
                    con.print_warning("Hostname cannot be empty. Please try again or cancel.")
                    if not con.confirm_action("Try entering hostname again?", default=True):
                        con.print_info("Hostname change cancelled.")
                        return True # User cancelled, not an error for the step itself

            if new_hostname != current_hostname:
                _run_command(["sudo", "hostnamectl", "set-hostname", new_hostname])
                con.print_success(f"Hostname changed to '{new_hostname}'. A reboot might be needed for all services to see the change.")
            else:
                con.print_info("New hostname is the same as current. Unchanged.")
        else:
            con.print_info("Hostname unchanged.")
        return True
    except FileNotFoundError:
        con.print_error("'hostnamectl' or 'hostname' command not found. Cannot set hostname.")
        return False
    except Exception as e:
        con.print_error(f"Failed to set hostname: {e}")
        return False

# --- Main Phase Function ---

def run_phase1(app_config: dict) -> bool:
    """
    Executes Phase 1: System Preparation.
    """
    con.print_step("PHASE 1: System Preparation")
    # Track overall success of critical parts of the phase
    # Non-critical failures might log a warning but not cause the phase to "fail"
    critical_success = True 
    
    phase1_config_data = config_loader.get_phase_data(app_config, "phase1_system_preparation")

    # Task sequence:
    # 1. Install base packages for this phase (e.g., dnf5, dnf-utils)
    # 2. Configure DNF performance (might be good before large downloads)
    # 3. Setup RPM Fusion (needed for some packages/drivers before system update)
    # 4. Configure DNS (important for all network operations)
    # 5. Clean DNF and Update System
    # 6. Setup Flatpak
    # 7. Set Hostname

    con.print_info("Step 1: Installing core packages for Phase 1 (including dnf5 if specified)...")
    if not _install_phase_packages(phase1_config_data):
        con.print_warning("Problem installing core DNF packages for Phase 1. Subsequent DNF operations might be affected.")

    con.print_info("Step 2: Configuring DNF performance...")
    if not _configure_dnf_performance():
        con.print_warning("DNF performance configuration encountered issues.")
        # Not setting critical_success = False, as system can still operate.

    con.print_info("Step 3: Setting up RPM Fusion repositories...")
    if not _setup_rpm_fusion():
        critical_success = False # RPM Fusion is often key.
        con.print_warning("RPM Fusion setup failed. Some packages/drivers might not be available.")

    con.print_info("Step 4: Configuring DNS...")
    if not _configure_dns():
        critical_success = False # DNS is critical for network operations.
        con.print_warning("DNS configuration encountered issues. Network operations might fail or be slow.")

    con.print_info("Step 5: Cleaning DNF metadata and updating system...")
    try:
        _run_command(["sudo", "dnf", "clean", "all"], capture_output=True)
    except Exception as e:
        con.print_warning(f"dnf clean all failed, proceeding with upgrade anyway: {e}")

    if not _update_system():
        critical_success = False # A failed system update is critical.
        con.print_error("CRITICAL: System update failed. Subsequent phases may be unstable.")

    con.print_info("Step 6: Setting up Flathub repository for Flatpak...")
    if not _setup_flatpak():
        con.print_warning("Flatpak (Flathub) setup encountered issues.")
        # Not critical for system stability, but important for apps.

    con.print_info("Step 7: Setting system hostname...")
    if not _set_hostname():
        con.print_warning("Setting hostname encountered issues.")
        # Not critical for most operations.

    if critical_success:
        con.print_success("Phase 1: System Preparation completed successfully.")
    else:
        con.print_error("Phase 1: System Preparation completed with CRITICAL errors. Please review the output.")
    
    return critical_success