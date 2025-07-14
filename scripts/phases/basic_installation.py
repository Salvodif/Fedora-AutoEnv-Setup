# Fedora-AutoEnv-Setup/scripts/phases/basic_installation.py

from scripts import console_output as con
from scripts import system_utils as util
from scripts.config import app_logger

def run(app_config):
    """
    Phase 2: Basic Installation.
    This phase is responsible for installing essential packages for the system.
    """
    con.print_step("Phase 2: Basic Installation")

    try:
        # Retrieve the list of packages to install from the configuration
        phase_config = app_config.get('phase2_basic_configuration', {})

        # Install dnf packages
        dnf_packages = phase_config.get('dnf_packages', [])
        if dnf_packages:
            con.print_sub_step("Installing base DNF packages...")
            if not util.install_dnf_packages(
                packages=dnf_packages,
                logger=app_logger,
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step
            ):
                con.print_error("Failed to install some base DNF packages.")
                return False

        # Swap ffmpeg-free with ffmpeg
        ffmpeg_swap = phase_config.get('dnf_swap_ffmpeg', {})
        if ffmpeg_swap:
            con.print_sub_step("Swapping ffmpeg-free for ffmpeg...")
            if not util.swap_dnf_packages(
                from_pkg=ffmpeg_swap.get('from'),
                to_pkg=ffmpeg_swap.get('to'),
                logger=app_logger,
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step
            ):
                con.print_error("Failed to swap ffmpeg packages.")
                # This may not be a fatal error, so we can continue

        # Install sound and video group
        sound_video_group = phase_config.get('dnf_groups_sound_video', [])
        if sound_video_group:
            con.print_sub_step("Installing sound and video DNF group...")
            if not util.install_dnf_groups(
                groups=sound_video_group,
                logger=app_logger,
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step
            ):
                con.print_error("Failed to install sound and video DNF group.")
                return False

        # Install flatpak apps
        flatpak_apps = phase_config.get('flatpak_apps', {})
        if flatpak_apps:
            con.print_sub_step("Installing Flatpak applications...")
            if not util.install_flatpak_apps(
                apps_to_install=flatpak_apps,
                logger=app_logger,
                print_fn_info=con.print_info,
                print_fn_error=con.print_error,
                print_fn_sub_step=con.print_sub_step
            ):
                con.print_error("Failed to install some Flatpak applications.")
                # This may not be a fatal error, so we can continue

        # Install nerd fonts
        nerd_fonts = phase_config.get('nerd_fonts_to_install', {})
        if nerd_fonts:
            con.print_sub_step("Installing Nerd Fonts...")
            # This is a placeholder for the actual implementation
            # You would need to implement a function to download and install fonts
            con.print_warning("Nerd Fonts installation is not yet implemented.")

        # Copy ghostty config
        con.print_sub_step("Copying ghostty configuration file...")
        try:
            user = util.get_target_user()
            if user:
                home_dir = util.get_user_home_dir(user)
                if home_dir:
                    config_dir = home_dir / ".config" / "ghostty"
                    util.ensure_dir_exists(config_dir, target_user=user, logger=app_logger)

                    source_path = "assets/ghostty.conf"
                    target_path = config_dir / "config"

                    util.run_command(
                        ["cp", source_path, str(target_path)],
                        logger=app_logger,
                        print_fn_info=con.print_info,
                        print_fn_error=con.print_error
                    )

                    util.run_command(
                        ["chown", f"{user}:{user}", str(target_path)],
                        logger=app_logger,
                        print_fn_info=con.print_info,
                        print_fn_error=con.print_error
                    )

                    con.print_success("Successfully copied ghostty configuration file.")
        except Exception as e:
            con.print_error(f"Failed to copy ghostty configuration file: {e}")

        con.print_success("Phase 2: Basic Installation completed successfully.")

    except Exception as e:
        con.print_error(f"An unexpected error occurred during Phase 2: {e}")
        app_logger.error(f"Phase 2 failed with error: {e}", exc_info=True)
        return False

    return True
