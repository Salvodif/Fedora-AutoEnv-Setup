import os
import sys
import pwd
import logging as std_logging 
from pathlib import Path

from . import shared_state
from .system_config import perform_system_update_check, check_critical_deps
from .package_manager import install_dnf_packages
from .shell_customization import install_oh_my_zsh, install_omz_plugins, set_default_shell_to_zsh # Import aggiunto
from .tool_installers import install_cargo_tools, install_scripted_tools
from .config_files import copy_config_files
from .gnome_manager import manage_gnome_extensions
from .post_install_checks import perform_post_install_checks
from . import utils as command_utils # Importa command_utils per check_command_exists


def initialize_script_logging_and_user():
    if os.geteuid() != 0:
        if shared_state.log: shared_state.log.critical("[bold red]Must be run as root (sudo).[/]")
        else: print("CRITICAL: Must be run as root (sudo).", file=sys.stderr, flush=True)
        sys.exit(1)

    shared_state.TARGET_USER = os.getenv("SUDO_USER")
    if not shared_state.TARGET_USER:
        if shared_state.log: shared_state.log.warning("No SUDO_USER. Targeting root user.")
        else: print("WARNING: No SUDO_USER. Targeting root.", flush=True)
        shared_state.TARGET_USER = pwd.getpwuid(os.geteuid()).pw_name
    
    try:
        pw_entry = pwd.getpwnam(shared_state.TARGET_USER)
        shared_state.TARGET_USER_HOME = Path(pw_entry.pw_dir)
    except KeyError:
        if shared_state.log: shared_state.log.critical(f"[bold red]User '{shared_state.TARGET_USER}' not found.[/]")
        else: print(f"CRITICAL: User '{shared_state.TARGET_USER}' not found.", file=sys.stderr, flush=True)
        sys.exit(1)
    
    if not shared_state.TARGET_USER_HOME.is_dir():
        if shared_state.log: shared_state.log.critical(f"[bold red]Home dir {shared_state.TARGET_USER_HOME} missing.[/]")
        else: print(f"CRITICAL: Home dir {shared_state.TARGET_USER_HOME} missing.", file=sys.stderr, flush=True)
        sys.exit(1)
    
    shared_state.LOG_FILE_PATH = shared_state.SCRIPT_DIR / shared_state.LOG_FILE_NAME

    if shared_state.log:
        for handler in list(shared_state.log.handlers):
            if isinstance(handler, std_logging.FileHandler) and handler.baseFilename == str(shared_state.LOG_FILE_PATH):
                shared_state.log.removeHandler(handler)
                handler.close()

        file_log_handler = std_logging.FileHandler(shared_state.LOG_FILE_PATH, mode='a', encoding='utf-8')
        file_log_handler.setLevel(std_logging.WARNING)
        file_formatter = std_logging.Formatter("%(asctime)s [%(levelname)-8s] %(name)s (%(filename)s:%(lineno)d): %(message)s")
        file_log_handler.setFormatter(file_formatter)
        shared_state.log.addHandler(file_log_handler)

        shared_state.log.info(f"--- Nova System Setup Script Initialized (Log vUI.Corrected.2) ---")
        shared_state.log.info(f"Target user: [yellow]{shared_state.TARGET_USER}[/], home: [yellow]{shared_state.TARGET_USER_HOME}[/].")

        try:
            from rich.markup import escape as escape_markup_func
        except ImportError:
            escape_markup_func = lambda text_to_escape: str(text_to_escape).replace('[', r'\[').replace(']', r'\]')
            shared_state.log.warning("rich.markup.escape not found, using basic fallback for log path in ui.py.")
        
        escaped_log_path_ui = escape_markup_func(str(shared_state.LOG_FILE_PATH))
        shared_state.log.info(f"Console INFO logging. File WARNING+ logging to: [link=file://{escaped_log_path_ui}][cyan]{escaped_log_path_ui}[/cyan][/link]")
    else:
        print(f"Fallback logging: File (WARNING+) to {shared_state.LOG_FILE_PATH}", flush=True)

    if not shared_state.ZSHRC_SOURCE_PATH or not shared_state.ZSHRC_SOURCE_PATH.is_file():
        msg_err_zsh = f"Source .zshrc missing: '{shared_state.ZSHRC_SOURCE_PATH}'"
        if shared_state.log: shared_state.log.critical(f"[bold red]{msg_err_zsh}. Exiting.[/]")
        else: print(f"CRITICAL: {msg_err_zsh}. Exiting.", file=sys.stderr, flush=True)
        sys.exit(1)
    if not shared_state.NANORC_SOURCE_PATH or not shared_state.NANORC_SOURCE_PATH.is_file():
        msg_err_nano = f"Source .nanorc missing: '{shared_state.NANORC_SOURCE_PATH}'"
        if shared_state.log: shared_state.log.critical(f"[bold red]{msg_err_nano}. Exiting.[/]")
        else: print(f"CRITICAL: {msg_err_nano}. Exiting.", file=sys.stderr, flush=True)
        sys.exit(1)
    if shared_state.log: shared_state.log.info("Source config files (.zshrc, .nanorc) found.")


def perform_initial_setup():
    _, Panel_cls, Text_cls, _, _, _, _, _, _ = shared_state.get_rich_components()

    shared_state.console.rule("[bold sky_blue2]Initial Environment Setup[/]", style="sky_blue2")
    perform_system_update_check()
    check_critical_deps()
    install_dnf_packages(shared_state.DNF_PACKAGES_BASE) # Zsh è in DNF_PACKAGES_BASE
    
    install_oh_my_zsh()
    install_omz_plugins()
    
    if shared_state.TARGET_USER:
        # Verifica se zsh è installato prima di tentare di cambiarlo
        if command_utils.check_command_exists(["zsh"]): # Controlla se zsh è nel PATH di root (dnf lo installa lì)
             set_default_shell_to_zsh(shared_state.TARGET_USER)
        else:
             shared_state.log.warning("Zsh command not found in root's PATH after DNF install (unexpected). Skipping default shell change for user.")
    
    install_cargo_tools()
    install_scripted_tools() 
    copy_config_files()
    perform_post_install_checks(check_gnome_specific_tools=False)
    
    shared_state.console.print(Panel_cls(Text_cls("Initial Setup Process Completed!", style="bold green"), expand=False))


def display_main_menu() -> bool:
    _, Panel_cls, Text_cls, Confirm_cls, Prompt_cls, _, _, Table_cls, Padding_cls = shared_state.get_rich_components()

    shared_state.console.print(Panel_cls(Text_cls("✨ Nova System Setup ✨", justify="center", style="bold white on dark_blue")))
    
    menu_options = {
        "1": ("Perform Initial Environment Setup", perform_initial_setup),
        "2": ("Manage GNOME Shell Extensions", manage_gnome_extensions),
        "3": ("Exit Nova Setup", lambda: sys.exit(0))
    }
    main_menu_exit_flag = False
    while True:
        shared_state.console.rule("[bold gold1]Main Menu[/]", style="gold1")
        menu_table = Table_cls(show_header=False, box=None, padding=(0,1))
        menu_table.add_column(style="cyan", justify="right"); menu_table.add_column()
        for key_choice, (desc_choice,_) in menu_options.items(): menu_table.add_row(f"[{key_choice}]", desc_choice)
        shared_state.console.print(Padding_cls(menu_table, (1,2)))
        
        user_choice = Prompt_cls.ask("Your choice", choices=list(menu_options.keys()), show_choices=False, console=shared_state.console)
        
        main_menu_exit_flag = (user_choice == "3")
        selected_desc, selected_action = menu_options[user_choice]
        shared_state.log.info(f"User selected menu option: ({user_choice}) {selected_desc}")
        
        if selected_action:
            try: selected_action()
            except SystemExit:
                shared_state.log.info(f"Exiting '{selected_desc}' due to SystemExit.")
                if main_menu_exit_flag: 
                    console_out_path = shared_state.SCRIPT_DIR / "nova_setup_console_output.txt"
                    try:
                        if shared_state.console: shared_state.console.save_text(console_out_path)
                        shared_state.log.info(f"Console output on exit: {console_out_path}")
                    except Exception as e_save: shared_state.log.error(f"Failed console save on exit: {e_save}")
                raise 
            except Exception as e_action:
                shared_state.log.exception(f"Error during '{selected_desc}': {e_action}")
                if shared_state.console:
                    shared_state.console.print_exception(show_locals=True, max_frames=5)
                    shared_state.console.print(Panel_cls(f"Error in '{selected_desc}'. Logs: {shared_state.LOG_FILE_PATH}", title="[red]Action Failed[/]",style="red"))
        
        if main_menu_exit_flag: break
        if not Confirm_cls.ask("\nReturn to main menu?", default=True, console=shared_state.console):
            shared_state.log.info("User chose not to return to main menu. Exiting."); main_menu_exit_flag = True; break
            
    return main_menu_exit_flag