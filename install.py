#!/usr/bin/env python3

import sys
import subprocess
import importlib
import logging as std_logging
from pathlib import Path

# Placeholder for rich components - will be populated after check
RichConsoleImport = None
RichPanelImport = None
RichTextImport = None
RichConfirmImport = None
RichPromptImport = None
RichIntPromptImport = None
RichLoggingHandlerImport = None
RichTableImport = None
RichPaddingImport = None

def _ensure_rich_library() -> bool:
    """Checks for 'rich', installs/upgrades if necessary. Returns True if available."""
    rich_module = None
    try:
        rich_module = importlib.import_module("rich")
        current_version = getattr(rich_module, "__version__", "unknown")
        print(f"Python 'rich' library found (v{current_version}). Checking for updates...", flush=True)
        try:
            pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "rich"]
            pip_process = subprocess.run(pip_cmd, check=True, capture_output=True, text=True, timeout=60)
            if "Requirement already satisfied" not in pip_process.stdout and "already up-to-date" not in pip_process.stdout:
                 print("Python 'rich' library updated. Reloading...", flush=True)
                 rich_module = importlib.reload(rich_module)
                 print(f"Python 'rich' reloaded (v{getattr(rich_module, '__version__', 'unknown')}).", flush=True)
            else: print("Python 'rich' is up-to-date.", flush=True)
            return True
        except subprocess.TimeoutExpired: print("Warning: Timeout upgrading 'rich'. Using installed.", file=sys.stderr, flush=True); return True
        except subprocess.CalledProcessError as e: print(f"Warning: Could not upgrade 'rich': {e.stderr.strip()}. Using installed.", file=sys.stderr, flush=True); return True
        except Exception as e_up: print(f"Warning: Error upgrading 'rich': {e_up}. Using installed.", file=sys.stderr, flush=True); return True
    except ImportError:
        print("Python 'rich' not found. Attempting to install...", flush=True)
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "rich"], check=True, capture_output=True, text=True, timeout=60)
            print("Python 'rich' installed. Attempting to load...", flush=True)
            rich_module = importlib.import_module("rich")
            print(f"Python 'rich' loaded (v{getattr(rich_module, '__version__', 'unknown')}).", flush=True)
            return True
        except subprocess.TimeoutExpired: print("ERROR: Timeout installing 'rich'. Please install manually ('pip install rich').", file=sys.stderr, flush=True); return False
        except subprocess.CalledProcessError as e: print(f"ERROR: Failed to install 'rich': {e.stderr.strip()}. Please install manually.", file=sys.stderr, flush=True); return False
        except ImportError: print("ERROR: 'rich' installed but cannot be imported. Check environment.", file=sys.stderr, flush=True); return False
        except Exception as e_inst: print(f"ERROR: Unexpected error installing 'rich': {e_inst}", file=sys.stderr, flush=True); return False
    return False # Should not be reached

def main():
    global RichConsoleImport, RichPanelImport, RichTextImport, RichConfirmImport, RichPromptImport
    global RichIntPromptImport, RichLoggingHandlerImport, RichTableImport, RichPaddingImport

    if not _ensure_rich_library():
        sys.exit(1)

    # Dynamically import rich components now that it's ensured
    from rich.console import Console as RichConsoleImp
    from rich.panel import Panel as RichPanelImp
    from rich.text import Text as RichTextImp
    from rich.prompt import Confirm as RichConfirmImp, Prompt as RichPromptImp, IntPrompt as RichIntPromptImp
    from rich.logging import RichHandler as RichLoggingHandlerImp
    from rich.table import Table as RichTableImp
    from rich.padding import Padding as RichPaddingImp

    RichConsoleImport = RichConsoleImp
    RichPanelImport = RichPanelImp
    RichTextImport = RichTextImp
    RichConfirmImport = RichConfirmImp
    RichPromptImport = RichPromptImp
    RichIntPromptImport = RichIntPromptImp
    RichLoggingHandlerImport = RichLoggingHandlerImp
    RichTableImport = RichTableImp
    RichPaddingImport = RichPaddingImp

    # Import shared_state now that rich components are assigned at the top level of this script
    # These top-level assignments will be seen by shared_state when it's imported.
    from nova_setup import shared_state
    
    # Initialize console and logger in shared_state
    shared_state.console = RichConsoleImport(record=True, log_time=False, log_path=False)
    
    std_logging.basicConfig(
        level="DEBUG", # Root logger level
        format="%(message)s", 
        datefmt="[%X]", 
        handlers=[RichLoggingHandlerImp(
            console=shared_state.console, 
            rich_tracebacks=True, 
            markup=True, 
            show_path=False, 
            show_level=True, # Show level on console
            log_time_format="[%X]"
        )]
    )
    shared_state.log = std_logging.getLogger("nova-setup")
    shared_state.log.setLevel(std_logging.INFO) # Console output set to INFO

    # Now import other modules that depend on shared_state being partially initialized
    from nova_setup import ui
    from nova_setup.system_config import initialize_script_base_paths # For SCRIPT_DIR

    initialize_script_base_paths() # Sets SCRIPT_DIR in shared_state

    clean_script_exit = False
    try:
        ui.initialize_script_logging_and_user() # Completes shared_state init, sets log file
        clean_script_exit = ui.display_main_menu()
    except SystemExit:
        if shared_state.log: shared_state.log.info("Nova System Setup exited via SystemExit.")
        else: print("INFO: Nova System Setup exited via SystemExit.", flush=True)
        clean_script_exit = True 
    except Exception as e_main:
        if shared_state.log: shared_state.log.exception(f"[bold red]Unhandled critical error in main: {e_main}[/]")
        else: print(f"CRITICAL ERROR (logger N/A): {e_main}", file=sys.stderr, flush=True)
        
        if shared_state.console:
            shared_state.console.print_exception(show_locals=True, max_frames=8)
            shared_state.console.print(RichPanelImport(f"Critical error. Logs: {shared_state.LOG_FILE_PATH}", title="[red]NOVA SETUP FAILED[/]", style="red"))
        sys.exit(1)
    finally:
        final_log_file_path = shared_state.LOG_FILE_PATH
        console_output_file_path = shared_state.SCRIPT_DIR / "nova_setup_console_output.txt"
        
        if shared_state.console and not clean_script_exit:
            try:
                if not console_output_file_path.exists(): # Avoid re-saving if menu exit already did
                    shared_state.console.save_text(console_output_file_path)
                    if shared_state.log: shared_state.log.info(f"Console output (abrupt exit): {console_output_file_path}")
            except Exception as e_save_f:
                if shared_state.log: shared_state.log.error(f"Error saving console (main finally): {e_save_f}")
                else: print(f"ERROR: Saving console output: {e_save_f}", file=sys.stderr, flush=True)
        
        if shared_state.log:
            shared_state.log.info(f"--- Nova Setup execution finished. File log (WARNING+): [link=file://{final_log_file_path}]{final_log_file_path}[/link] ---")
        else: print(f"INFO: Execution finished. Log: {final_log_file_path}", flush=True)

if __name__ == "__main__":
    main()