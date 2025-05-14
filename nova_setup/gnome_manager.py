import shutil
import subprocess # For CalledProcessError, TimeoutExpired

from . import shared_state
from . import utils as command_utils

from .package_manager import install_dnf_packages # Specific import

def _apply_dark_style_settings(gtk_theme_name="Adwaita-dark", icons_name="Adwaita", cursor_name="Adwaita"):
    """
    Applies dark style settings for GNOME, primarily by setting color-scheme.
    Also explicitly sets GTK, icon, and cursor themes for robustness.
    """
    Console, Panel, Text, Confirm, _, _, _, _, _ = shared_state.get_rich_components()

    if not shutil.which("gsettings"):
        shared_state.log.error("`gsettings` command not found. Cannot set GNOME appearance settings.")
        shared_state.log.info("This tool is usually part of the core GNOME desktop environment.")
        return

    shared_state.log.info(
        f"Attempting to apply 'Dark' style for user {shared_state.TARGET_USER}. "
        f"(GTK: {gtk_theme_name}, Icons: {icons_name}, Cursor: {cursor_name})"
    )

    settings_to_apply = {
        "color-scheme": "'prefer-dark'", # Primary setting for "Style: Dark"
        "gtk-theme": gtk_theme_name,
        "icon-theme": icons_name,
        "cursor-theme": cursor_name,
    }

    all_settings_succeeded = True
    for key, value in settings_to_apply.items():
        actual_value_for_cmd = value
        gsettings_cmd = ["gsettings", "set", "org.gnome.desktop.interface", key, actual_value_for_cmd]
        
        log_key_display = key
        if key == "color-scheme":
            log_key_display = "color-scheme (Style: Dark)"

        try:
            shared_state.log.info(f"Setting org.gnome.desktop.interface {log_key_display} to {value}...")
            command_utils.run_command(gsettings_cmd, as_user=shared_state.TARGET_USER, check=True)
            shared_state.log.debug(f"Successfully set {log_key_display} to {value}.")
        except subprocess.CalledProcessError as e:
            shared_state.log.error(f"Failed to set org.gnome.desktop.interface {log_key_display} to {value}.")
            shared_state.log.debug(f"Command: {' '.join(e.cmd)}")
            if e.stderr: shared_state.log.debug(f"[stderr]: {e.stderr.strip()}")
            if e.stdout: shared_state.log.debug(f"[stdout]: {e.stdout.strip()}")
            all_settings_succeeded = False
        except Exception as e_unexp:
            shared_state.log.error(f"[bold red]Unexpected error setting {log_key_display}: {e_unexp}[/]")
            all_settings_succeeded = False
            if shared_state.console: shared_state.console.print_exception(max_frames=3)
    
    if all_settings_succeeded:
        shared_state.log.info(
            f":art: GNOME 'Dark' style preference applied. "
            f"GTK theme explicitly set to: {gtk_theme_name}."
        )
        shared_state.log.info("Changes should take effect for new applications, or after a session restart for full effect.")
    else:
        shared_state.log.warning("Some GNOME appearance settings could not be applied. Check logs.")


def manage_gnome_extensions_and_appearance(): # Renamed for clarity
    Console, Panel, Text, Confirm, _, _, _, _, _ = shared_state.get_rich_components()

    shared_state.console.rule("[bold magenta]GNOME Shell Extension & Appearance Management[/]", style="magenta")
    
    # Check for essential GNOME tools first
    if not shutil.which("gnome-extensions"):
        shared_state.log.error("`gnome-extensions` CLI tool not found. Cannot manage extensions.")
        shared_state.log.info("This tool is usually part of the `gnome-shell` package or your GNOME desktop installation.")
        shared_state.log.info("Please ensure you are running a GNOME desktop environment and `gnome-shell` is installed if you wish to manage extensions.")
        # Decide if you want to proceed to theme settings or return
        if not Confirm.ask("`gnome-extensions` tool not found. Still attempt to manage GNOME appearance settings (e.g., dark style)?", default=True, console=shared_state.console):
            return # User chose not to proceed without extension management
        # If user says yes, we can skip extension parts and go to appearance
        manage_extensions = False
    else:
        manage_extensions = True

    if not shutil.which("gsettings"):
        shared_state.log.error("`gsettings` command not found. Cannot manage GNOME appearance settings.")
        shared_state.log.info("This tool is usually part of the core GNOME desktop environment.")
        if not manage_extensions: # If both tools are missing, probably best to exit
            shared_state.log.warning("Neither `gnome-extensions` nor `gsettings` found. Aborting GNOME management.")
            return
        # If only gsettings is missing, but gnome-extensions was found, we could ask to proceed with extensions only
        # For simplicity now, if gsettings is missing, we might log an error and theme part will fail later.
        # The _apply_dark_style_settings function already checks for gsettings.

    if manage_extensions:
        # --- DNF Package Installation for Extensions ---
        core_mgmt_packages = set()
        if hasattr(shared_state, 'GNOME_MANAGEMENT_DNF_PACKAGES') and shared_state.GNOME_MANAGEMENT_DNF_PACKAGES:
            core_mgmt_packages.update(shared_state.GNOME_MANAGEMENT_DNF_PACKAGES)
            shared_state.log.info("Installing/Verifying core GNOME management tools and base extension DNF packages...")
            install_dnf_packages(list(core_mgmt_packages))
        else:
            shared_state.log.debug("`shared_state.GNOME_MANAGEMENT_DNF_PACKAGES` is not defined or empty. Skipping core DNF tools installation for GNOME.")

        ext_specific_dnf_packages = set()
        if hasattr(shared_state, 'GNOME_EXTENSIONS_CONFIG'):
            for ext_cfg in shared_state.GNOME_EXTENSIONS_CONFIG:
                if "dnf_package" in ext_cfg:
                    ext_specific_dnf_packages.add(ext_cfg["dnf_package"])
        else:
            shared_state.log.warning("`shared_state.GNOME_EXTENSIONS_CONFIG` not found. Cannot process DNF packages for specific extensions.")
            shared_state.GNOME_EXTENSIONS_CONFIG = []

        dnf_pkgs_to_install_for_exts = list(ext_specific_dnf_packages - core_mgmt_packages)
        if dnf_pkgs_to_install_for_exts:
            shared_state.log.info("Installing/Verifying additional DNF packages required for specific GNOME extensions...")
            install_dnf_packages(dnf_pkgs_to_install_for_exts)
        
        # --- GNOME Extension Management ---
        shared_state.log.info("Attempting to enable configured GNOME Shell extensions...")
        enabled_new_extensions = False
        for ext_cfg in shared_state.GNOME_EXTENSIONS_CONFIG:
            name = ext_cfg.get("name", "Unknown Extension")
            uuid = ext_cfg.get("uuid")
            dnf_pkg = ext_cfg.get("dnf_package")

            if not uuid:
                shared_state.log.warning(f"Skipping extension '{name}' due to missing UUID in its configuration.")
                continue

            shared_state.log.info(f"Processing extension: [cyan]{name}[/] (UUID: {uuid})")
            try:
                info_res = command_utils.run_command(
                    ["gnome-extensions", "info", uuid],
                    as_user=shared_state.TARGET_USER, capture_output=True, text=True, check=False
                )
                current_state = next(
                    (line.split(":", 1)[1].strip() for line in info_res.stdout.splitlines() if line.startswith("State:")),
                    "NOT FOUND" if info_res.returncode != 0 else "UNKNOWN (Could not parse state)"
                )
                shared_state.log.debug(f"Extension '{name}' current state: {current_state}")

                if current_state == "ENABLED":
                    shared_state.log.info(f":heavy_check_mark: Extension '[cyan]{name}[/]' is already enabled.")
                elif current_state in ["DISABLED", "INITIALIZED", "ERROR", "DOWNLOAD_NEEDED", "OUTDATED"]:
                    shared_state.log.info(f"Attempting to enable extension '[cyan]{name}[/]' (current state: {current_state})...")
                    with shared_state.console.status(f"[green]Enabling {name}...[/]", spinner="dots"):
                        command_utils.run_command(
                            ["gnome-extensions", "enable", uuid], as_user=shared_state.TARGET_USER, check=True
                        )
                    shared_state.log.info(f":arrow_up_small: Extension '[cyan]{name}[/]' successfully enabled.")
                    enabled_new_extensions = True
                elif current_state == "NOT FOUND":
                    shared_state.log.warning(
                        f"[yellow]Extension '{name}' (UUID: {uuid}) not found by `gnome-extensions info`."
                        f" Its DNF package '{dnf_pkg or 'N/A'}' might be missing, incompatible, or failed to install correctly."
                    )
                else:
                    shared_state.log.warning(f"Extension '{name}' is in an unexpected state: '{current_state}'. Manual check may be needed.")
            except subprocess.CalledProcessError as e:
                shared_state.log.warning(
                    f"Failed to manage extension '{name}'. Command: `{' '.join(e.cmd)}`."
                    f" Associated DNF package: {dnf_pkg or 'N/A'}."
                )
                if e.stderr: shared_state.log.debug(f"stderr for '{name}': {e.stderr.strip()}")
                if e.stdout: shared_state.log.debug(f"stdout for '{name}': {e.stdout.strip()}")
            except Exception as e_unexp:
                shared_state.log.error(f"[bold red]An unexpected error occurred while managing extension '{name}': {e_unexp}[/]")
                if shared_state.console: shared_state.console.print_exception(max_frames=3)

        if enabled_new_extensions:
            shared_state.log.info("[yellow]One or more GNOME Shell extensions were newly enabled. A GNOME Shell restart (Alt+F2, 'r', Enter) or a logout/login might be needed for full effect.[/]")
        else:
            shared_state.log.info("No new GNOME extensions were enabled (already active, not found, or failed to enable).")

        try:
            shared_state.log.info(f"Listing currently enabled GNOME extensions for user {shared_state.TARGET_USER}:")
            enabled_list_res = command_utils.run_command(
                ["gnome-extensions", "list", "--enabled"],
                as_user=shared_state.TARGET_USER, capture_output=True, check=True, text=True
            )
            if enabled_list_res.stdout and enabled_list_res.stdout.strip():
                shared_state.console.print(f"[italic]Enabled extensions for {shared_state.TARGET_USER}:[/]")
                shared_state.console.print(enabled_list_res.stdout.strip())
            else:
                shared_state.log.info("No enabled extensions found, or the GNOME session might be inactive for this command.")
        except Exception as e_list_enabled:
            shared_state.log.warning(f"Could not list enabled GNOME extensions: {e_list_enabled}")
    
    # --- GNOME Appearance Settings (Dark Style) ---
    # This part will run if gsettings is present, even if gnome-extensions was not.
    # The _apply_dark_style_settings function checks for gsettings internally.
    shared_state.console.rule("[bold cyan]GNOME Appearance Configuration[/]", style="cyan")
    prompt_message = (
        f"Do you want to switch to the 'Dark' style for user {shared_state.TARGET_USER}? "
        "(This activates dark mode for applications and the desktop shell, matching the 'Style: Dark' option in GNOME Settings)"
    )
    if Confirm.ask(prompt_message, default=True, console=shared_state.console):
        _apply_dark_style_settings(
            gtk_theme_name="Adwaita-dark",
            icons_name="Adwaita",
            cursor_name="Adwaita"
        )
    else:
        shared_state.log.info("Skipping GNOME 'Dark' style configuration.")

    shared_state.console.print(Panel(Text("GNOME Extension & Appearance Management Completed.", style="bold green"), expand=False))

    # --- Post-Install Checks ---
    try:
        from .post_install_checks import perform_post_install_checks
        shared_state.log.info("Performing post-check for GNOME tools after management attempt...")
        perform_post_install_checks(check_gnome_specific_tools=True)
    except ImportError:
        shared_state.log.debug("`post_install_checks` module not found, skipping GNOME post-checks from here.")
    except AttributeError:
        shared_state.log.debug("`perform_post_install_checks` function not found in `post_install_checks` module.")