# Fedora-AutoEnv-Setup/scripts/phase3_terminal_enhancement.py

import sys
from pathlib import Path

# Adjust import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import console_output as con
from scripts import system_utils
from scripts.logger_utils import app_logger

def run_phase3(app_config: dict) -> bool:
    con.print_step("PHASE 3: Terminal Enhancement")
    app_logger.info("Starting Phase 3: Terminal Enhancement.")
    overall_success = True

    # --- Step 0: Determine Target User ---
    target_user = system_utils.get_target_user(
        logger=app_logger, print_fn_info=con.print_info,
        print_fn_error=con.print_error, print_fn_warning=con.print_warning
    )
    if not target_user:
        app_logger.error("Cannot determine target user for Phase 3. Aborting phase.")
        return False

    target_user_home = system_utils.get_user_home_dir(target_user, logger=app_logger, print_fn_error=con.print_error)
    if not target_user_home:
        app_logger.error(f"Target user home for '{target_user}' not found. Aborting user-specific part of Phase 3.")
        return False

    phase3_config = config_loader.get_phase_data(app_config, "phase3_terminal_enhancement")
    if not phase3_config:
        con.print_warning("No configuration found for Phase 3. Skipping.")
        app_logger.warning("No Phase 3 configuration found or configuration is invalid. Skipping.")
        return True

    # --- Step 1: Install DNF packages ---
    con.print_sub_step("Installing DNF packages for terminal enhancement...")
    dnf_packages = phase3_config.get("dnf_packages", [])
    if dnf_packages:
        # Enable copr repo for ghostty
        copr_enable_cmd = "dnf copr enable -y scottames/ghostty"
        try:
            system_utils.run_command(
                copr_enable_cmd,
                shell=True,
                check=True,
                logger=app_logger,
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
            )
        except Exception as e:
            con.print_error(f"Failed to enable ghostty copr repository: {e}")
            overall_success = False

        if overall_success:
            if not system_utils.install_dnf_packages(
                dnf_packages,
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step,
                logger=app_logger
            ):
                overall_success = False

    # --- Step 2: Configure Ghostty ---
    if overall_success:
        con.print_sub_step("Configuring Ghostty...")
        try:
            config_dir = target_user_home / ".config" / "ghostty"
            system_utils.ensure_dir_exists(
                config_dir,
                target_user=target_user,
                logger=app_logger,
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
            )
            config_file = config_dir / "config"
            source_config_file = Path(__file__).resolve().parent.parent / "assets" / "ghostty.conf"

            with open(source_config_file, "r") as f:
                config_content = f.read()

            system_utils.create_file_as_user(
                config_file,
                config_content,
                target_user,
                logger=app_logger,
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
            )
            con.print_success("Ghostty configured successfully.")
        except Exception as e:
            con.print_error(f"Failed to configure Ghostty: {e}")
            overall_success = False

    # --- Step 3: Install Fisher and plugins ---
    if overall_success:
        con.print_sub_step("Installing fisher and plugins...")
        try:
            fisher_install_cmd = "fish -c 'curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source && fisher install jorgebucaran/fisher'"
            system_utils.run_command(
                fisher_install_cmd,
                run_as_user=target_user,
                shell=True,
                check=True,
                logger=app_logger,
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
            )
            zoxide_plugin_install_cmd = "fish -c 'fisher install kidonng/zoxide.fish'"
            system_utils.run_command(
                zoxide_plugin_install_cmd,
                run_as_user=target_user,
                shell=True,
                check=True,
                logger=app_logger,
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
            )
            con.print_success("Fisher and zoxide plugin installed successfully.")
        except Exception as e:
            con.print_error(f"Failed to install fisher or zoxide plugin: {e}")
            overall_success = False

    # --- Phase Completion Summary ---
    if overall_success:
        con.print_success("Phase 3: Terminal Enhancement completed successfully.")
        app_logger.info("Phase 3 completed successfully.")
    else:
        con.print_error("Phase 3: Terminal Enhancement completed with errors.")
        app_logger.error("Phase 3 completed with errors.")

    return overall_success
