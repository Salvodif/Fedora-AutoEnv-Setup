# basic_configuration.py
import logging
import os
import shutil
import re # For regex operations on config files
from pathlib import Path

from scripts.myrich import (
    console, print_info, print_warning, print_error, print_success,
    print_step, print_with_emoji, print_header
)
from scripts.utils import run_command

# Google Chrome repo details
CHROME_REPO_URL = "https://dl.google.com/linux/chrome/rpm/stable/x86_64"
CHROME_REPO_NAME = "google-chrome"
GOOGLE_CHROME_REPO_FILE_PATH = Path("/etc/yum.repos.d/") / f"{CHROME_REPO_NAME}.repo"

# Google DNS Servers
GOOGLE_DNS_IPV4 = ["8.8.8.8", "8.8.4.4"]
GOOGLE_DNS_IPV6 = ["2001:4860:4860::8888", "2001:4860:4860::8844"]


def _check_root_privileges():
    if os.geteuid() != 0:
        print_error("This operation requires superuser (root) privileges.")
        logging.error("Attempted basic configuration without root privileges.")
        return False
    return True

def _add_google_chrome_repo_manual():
    print_info("Attempting to add Google Chrome repository by creating .repo file manually.")
    repo_content = f"""[{CHROME_REPO_NAME}]
name={CHROME_REPO_NAME}
baseurl={CHROME_REPO_URL}
enabled=1
gpgcheck=1
gpgkey=https://dl.google.com/linux/linux_signing_key.pub
"""
    try:
        if GOOGLE_CHROME_REPO_FILE_PATH.exists():
            existing_content = GOOGLE_CHROME_REPO_FILE_PATH.read_text()
            if CHROME_REPO_URL in existing_content and "enabled=1" in existing_content.replace(" ", ""):
                print_info(f"Google Chrome repository file '{GOOGLE_CHROME_REPO_FILE_PATH}' already exists and seems correctly configured.")
                return True
        print_info(f"Creating repository file: {GOOGLE_CHROME_REPO_FILE_PATH}")
        GOOGLE_CHROME_REPO_FILE_PATH.parent.mkdir(parents=True, exist_ok=True) 
        with open(GOOGLE_CHROME_REPO_FILE_PATH, "w") as f:
            f.write(repo_content)
        print_success(f"Google Chrome repository file '{GOOGLE_CHROME_REPO_FILE_PATH}' created/updated successfully.")
        dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
        print_info(f"Running '{dnf_cmd} makecache --repo={CHROME_REPO_NAME}' to refresh repository information.")
        run_command([dnf_cmd, "makecache", f"--repo={CHROME_REPO_NAME}"], check=False, capture_output=True) 
        return True
    except IOError as e:
        print_error(f"Failed to write Google Chrome repository file '{GOOGLE_CHROME_REPO_FILE_PATH}': {e}")
        logging.error(f"IOError writing {GOOGLE_CHROME_REPO_FILE_PATH}: {e}", exc_info=True)
        return False
    except Exception as e:
        print_error(f"An unexpected error occurred while creating Google Chrome repository file: {e}")
        logging.error(f"Unexpected error creating .repo file: {e}", exc_info=True)
        return False

def _add_google_chrome_repo(packages_to_install_this_run: list):
    print_info("Configuring Google Chrome repository...")
    dnf_cmd = "dnf5" if shutil.which("dnf5") else "dnf"
    if not shutil.which(dnf_cmd):
        print_error(f"`{dnf_cmd}` command not found. Cannot proceed with repository management.")
        logging.error(f"`{dnf_cmd}` command not found during Chrome repo setup.")
        return False
    use_manual_method = False
    config_manager_cmd_name = f"{dnf_cmd}-config-manager"
    config_manager_path = shutil.which(config_manager_cmd_name)

    if dnf_cmd == "dnf" and "dnf-plugins-core" in packages_to_install_this_run and config_manager_path:
        print_info(f"Attempting to add repo using '{config_manager_cmd_name} --add-repo'...")
        cmd_add_repo_config_manager = [config_manager_cmd_name, "--add-repo", CHROME_REPO_URL]
        stdout, stderr, returncode = run_command(cmd_add_repo_config_manager, capture_output=True, check=False)
        if returncode == 0:
            print_success("Google Chrome repository added successfully using config-manager.")
            return True
        else:
            print_warning(f"'{' '.join(cmd_add_repo_config_manager)}' failed (code: {returncode}). Stderr: {stderr.strip() if stderr else 'N/A'}")
            print_info("Falling back to manual .repo file creation method for Google Chrome.")
            use_manual_method = True
    else:
        if dnf_cmd == "dnf" and "dnf-plugins-core" in PACKAGES_TO_INSTALL and not config_manager_path:
            print_info(f"'{config_manager_cmd_name}' not found, even if dnf-plugins-core is in install list. Proceeding with manual method.")
        elif dnf_cmd == "dnf5":
             print_info(f"DNF5 detected. Using manual .repo file creation for Google Chrome as '{config_manager_cmd_name}' might behave differently or not be the preferred method for DNF5 repo addition initially.")
        else:
            print_info("Using manual .repo file creation method for Google Chrome.")
        use_manual_method = True
    if use_manual_method:
        return _add_google_chrome_repo_manual()
    return False

def _install_core_packages(config: dict):
    dnf_command = "dnf5" if shutil.which("dnf5") else "dnf"
    if not shutil.which(dnf_command):
        print_error(f"`{dnf_command}` command not found. Cannot install packages.")
        logging.error(f"`{dnf_command}` not found for package installation.")
        return False

    packages_to_install_this_run = list(config.get('dnf_packages', []))
    if not packages_to_install_this_run:
        print_info("No core DNF packages specified in configuration for basic_configuration.")
        return True

    all_good = True
    if "dnf-plugins-core" in packages_to_install_this_run and dnf_command == "dnf":
        config_manager_for_dnf_path = shutil.which("dnf-config-manager")
        if not config_manager_for_dnf_path:
            print_info("Ensuring 'dnf-plugins-core' is installed (for dnf config-manager)...")
            if not run_command([dnf_command, "install", "-y", "dnf-plugins-core"]):
                print_warning("Failed to install 'dnf-plugins-core'. Repository management for Chrome via config-manager might fail if it wasn't already present.")
                logging.warning("Failed to install/update dnf-plugins-core.")
            else:
                print_success("'dnf-plugins-core' installed/updated.")
        else:
            print_info("'dnf-config-manager' found, 'dnf-plugins-core' likely already installed or handled.")

    chrome_package_name = "google-chrome-stable" # As defined in YAML
    if chrome_package_name in packages_to_install_this_run:
        print_info("Processing Google Chrome installation:")
        if not _add_google_chrome_repo(packages_to_install_this_run):
            print_warning("Proceeding without Google Chrome due to repository setup failure.")
            logging.warning("Google Chrome repository setup failed. Chrome will not be installed.")
            try:
                packages_to_install_this_run.remove(chrome_package_name)
            except ValueError:
                pass 

    final_packages_list = [pkg for pkg in packages_to_install_this_run if pkg] 
    if not final_packages_list:
        print_info("No further core packages to install from the list at this stage.")
        return True

    print_info(f"Installing/updating core packages: {', '.join(final_packages_list)}")
    command = [dnf_command, "install", "-y"] + final_packages_list
    if run_command(command):
        print_success(f"Successfully processed core packages: {', '.join(final_packages_list)}")
    else:
        print_error(f"Failed to install/process some core packages: {', '.join(final_packages_list)}")
        logging.error(f"{dnf_command} installation command failed for: {', '.join(final_packages_list)}")
        all_good = False
    return all_good

def _install_media_codecs(config: dict): # Accept config
    dnf_command = "dnf5" if shutil.which("dnf5") else "dnf"
    if not shutil.which(dnf_command):
        print_error(f"`{dnf_command}` command not found. Cannot install media codecs.")
        return False

    all_codecs_installed_successfully = True
    print_info("Attempting to install multimedia packages and codecs.")
    print_info("This assumes RPM Fusion repositories (free and non-free) are enabled (usually done in Phase 1).")

    # Get configurations from YAML or use defaults/skip if not present
    multimedia_groups = config.get('dnf_groups_multimedia', [])
    ffmpeg_swap = config.get('dnf_swap_ffmpeg', {})
    multimedia_upgrade_opts_config = config.get('dnf_multimedia_upgrade_opts', {})
    sound_video_groups = config.get('dnf_groups_sound_video', [])

    if multimedia_groups:
        print_info(f"Installing 'multimedia' group(s): {', '.join(multimedia_groups)}")
        # Assuming multimedia_groups is a list like ["multimedia"]
        cmd1 = [dnf_command, "group", "install", "-y"] + multimedia_groups
        if run_command(cmd1):
            print_success(f"'multimedia' group(s) {', '.join(multimedia_groups)} processed successfully.")
        else:
            print_error(f"Failed to process 'multimedia' group(s) {', '.join(multimedia_groups)}.")
            all_codecs_installed_successfully = False
    else:
        print_info("No 'dnf_groups_multimedia' specified in config. Skipping.")

    if ffmpeg_swap and 'from' in ffmpeg_swap and 'to' in ffmpeg_swap:
        print_info(f"Swapping '{ffmpeg_swap['from']}' with full '{ffmpeg_swap['to']}'...")
        cmd2 = [dnf_command, "swap", ffmpeg_swap['from'], ffmpeg_swap['to'], "--allowerasing", "-y"]
        stdout_swap, stderr_swap, rc_swap = run_command(cmd2, capture_output=True, check=False)
        if rc_swap == 0:
            print_success(f"Successfully swapped '{ffmpeg_swap['from']}' for '{ffmpeg_swap['to']}' (or already swapped/not present).")
        else:
            if stderr_swap and (f"No match for argument: {ffmpeg_swap['from']}" in stderr_swap or "Nothing to do." in stderr_swap):
                print_info(f"Swap for {ffmpeg_swap['to']}: '{ffmpeg_swap['from']}' not found or no swap needed. This is likely okay.")
            elif stdout_swap and "Nothing to do." in stdout_swap:
                 print_info(f"Swap for {ffmpeg_swap['to']}: Nothing to do. This is likely okay.")
            else:
                print_warning(f"Command to swap '{ffmpeg_swap['from']}' with '{ffmpeg_swap['to']}' returned code {rc_swap}. This might be okay.")
    else:
        print_info("No 'dnf_swap_ffmpeg' specified correctly in config. Skipping ffmpeg swap.")

    if multimedia_upgrade_opts_config and 'group' in multimedia_upgrade_opts_config:
        group_to_upgrade = multimedia_upgrade_opts_config['group']
        setopt_val = multimedia_upgrade_opts_config.get('setopt', "")
        exclude_val = multimedia_upgrade_opts_config.get('exclude', "")
        
        print_info(f"Upgrading '{group_to_upgrade}' group...")
        cmd3_list = [dnf_command, "upgrade", "-y", group_to_upgrade]
        if setopt_val: cmd3_list.append(setopt_val)
        if exclude_val: cmd3_list.append(exclude_val)
        
        if run_command(cmd3_list):
            print_success(f"Successfully upgraded '{group_to_upgrade}' group with specified options.")
        else:
            print_error(f"Failed to upgrade '{group_to_upgrade}' group.")
            all_codecs_installed_successfully = False
    else:
        print_info("No 'dnf_multimedia_upgrade_opts' specified correctly in config. Skipping gstreamer component upgrade.")

    if sound_video_groups:
        print_info(f"Installing 'sound-and-video' group(s): {', '.join(sound_video_groups)}")
        # Assuming sound_video_groups is a list like ["sound-and-video"]
        cmd4 = [dnf_command, "group", "install", "-y"] + sound_video_groups
        if run_command(cmd4):
            print_success(f"'sound-and-video' group(s) {', '.join(sound_video_groups)} processed successfully.")
        else:
            print_error(f"Failed to process 'sound-and-video' group(s) {', '.join(sound_video_groups)}.")
            all_codecs_installed_successfully = False
    else:
        print_info("No 'dnf_groups_sound_video' specified in config. Skipping.")

    if all_codecs_installed_successfully:
        print_success("Media codecs and sound/video packages configuration completed successfully.")
    else:
        print_warning("Some media codec or sound/video package configurations encountered issues.")
    return all_codecs_installed_successfully

def _is_systemd_resolved_active():
    """Checks if systemd-resolved is likely managing /etc/resolv.conf."""
    resolv_conf_path = Path("/etc/resolv.conf")
    if resolv_conf_path.is_symlink():
        link_target = os.readlink(resolv_conf_path)
        # Common targets for systemd-resolved
        if "systemd/resolve/stub-resolv.conf" in link_target or \
           "systemd/resolve/resolv.conf" in link_target:
            print_info(f"/etc/resolv.conf is a symlink to '{link_target}', systemd-resolved is likely active.")
            return True
    # Check service status as a fallback or primary check
    _, _, retcode = run_command(["systemctl", "is-active", "systemd-resolved.service"], capture_output=True, check=False)
    if retcode == 0:
        print_info("systemd-resolved.service is active.")
        return True
    print_info("systemd-resolved does not appear to be the primary DNS resolver or is not active.")
    return False

def _update_resolved_conf():
    """Updates /etc/systemd/resolved.conf with Google DNS."""
    resolved_conf_path = Path("/etc/systemd/resolved.conf")
    dns_line = f"DNS={GOOGLE_DNS_IPV4[0]} {GOOGLE_DNS_IPV6[0]}"
    fallback_dns_line = f"FallbackDNS={GOOGLE_DNS_IPV4[1]} {GOOGLE_DNS_IPV6[1]}"
    # Domains_line can be added if specific search domains are needed, e.g., Domains=~.
    # For now, we are only setting DNS and FallbackDNS.

    try:
        if not resolved_conf_path.exists():
            print_warning(f"{resolved_conf_path} does not exist. Cannot configure systemd-resolved DNS.")
            # Create a minimal one? Or let the service handle its creation?
            # For now, assume it should exist if systemd-resolved is meant to be configured.
            # If it's missing, systemd-resolved might not be properly set up or used.
            return False

        print_info(f"Updating {resolved_conf_path}...")
        content = resolved_conf_path.read_text().splitlines()
        new_content = []
        dns_set = False
        fallback_dns_set = False
        in_resolve_section = False

        for line in content:
            stripped_line = line.strip()
            if stripped_line == "[Resolve]":
                in_resolve_section = True
                new_content.append(line)
            elif stripped_line.startswith("DNS="):
                new_content.append(dns_line)
                dns_set = True
            elif stripped_line.startswith("#DNS="): # Also replace commented out
                new_content.append(dns_line)
                dns_set = True
            elif stripped_line.startswith("FallbackDNS="):
                new_content.append(fallback_dns_line)
                fallback_dns_set = True
            elif stripped_line.startswith("#FallbackDNS="): # Also replace commented out
                new_content.append(fallback_dns_line)
                fallback_dns_set = True
            else:
                new_content.append(line)
        
        if not in_resolve_section: # If [Resolve] section is missing, add it with the settings
            print_info(f"'[Resolve]' section not found in {resolved_conf_path}. Adding it.")
            new_content.append("[Resolve]")
            if not dns_set: new_content.append(dns_line)
            if not fallback_dns_set: new_content.append(fallback_dns_line)
        else: # [Resolve] section exists, but maybe not the DNS lines
            if not dns_set:
                # Find [Resolve] and insert after it, or at the end of the section.
                # Simplest: add to the end of new_content if it was supposed to be in [Resolve]
                # This logic assumes simple structure; robust parsing would use a config library.
                try:
                    idx_resolve = new_content.index("[Resolve]")
                    new_content.insert(idx_resolve + 1, dns_line)
                except ValueError: # Should not happen if in_resolve_section was true
                     new_content.append(dns_line) # Fallback append
            if not fallback_dns_set:
                try:
                    idx_resolve = new_content.index("[Resolve]")
                    # Insert after DNS line if possible, or after [Resolve]
                    inserted_fallback = False
                    for i, l_new in enumerate(new_content):
                        if l_new.strip().startswith("DNS="):
                            new_content.insert(i + 1, fallback_dns_line)
                            inserted_fallback = True
                            break
                    if not inserted_fallback:
                         new_content.insert(idx_resolve + 1, fallback_dns_line) # Fallback if DNS= not found
                except ValueError:
                    new_content.append(fallback_dns_line)

        resolved_conf_path.write_text("\n".join(new_content) + "\n")
        print_success(f"{resolved_conf_path} updated with Google DNS.")
        return True

    except Exception as e:
        print_error(f"Failed to update {resolved_conf_path}: {e}")
        logging.error(f"Error updating {resolved_conf_path}: {e}", exc_info=True)
        return False

def _configure_google_dns():
    """Configures Google DNS servers, prioritizing systemd-resolved."""
    # This will be Step 2.3 in run_basic_configuration
    print_info("Attempting to configure Google DNS servers...")

    if not _is_systemd_resolved_active():
        print_warning("systemd-resolved is not active or not managing /etc/resolv.conf.")
        print_warning("Automatic DNS configuration for systemd-resolved will be skipped.")
        # Optionally, here you could try to configure NetworkManager directly,
        # but it's more complex to do robustly for all connections.
        # For now, we'll just warn if systemd-resolved isn't the clear manager.
        print_info("If you use NetworkManager directly, you might need to configure DNS per-connection or in /etc/NetworkManager/NetworkManager.conf.")
        return True # Not a failure of this step if the target service isn't primary

    if _update_resolved_conf():
        print_info("Restarting systemd-resolved.service to apply DNS changes...")
        if run_command(["sudo", "systemctl", "restart", "systemd-resolved.service"]):
            print_success("systemd-resolved.service restarted. Google DNS should be active.")
            # Verification step (optional)
            # run_command(["resolvectl", "query", "google.com"], check=False)
            return True
        else:
            print_error("Failed to restart systemd-resolved.service. DNS changes may not be active.")
            logging.error("Failed to restart systemd-resolved.service after DNS config.")
            return False
    else:
        # _update_resolved_conf already printed an error
        return False

def _set_zsh_as_default_shell(packages_installed: list): # Accept list of packages that were intended/attempted
    zsh_path = shutil.which("zsh")
    if not zsh_path:
        if "zsh" in packages_installed:
            print_error("Zsh is not installed or not found in PATH. Cannot set as default shell.")
            logging.error("Zsh not found via shutil.which('zsh').")
        else:
            print_info("Zsh is not installed (or not in PATH) and was not in the list of packages for this phase. Skipping setting it as default.")
        logging.error("Zsh not found via shutil.which('zsh').")
        return False # Or True if skipping is considered non-failure

    try:
        username = os.environ.get('SUDO_USER')
        if not username: 
            username = os.getlogin()
            print_warning(f"SUDO_USER not set, falling back to os.getlogin(): {username} for chsh.")
            logging.warning(f"SUDO_USER not set, chsh target user: {username}")
        if not username:
             print_error("Could not determine the target username for chsh.")
             logging.error("Username for chsh could not be determined.")
             return False
    except OSError:
        print_error("Could not determine the current user to change shell (OSError on os.getlogin()).")
        logging.error("os.getlogin() failed and SUDO_USER not set for chsh.")
        return False
    print_info(f"Attempting to set {zsh_path} as default shell for user '{username}'.")
    try:
        current_shell_cmd = ["getent", "passwd", username]
        stdout, _, retcode = run_command(current_shell_cmd, capture_output=True, check=False)
        if retcode == 0 and stdout:
            current_shell = stdout.strip().split(':')[-1]
            if current_shell == zsh_path:
                print_info(f"Zsh ('{zsh_path}') is already the default shell for user '{username}'.")
                return True
    except Exception as e:
        print_warning(f"Could not determine current shell for user '{username}': {e}")
    command = ["chsh", "-s", zsh_path, username]
    if run_command(command):
        print_success(f"Zsh set as default shell for user '{username}'.")
        return True
    else:
        print_error(f"Failed to set Zsh as default shell for user '{username}'.")
        logging.error(f"chsh command failed for user {username} with shell {zsh_path}.")
        return False

def run_basic_configuration(config: dict): # Accept config
    print_header("Phase 2: Basic System Package Configuration")
    if not _check_root_privileges():
        return False 
    overall_success = True 

    core_packages_config = config.get('dnf_packages', []) # Used for Zsh check later

    print_step(2.1, "Installing core packages & Google Chrome repository")
    if not _install_core_packages():
        print_error("Core package installation phase encountered errors.")
        overall_success = False 
    
    print_step(2.2, "Installing Media Codecs and Sound/Video packages")
    if not _install_media_codecs():
        print_warning("Media codec installation phase encountered errors. Some codecs or players might not function correctly.")
        overall_success = False
    
    print_step(2.3, "Configuring Google DNS")
    if not _configure_google_dns():
        print_warning("Google DNS configuration encountered issues or was skipped.")
        # Not necessarily a critical failure for the whole phase, but good to note.
        # Let's consider it non-critical for overall_success unless a direct error occurred during an attempt.
        # The function itself returns False on direct error, so overall_success will be affected.
    
    zsh_in_list = "zsh" in core_packages_config
    if zsh_in_list:
        print_step(2.4, "Setting Zsh as default shell")
        if not _set_zsh_as_default_shell(core_packages_config): # Pass the list of packages
            print_warning("Failed to set Zsh as default shell. Please do it manually if desired.")
    else:
        print_info("Zsh is not in the list of configured packages for this phase. Skipping setting it as default shell.")

    if overall_success:
        console.print("\n[bold green]Phase 2 (Basic Package Configuration) completed successfully.[/bold green]")
        # Common message for logout/reboot
        print_with_emoji("❗", "[bold yellow on_black] IMPORTANT: Some changes (like DNS, new shell, codecs) may require [/bold yellow on_black]")
        print_with_emoji("❗", "[bold yellow on_black] you to log out and log back in, or restart network services, or reboot [/bold yellow on_black]")
        print_with_emoji("❗", "[bold yellow on_black] for them to take full effect. [/bold yellow on_black]")
    else:
        console.print("\n[bold yellow]Phase 2 (Basic Package Configuration) completed with some errors.[/bold yellow]")
        print_warning("Please check the log file 'app.log' and output above for details.")
        print_info("Some configurations might require manual intervention.")
    return overall_success
