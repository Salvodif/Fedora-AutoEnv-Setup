#!/usr/bin/env python3
# fedora_config_app/main.py
# English: Main entry point for the Fedora Configuration App.

import sys
import os

# Ensure the app's root directory is in PYTHONPATH if running as a script
# This allows for `from fedora_config_app.myrich import ...` style imports
# if you run `python fedora_config_app/main.py` from one level up.
# If running `python main.py` from within `fedora_config_app/`, direct imports work.
# For robustness, especially if packaging later:
# current_dir = os.path.dirname(os.path.abspath(__file__))
# parent_dir = os.path.dirname(current_dir)
# if parent_dir not in sys.path:
#    sys.path.insert(0, parent_dir)

# If running directly from fedora_config_app, these imports should work:
from myrich import console, print_header, print_message, ask_question, confirm_action
from logging_setup import logger # This initializes logging
from actions import basic_config # This imports the basic_config.py module

def display_main_menu():
    """Displays the main menu and returns the user's choice."""
    console.line(2)
    print_header("Fedora Configuration App Menu")
    
    options = {
        "1": "Basic Configuration (Install essential packages)",
        "0": "Exit"
    }
    
    for key, value in options.items():
        console.print(f"[bold cyan]{key}[/bold cyan]: {value}")
    console.line()
    
    choice = ask_question("Enter your choice", choices=list(options.keys()))
    return choice

def main():
    """Main application loop."""
    logger.info("Application started.")
    print_header("Welcome to the Fedora Post-Install Setup Script!")
    print_message("This script will help you configure your new Fedora installation.", style="info")
    
    # Check for sudo/root privileges early, although dnf will prompt anyway
    # This is more of a UX heads-up.
    if os.geteuid() != 0:
        print_message(
            "This script requires superuser (sudo) privileges for some operations (like DNF).\n"
            "You will be prompted for your password by the system when needed.",
            style="warning"
        )
        logger.warning("Script not run as root. Sudo will be required for DNF operations.")
    else:
        print_message("Script running with root privileges.", style="info")
        logger.info("Script running with root privileges.")


    while True:
        user_choice = display_main_menu()
        
        if user_choice == "1":
            logger.info("User selected 'Basic Configuration'.")
            print_header("Basic Configuration")
            if confirm_action("Proceed with basic package installation?", default=True):
                try:
                    basic_config.run_basic_configuration()
                except Exception as e:
                    err_msg = f"An unexpected error occurred during basic configuration: {e}"
                    print_message(err_msg, style="error")
                    logger.exception(err_msg) # Logs with stack trace
                print_message("Returned to main menu.", style="info")
            else:
                print_message("Basic configuration cancelled.", style="info")
                logger.info("User cancelled basic configuration.")
        
        elif user_choice == "0":
            print_message("Exiting application. Goodbye!", style="success")
            logger.info("Application exiting.")
            break
            
        else:
            # Should not happen if using Prompt with choices, but good for robustness
            print_message(f"Invalid choice '{user_choice}'. Please try again.", style="error")
            logger.warning(f"Invalid menu choice: {user_choice}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_message("\nApplication interrupted by user. Exiting.", style="warning")
        logger.warning("Application interrupted by user (KeyboardInterrupt).")
    except Exception as e:
        # Catch-all for unexpected errors at the top level
        print_message(f"A critical unexpected error occurred: {e}", style="error")
        logger.critical(f"Unhandled top-level exception: {e}", exc_info=True)
        sys.exit(1)
    sys.exit(0)