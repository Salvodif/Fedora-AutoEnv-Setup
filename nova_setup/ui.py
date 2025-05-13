import os
import sys
import pwd
import logging as std_logging # For file handler setup
from pathlib import Path

# Import from sibling modules within the 'nova_setup' package
from . import shared_state
from .system_config import perform_system_update_check, check_critical_deps
from .package_manager import install_dnf_packages
from .shell_customization import install_oh_my_zsh, install_omz_plugins
from .tool_installers import install_cargo_tools, install_scripted_tools
from .config_files import copy_config_files
from .gnome_manager import manage_gnome_extensions
from .post_install_checks import perform_post_install_checks


def initialize_script_logging_and_user():
    """Initializes user-specific paths and file logging.
    Assumes shared_state.log (Rich logger) and shared_state.SCRIPT_DIR are already set.
    """
    if os.geteuid() != 0:
        shared_state.log.critical("[bold red]Must be run as root (sudo).[/]")
        sys.exit(1)

    shared_state.TARGET_USER = os.getenv("SUDO_USER")
    if not shared_state.TARGET_USER:
        shared_state.log.warning("No SUDO_USER. Targeting root user.")
        shared_state.TARGET_USER = pwd.getpwuid(os.geteuid()).pw_name
    
    try:
        pw_entry = pwd.getpwnam(shared_state.TARGET_USER)
        shared_state.TARGET_USER_HOME = Path(pw_entry.pw_dir)
    except KeyError:
        shared_state.log.critical(f"[bold red]User '{shared_state.TARGET_USER}' not found.[/]")
        sys.exit(1)
    
    if not shared_state.TARGET_USER_HOME.is_dir():
        shared_state.log.critical(f"[bold red]Home dir {shared_state.TARGET_USER_HOME} missing.[/]")
        sys.exit(1)
    
    # LOG_FILE_PATH is already SCRIPT_DIR / LOG_FILE_NAME from shared_state default
    # but let's confirm it's set based on SCRIPT_DIR which is now definitively known
    shared_state.LOG_FILE_PATH = shared_state.SCRIPT_DIR / shared_state.LOG_FILE_NAME

    # Configure file logging part (WARNING+ level)
    file_log_handler = std_logging.FileHandler(shared_state.LOG_FILE_PATH, mode='a', encoding='utf-8') # Append mode
    file_log_handler.setLevel(std_logging.WARNING)
    file_formatter = std_logging.Formatter("%(asctime)s [%(levelname)-8s] %(name)s: %(message)s (%(filename)s:%(lineno)d)")
    file_log_handler.setFormatter(file_formatter)
    shared_state.log.addHandler(file_log_handler) # Add to the Rich-based logger

    shared_state.log.info(f"--- Nova System Setup Script Initialized (Log vRefactor) ---")
    shared_state.log.info(f"Target user: [yellow]{shared_state.TARGET_USER}[/], home: [yellow]{shared_state.TARGET_USER_HOME}[/].")
    shared_state.log.info(f"Console INFO logging enabled. File WARNING+ logging to: [cyan]{shared_state.LOG_FILE_PATH}[/link]")
    
    # Check source config files
    if not shared_state.ZSHRC_SOURCE_PATH or not shared_state.ZSHRC_SOURCE_PATH.is_file() or \
       not shared_state.NANORC_SOURCE_PATH or not shared_state.NANORC_SOURCE_PATH.is_file():
        shared_state.log.critical("[bold red]Source .zshrc or .nanorc missing or paths invalid. Exiting.[/]")
        sys.exit(1)
    shared_state.log.info("Source config files (.zshrc, .nanorc) found and paths are set.")


def perform_initial_setup():
    Console, Panel, Text, _, _, _, _, _, _ = shared_state.get_rich_components()
    shared_state.console.rule("[bold sky_blue2]Initial Environment Setup[/]", style="sky_blue2")
    perform_system_update_check()
    check_critical_deps()
    install_dnf_packages(shared_state.DNF_PACKAGES_BASE)
    install_oh_my_zsh()
    install_omz_plugins()
    install_cargo_tools()
    install_scripted_tools() 
    copy_config_files()
    perform_post_install_checks()
    shared_state.console.print(Panel(Text("Initial Setup Process Completed!", style="bold green"), expand=False))


def display_main_menu() -> bool:
    Console, Panel, Text, Confirm, Prompt, _, _, Table, Padding = shared_state.get_rich_components()

    shared_state.console.print(Panel(Text("✨ Nova System Setup ✨", justify="center", style="bold white on dark_blue")))
    menu_options = {
        "1": ("Perform Initial Environment Setup", perform_initial_setup),
        "2": ("Manage GNOME Shell Extensions", manage_gnome_extensions),
        "3": ("Exit Nova Setup", lambda: sys.exit(0))
    }
    main_menu_exit_flag = False
    while True:
        shared_state.console.rule("[bold gold1]Main Menu[/]", style="gold1")
        menu_table = Table(show_header=False, box=None, padding=(0,1))
        menu_table.add_column(style="cyan", justify="right"); menu_table.add_column()
        for key_choice, (desc_choice,_) in menu_options.items(): menu_table.add_row(f"[{key_choice}]", desc_choice)
        shared_state.console.print(Padding(menu_table, (1,2)))
        
        user_choice = Prompt.ask("Your choice", choices=list(menu_options.keys()), show_choices=False, console=shared_state.console)
        
        main_menu_exit_flag = (user_choice == "3")
        selected_desc, selected_action = menu_options[user_choice]
        shared_state.log.info(f"User selected menu option: ({user_choice}) {selected_desc}")
        
        if selected_action:
            try: selected_action()
            except SystemExit:
                shared_state.log.info(f"Exiting '{selected_desc}' due to SystemExit.")
                if main_menu_exit_flag: # This was the "Exit" menu option
                    console_out_path = shared_state.SCRIPT_DIR / "nova_setup_console_output.txt"
                    try: shared_state.console.save_text(console_out_path); shared_state.log.info(f"Console output on exit: {console_out_path}")
                    except Exception as e_save: shared_state.log.error(f"Failed console save on exit: {e_save}")
                raise 
            except Exception as e_action:
                shared_state.log.exception(f"Error during '{selected_desc}': {e_action}")
                shared_state.console.print_exception(show_locals=True, max_frames=5)
                shared_state.console.print(Panel(f"Error in '{selected_desc}'. Logs: {shared_state.LOG_FILE_PATH}", title="[red]Action Failed[/]",style="red"))
        
        if main_menu_exit_flag: break
        if not Confirm.ask("\nReturn to main menu?", default=True, console=shared_state.console):
            shared_state.log.info("User chose not to return to main menu. Exiting."); main_menu_exit_flag = True; break
            
    return main_menu_exit_flag