# Fedora-AutoEnv-Setup/install.py

import sys
from pathlib import Path

# Ensure the script's directory is in the Python path
sys.path.insert(0, str(Path(__file__).parent))

from scripts import console_output as con
from scripts.config import app_logger, CONFIG_FILE_NAME
from scripts.phase_manager import load_phase_status
from scripts.main_menu import main_menu_handler
from scripts.config_loader import load_configuration


def main():
    """Main function to run the Fedora AutoEnv Setup utility."""
    app_logger.info("Fedora AutoEnv Setup script started.")

    try:
        # Load application-wide configuration from packages
        app_config = load_configuration(CONFIG_FILE_NAME) # Explicitly pass filename
        if not app_config: # load_configuration returns {} on error or empty file
            # Check if the file itself is missing, as load_configuration prints detailed errors
            if not Path(CONFIG_FILE_NAME).is_file():
                con.print_error(f"Critical: Configuration file '{CONFIG_FILE_NAME}' not found in project root or current directory.", exit_after=True)
            else:
                # File exists but is empty, or parsing failed (error already printed by loader)
                con.print_error(f"Critical: Failed to load or parse '{CONFIG_FILE_NAME}'. Please ensure it exists and is valid. Check messages above.", exit_after=True)
            sys.exit(1) # exit_after=True should handle this, but being explicit.

        phase_status = load_phase_status()
        main_menu_handler(app_config, phase_status)

    except ImportError as e:
        # This is a critical error, as it means the script's structure is broken.
        print(f"FATAL: A required module could not be imported: {e}", file=sys.stderr)
        print("This usually means the script is being run from the wrong directory or the file structure is incorrect.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # con.console.print_exception(show_locals=True) # Rich traceback to console
        app_logger.critical(f"An unexpected critical error occurred in the main application: {e}", exc_info=True) # Log with traceback
        con.print_error(f"An unexpected critical error occurred: {e}. Check the log file for details.")


    # In finally block:
    finally:
        app_logger.info("Fedora AutoEnv Setup script finished.")
        con.print_info("Fedora AutoEnv Setup finished.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        con.print_info("\nOperation cancelled by user. Exiting.")
    except Exception as e:
        con.console.print_exception(show_locals=True) # Rich traceback for debugging
        con.print_error(f"An unexpected critical error occurred in the main application: {e}")
    finally:
        con.print_info("Fedora AutoEnv Setup finished.")