# Fedora-AutoEnv-Setup/scripts/phase1_system_preparation.py

import subprocess
import shutil
import os
import sys
from pathlib import Path
import configparser # For DNF configuration
import shlex # For _append_to_file_sudo

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
    
    timestamp_suffix = Path.cwd().name 
    backup_path = filepath.with_name(f"{filepath.name}.backup_{timestamp_suffix}")
    counter = 0
    while backup_path.exists(): 
        counter += 1
        backup_path = filepath.with_name(f"{filepath.name}.backup_{timestamp_suffix}_{counter}")

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
    con.print_sub_step("Configuring DNS...")
    systemd_active = False
    if RESOLV_CONF_PATH.is_symlink():
        try:
            link_target = os.readlink(RESOLV_CONF_PATH) 
            if "systemd" in link_target or "resolved" in link_target:
                systemd_active = True
        except OSError: pass 

    if not systemd_active and SYSTEMD_RESOLVED_CONF_PATH.exists(): 
        try:
            status_proc = system_utils.run_command(
                ["systemctl", "is-active", "systemd-resolved.service"],
                capture_output=True, check=False, 
                print_fn_info=con.print_info 
            )
            if status_proc.returncode == 0 and status_proc.stdout.strip() == "active":
                systemd_active = True
        except (FileNotFoundError, subprocess.CalledProcessError): pass 

    if systemd_active:
        con.print_info(f"systemd-resolved detected. Attempting to configure via {SYSTEMD_RESOLVED_CONF_PATH}.")
        _backup_file(SYSTEMD_RESOLVED_CONF_PATH) 
        try:
            current_config_content = ""
            if SYSTEMD_RESOLVED_CONF_PATH.exists(): 
                read_proc = system_utils.run_command(
                    ["sudo", "cat", str(SYSTEMD_RESOLVED_CONF_PATH)], capture_output=True, check=False,
                    print_fn_info=con.print_info
                )
                if read_proc.returncode == 0: current_config_content = read_proc.stdout
            
            lines_to_ensure = []
            if "[Resolve]" not in current_config_content: lines_to_ensure.append("[Resolve]")
            
            dns_v4_line = f"DNS={ ' '.join(GOOGLE_DNS_IPV4) }"
            if dns_v4_line not in current_config_content.replace(" ", ""): lines_to_ensure.append(dns_v4_line)
            
            dns_v6_line = f"DNS={ ' '.join(GOOGLE_DNS_IPV6) }" 
            if dns_v6_line not in current_config_content.replace(" ", ""): lines_to_ensure.append(dns_v6_line)
            
            domains_line = "Domains=~." 
            if domains_line not in current_config_content: lines_to_ensure.append(domains_line)

            if lines_to_ensure:
                content_to_append = "\n" + "\n".join(lines_to_ensure) + "\n"
                _append_to_file_sudo(SYSTEMD_RESOLVED_CONF_PATH, content_to_append)
                
                con.print_info("Restarting systemd-resolved to apply DNS changes...")
                system_utils.run_command(["sudo", "systemctl", "restart", "systemd-resolved.service"], print_fn_info=con.print_info, print_fn_error=con.print_error)
                system_utils.run_command(["sudo", "resolvectl", "flush-caches"], print_fn_info=con.print_info, print_fn_error=con.print_error)
                con.print_success("systemd-resolved configuration updated for DNS.")
            else:
                 con.print_info("No changes required for systemd-resolved DNS configuration.")
            return True
        except Exception as e: 
            con.print_error(f"Failed to configure systemd-resolved: {e}")
            return False
    
    try:
        resolv_content = ""
        if RESOLV_CONF_PATH.exists(): 
            resolv_content = RESOLV_CONF_PATH.read_text()

        if "NetworkManager" in resolv_content: 
            con.print_warning(f"{RESOLV_CONF_PATH} seems to be managed by NetworkManager.")
            con.print_info("Automatic DNS configuration for NetworkManager is complex for a generic script.")
            con.print_info(f"Please configure DNS manually via NetworkManager settings (e.g., nm-connection-editor or nmtui),")
            con.print_info(f"or using nmcli for a connection (e.g., 'Wired connection 1'):")
            con.print_info(f"  sudo nmcli con mod \"Wired connection 1\" ipv4.dns \"{GOOGLE_DNS_IPV4[0]} {GOOGLE_DNS_IPV4[1]}\"")
            con.print_info(f"  sudo nmcli con mod \"Wired connection 1\" ipv6.dns \"{GOOGLE_DNS_IPV6[0]} {GOOGLE_DNS_IPV6[1]}\"") 
            con.print_info(f"  sudo nmcli con up \"Wired connection 1\"") 
            return True 
    except Exception: pass 

    con.print_warning(f"Could not confirm systemd-resolved or NetworkManager. Attempting to append to {RESOLV_CONF_PATH} (might be overwritten).")
    _backup_file(RESOLV_CONF_PATH) 
    
    lines_to_add_to_resolv = []
    current_resolv_text = ""
    if RESOLV_CONF_PATH.exists(): 
        current_resolv_text = RESOLV_CONF_PATH.read_text()

    for dns_ip in GOOGLE_DNS_IPV4 + GOOGLE_DNS_IPV6:
        entry = f"nameserver {dns_ip}"
        if entry not in current_resolv_text: 
            lines_to_add_to_resolv.append(entry)
    
    if lines_to_add_to_resolv:
        try:
            _append_to_file_sudo(RESOLV_CONF_PATH, "\n" + "\n".join(lines_to_add_to_resolv) + "\n")
            con.print_success(f"DNS entries added to {RESOLV_CONF_PATH}. System may overwrite this.")
        except Exception: 
            return False
    else:
        con.print_info(f"Google DNS entries already seem present in {RESOLV_CONF_PATH}.")
    return True

def _configure_dnf_performance() -> bool:
    con.print_sub_step("Configuring DNF for performance...")
    if not DNF_CONF_PATH.exists():
        con.print_warning(f"{DNF_CONF_PATH} does not exist. Cannot configure DNF performance.")
        return True 

    _backup_file(DNF_CONF_PATH) 
    
    settings_to_set = {
        "max_parallel_downloads": "10",
        "fastestmirror": "True"
    }
    
    parser = configparser.ConfigParser(comment_prefixes=('#'), allow_no_value=True)
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
            temp_config_path = Path(f"/tmp/dnf_conf_new_{os.getpid()}.conf")
            with open(temp_config_path, 'w', encoding='utf-8') as f_write:
                parser.write(f_write, space_around_delimiters=False) 
            
            system_utils.run_command(["sudo", "cp", str(temp_config_path), str(DNF_CONF_PATH)], print_fn_info=con.print_info, print_fn_error=con.print_error)
            system_utils.run_command(["sudo", "chown", "root:root", str(DNF_CONF_PATH)], print_fn_info=con.print_info, print_fn_error=con.print_error)
            system_utils.run_command(["sudo", "chmod", "644", str(DNF_CONF_PATH)], print_fn_info=con.print_info, print_fn_error=con.print_error)
            
            temp_config_path.unlink() 
            con.print_success("DNF performance settings updated.")
        else:
            con.print_info("DNF performance settings already up-to-date.")
        return True
    except Exception as e:
        con.print_error(f"Failed to configure DNF performance: {e}")
        temp_file_check = Path(f"/tmp/dnf_conf_new_{os.getpid()}.conf")
        if temp_file_check.exists(): temp_file_check.unlink()
        return False

def _setup_rpm_fusion() -> bool:
    con.print_sub_step("Setting up RPM Fusion repositories...")
    try:
        rpm_check_cmd = ["rpm", "-q", "rpmfusion-free-release", "rpmfusion-nonfree-release"]
        process = system_utils.run_command(
            rpm_check_cmd, capture_output=True, check=False, print_fn_info=con.print_info
        )
        if process.returncode == 0: 
            con.print_info("RPM Fusion repositories seem to be already installed.")
            return True
    except FileNotFoundError: 
        con.print_warning("'rpm' command not found. Cannot check for existing RPM Fusion. Proceeding with install attempt.")

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

        cmd_install_rpmfusion = ["sudo", "dnf", "install", "-y", rpm_fusion_free_url, rpm_fusion_nonfree_url]
        system_utils.run_command(
            cmd_install_rpmfusion, capture_output=True,
            print_fn_info=con.print_info, print_fn_error=con.print_error, print_fn_sub_step=con.print_sub_step
        )
        con.print_success("RPM Fusion repositories enabled.")
        return True
    except Exception: 
        return False

def _update_system() -> bool:
    con.print_sub_step("Updating system (sudo dnf upgrade -y)...")
    try:
        system_utils.run_command(
            ["sudo", "dnf", "upgrade", "-y"], capture_output=False,
            print_fn_info=con.print_info, print_fn_error=con.print_error
        )
        con.print_success("System updated successfully.")
        return True
    except Exception: 
        return False

def _setup_flatpak() -> bool:
    """
    Sets up the Flathub repository for Flatpak system-wide.
    This function assumes Flatpak is already installed.
    If Flatpak itself needs to be installed, it should be part of
    'phase1_system_preparation.dnf_packages' in 'packages.yaml'.
    """
    con.print_sub_step("Setting up Flathub repository for Flatpak...")
    try:
        # Check if Flathub remote already exists (system-wide)
        # This command lists system remotes. `flatpak remotes` alone lists user then system.
        check_cmd = ["flatpak", "remotes", "--system"]
        # check=False because it's okay if 'flatpak remotes' fails (e.g., no remotes yet or flatpak not init'd)
        # We rely on `stdout` content to confirm existence.
        remotes_process = system_utils.run_command(
            check_cmd, capture_output=True, check=False, print_fn_info=con.print_info
        )
        
        # A more robust check: iterate through lines of output
        flathub_found = False
        if remotes_process.returncode == 0 and remotes_process.stdout:
            for line in remotes_process.stdout.strip().splitlines():
                # Example line: flathub system,oci https://dl.flathub.org/repo/
                # We just care if 'flathub' is listed as a remote name.
                if line.strip().startswith("flathub"):
                    flathub_found = True
                    break
        
        if flathub_found:
            con.print_info("Flathub remote 'flathub' already exists (system-wide).")
            return True
        
        # If not found system-wide, attempt to add it
        # The command provided by the user is correct and robust.
        con.print_info("Flathub remote not found or not configured. Attempting to add system-wide...")
        cmd_add_flathub = [
            "sudo", "flatpak", "remote-add", "--if-not-exists", 
            "flathub", "https://dl.flathub.org/repo/flathub.flatpakrepo"
        ]
        system_utils.run_command(
            cmd_add_flathub, 
            capture_output=True, # Output of this command is usually minimal on success
            check=True, # Ensure it succeeds
            print_fn_info=con.print_info, 
            print_fn_error=con.print_error, 
            print_fn_sub_step=con.print_sub_step
        )
        con.print_success("Flathub repository added for Flatpak (system-wide).")
        return True
    except FileNotFoundError: # flatpak command itself not found
        con.print_warning("'flatpak' command not found. Is Flatpak installed?")
        con.print_info("Consider adding 'flatpak' to 'phase1_system_preparation.dnf_packages' in your packages.yaml if it's not pre-installed on your system.")
        return False # Cannot proceed if flatpak isn't there
    except subprocess.CalledProcessError as e: # Error already logged by run_command
        con.print_error(f"Failed to setup Flathub repository. Error: {e}")
        if e.stdout: con.print_error(f"STDOUT: {e.stdout.strip()}")
        if e.stderr: con.print_error(f"STDERR: {e.stderr.strip()}")
        return False
    except Exception as e: # Other unexpected errors
        con.print_error(f"An unexpected error occurred during Flathub setup: {e}")
        return False

def _set_hostname() -> bool:
    con.print_sub_step("Setting system hostname...")
    try:
        current_hostname_proc = system_utils.run_command(
            ["hostnamectl", "status", "--static"], capture_output=True, check=False, 
            print_fn_info=con.print_info
        )
        if current_hostname_proc.returncode != 0: 
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
    except Exception: 
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
        con.print_info("Step 2: Configuring DNF performance...")
        if not _configure_dnf_performance():
            con.print_warning("DNF performance configuration encountered issues. Continuing...")

        con.print_info("Step 3: Setting up RPM Fusion repositories...")
        if not _setup_rpm_fusion():
            con.print_error("RPM Fusion setup failed. This may impact package availability.")
            critical_success = False 

    if critical_success: 
        con.print_info("Step 4: Configuring DNS...")
        if not _configure_dns():
            con.print_error("DNS configuration encountered issues. Network operations might fail or be slow.")
            critical_success = False 

    if critical_success: 
        con.print_info("Step 5: Cleaning DNF metadata and updating system...")
        try:
            system_utils.run_command(
                ["sudo", "dnf", "clean", "all"], capture_output=True,
                print_fn_info=con.print_info, print_fn_error=con.print_error
            )
        except Exception as e:
            con.print_warning(f"DNF clean all failed: {e}. Proceeding with upgrade attempt.")

        if not _update_system():
            con.print_error("CRITICAL: System update failed. Subsequent phases may be unstable.")
            critical_success = False
    
    con.print_info("Step 6: Setting up Flathub repository for Flatpak...")
    # This step assumes 'flatpak' command is available.
    # If flatpak needs to be installed by this script, add 'flatpak' to 
    # phase1_system_preparation.dnf_packages in packages.yaml.
    if not _setup_flatpak():
        # Not marking critical_success = False, as Flatpak setup might be optional for some users,
        # but it's a significant warning.
        con.print_warning("Flatpak (Flathub) setup encountered issues. This may affect Flatpak app installations in later phases.")

    con.print_info("Step 7: Setting system hostname...")
    if not _set_hostname():
        con.print_warning("Setting hostname encountered issues. Non-critical for phase success.")

    if critical_success:
        con.print_success("Phase 1: System Preparation completed successfully.")
    else:
        con.print_error("Phase 1: System Preparation completed with CRITICAL errors. Please review the output.")
    
    return critical_success