#!/usr/bin/env python3

import sys
import subprocess # Kept for potential future use, though not used by core logic now
import importlib # Kept for potential future use
import logging as std_logging # Used before Rich is set up for basic config, and potentially for FileHandler
from pathlib import Path

# Rich components will be imported directly in main()
# No global placeholders needed here anymore.

def main():
    # Initialize shared_state to None. It will be assigned the module object
    # after successful Rich import and its own import.
    # This allows the 'finally' block to check 'if shared_state:'
    shared_state_module = None
    # Initialize clean_script_exit_flag for use in the 'finally' block
    # It tracks if the script is exiting cleanly via the menu's "Exit" option.
    clean_script_exit_flag = False

    try:
        # Attempt to import Rich components directly.
        # If 'rich' is not installed, this will raise an ImportError.
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text
            from rich.prompt import Confirm, Prompt, IntPrompt
            from rich.logging import RichHandler
            from rich.table import Table
            from rich.padding import Padding
            from rich.markup import escape as escape_markup_text
        except ImportError:
            print("ERROR: The 'rich' library is not installed, or not found in the Python environment.", file=sys.stderr, flush=True)
            print("       This script requires 'rich' for its user interface and logging.", file=sys.stderr, flush=True)
            print("       Please install it. You can typically do this by running:", file=sys.stderr, flush=True)
            print("         python3 -m pip install rich", file=sys.stderr, flush=True)
            print("       Alternatively, if a 'requirements.txt' file is provided with this script:", file=sys.stderr, flush=True)
            print("         python3 -m pip install -r requirements.txt", file=sys.stderr, flush=True)
            sys.exit(1)

        # Import shared_state ONLY NOW, after Rich types are confirmed to be available.
        # Assign it to the local variable for clarity and use in 'finally'.
        from nova_setup import shared_state as imported_shared_state
        shared_state_module = imported_shared_state
        
        # Populate Rich component TYPES in shared_state
        shared_state_module._set_rich_components(
            Console, Panel, Text,
            Confirm, Prompt, IntPrompt,
            RichHandler, Table, Padding
        )
        
        # Initialize the global shared_state.console INSTANCE using the Console CLASS from shared_state
        shared_state_module.console = shared_state_module.Console(record=True, log_time=False, log_path=False)
        
        # Configure the main logger to use RichHandler with the console instance
        std_logging.basicConfig(
            level="DEBUG", # The root logger captures everything from DEBUG upwards
            format="%(message)s", # RichHandler will take care of the actual formatting
            datefmt="[%X]", # Datetime format for logs (used by RichHandler)
            handlers=[shared_state_module.RichHandler( # Use RichHandler CLASS from shared_state
                console=shared_state_module.console,
                rich_tracebacks=True,
                markup=True,
                show_path=False,
                show_level=True, # Show log level (INFO, ERROR, etc.) on the console
                log_time_format="[%X]" # Specific time format for RichHandler
            )]
        )
        shared_state_module.log = std_logging.getLogger("nova-setup") # Get an application-specific logger
        shared_state_module.log.setLevel(std_logging.INFO) # Set level for console output to INFO

        # Import other modules from the nova_setup package NOW that shared_state is partially initialized
        from nova_setup import ui
        from nova_setup.system_config import initialize_script_base_paths # For setting SCRIPT_DIR

        initialize_script_base_paths() # Sets shared_state.SCRIPT_DIR and source file paths

        # Complete initialization (user, log paths, etc.) and start the main menu
        ui.initialize_script_logging_and_user()
        clean_script_exit_flag = ui.display_main_menu()

    except SystemExit:
        # Catch sys.exit() called explicitly (e.g., from the menu's "Exit" option)
        log_message = "Nova System Setup exited via SystemExit."
        if shared_state_module and hasattr(shared_state_module, 'log') and shared_state_module.log:
            shared_state_module.log.info(log_message)
        else: # Fallback if logger is not available
            print(f"INFO: {log_message}", flush=True)
        clean_script_exit_flag = True # Consider this a clean exit
    except Exception as e_unhandled_main:
        # Handle critical exceptions not caught elsewhere
        error_message = f"[bold red]Unhandled critical error in main execution: {e_unhandled_main}[/]"
        if shared_state_module and hasattr(shared_state_module, 'log') and shared_state_module.log:
            shared_state_module.log.exception(error_message, exc_info=e_unhandled_main) # Ensure traceback is logged
        else:
            print(f"CRITICAL ERROR (logger not available): {e_unhandled_main}", file=sys.stderr, flush=True)
        
        if shared_state_module and hasattr(shared_state_module, 'console') and shared_state_module.console:
            shared_state_module.console.print_exception(show_locals=True, max_frames=8)
            # Use Panel CLASS from shared_state to create the panel
            panel_error_text = ("A critical error occurred. "
                                "Please check logs (if available) and console output.")
            if hasattr(shared_state_module, 'LOG_FILE_PATH') and shared_state_module.LOG_FILE_PATH:
                panel_error_text = f"A critical error occurred. Please check logs at {shared_state_module.LOG_FILE_PATH} and console output."
            
            shared_state_module.console.print(
                shared_state_module.Panel(panel_error_text, title="[bold red]NOVA SETUP FAILED CRITICALLY[/]", border_style="red")
            )
        sys.exit(1) # Exit with error code
    finally:
        # 'finally' block to ensure console output and final messages are handled
        
        # Default paths in case shared_state_module or its attributes weren't set (e.g., due to early exit)
        final_log_file_path_obj = Path("nova_setup.log") # A sensible default name
        console_output_file_dir = Path(".") # Default to current directory

        if shared_state_module and hasattr(shared_state_module, 'LOG_FILE_PATH') and shared_state_module.LOG_FILE_PATH:
            final_log_file_path_obj = shared_state_module.LOG_FILE_PATH
        if shared_state_module and hasattr(shared_state_module, 'SCRIPT_DIR') and shared_state_module.SCRIPT_DIR:
            console_output_file_dir = shared_state_module.SCRIPT_DIR
        
        console_output_file_path_obj = console_output_file_dir / "nova_setup_console_output.txt"
        
        # Save console output if it was not a "clean" exit via the menu's Exit option
        # (display_main_menu saves on its own if the "Exit" option is chosen)
        if shared_state_module and hasattr(shared_state_module, 'console') and shared_state_module.console and not clean_script_exit_flag:
            try:
                # Save only if the file doesn't already exist, to avoid overwriting a previous save
                # made by a clean exit from the menu.
                if not console_output_file_path_obj.exists():
                    shared_state_module.console.save_text(str(console_output_file_path_obj)) # save_text expects string path
                    log_msg = f"Console output (abrupt exit path or non-menu exit) saved to {console_output_file_path_obj}"
                    if hasattr(shared_state_module, 'log') and shared_state_module.log:
                        shared_state_module.log.info(log_msg)
                    else:
                        print(f"INFO: {log_msg}", flush=True)
            except Exception as e_save_console_final:
                err_msg = f"Error saving console output in main's finally block: {e_save_console_final}"
                if hasattr(shared_state_module, 'log') and shared_state_module.log:
                    shared_state_module.log.error(err_msg)
                else:
                    print(f"ERROR: Failed to save console output in main's finally block: {err_msg}", file=sys.stderr, flush=True)
        
        # Final log message
        if shared_state_module and hasattr(shared_state_module, 'log') and shared_state_module.log:
            try:
                # escape_markup_text is imported at the beginning of the try block in main
                # If we are here and log is available, Rich was imported successfully.
                escaped_log_path_str = escape_markup_text(str(final_log_file_path_obj))
                shared_state_module.log.info(f"--- Nova Setup execution finished. File log (WARNING+): [link=file://{escaped_log_path_str}]{escaped_log_path_str}[/link] ---")
            except NameError: # Should not happen if rich was imported.
                 shared_state_module.log.warning(f"rich.markup.escape function was not found. Log path link might not be correct: {final_log_file_path_obj}")
            except Exception as e_final_log_message:
                shared_state_module.log.error(f"Error generating final log message: {e_final_log_message}")
        else:
            # This 'else' block is reached if shared_state_module.log is not available.
            # This includes the case where 'rich' import failed and the script exited early.
            # We want to avoid printing this if the ImportError for 'rich' was the reason for exit,
            # as a more specific message was already printed.
            current_exception_type, current_exception_value, _ = sys.exc_info()
            is_rich_import_error = False
            if current_exception_type and issubclass(current_exception_type, ImportError):
                if "rich" in str(current_exception_value).lower():
                    is_rich_import_error = True
            
            if not is_rich_import_error:
                print(f"INFO: Nova Setup execution finished. Log file expected at: {final_log_file_path_obj}", flush=True)

if __name__ == "__main__":
    main()