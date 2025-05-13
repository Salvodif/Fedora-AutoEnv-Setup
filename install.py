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
        
        # CORREZIONE: Definisci force_upgrade_check qui
        force_upgrade_check = current_version == "unknown" 

        try:
            pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "rich"]
            pip_process = subprocess.run(pip_cmd, check=True, capture_output=True, text=True, timeout=60)
            
            was_upgraded_or_installed = "Successfully installed rich" in pip_process.stdout or \
                                        ( "Requirement already satisfied" not in pip_process.stdout and \
                                          "already up-to-date" not in pip_process.stdout )

            # Ora force_upgrade_check è definito quando viene usato qui
            if was_upgraded_or_installed or force_upgrade_check:
                 print("Python 'rich' library may have been updated or version was unknown. Reloading...", flush=True)
                 for k in list(sys.modules.keys()):
                     if k.startswith('rich'):
                         del sys.modules[k]
                 rich_module = importlib.import_module("rich")
                 new_version = getattr(rich_module, "__version__", "still unknown")
                 print(f"Python 'rich' library reloaded (new version {new_version}).", flush=True)
                 if new_version == "still unknown":
                     print("Warning: 'rich' version still unknown after reload. Installation might be problematic.", file=sys.stderr, flush=True)
            else:
                print("Python 'rich' library is up-to-date.", flush=True)
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
    from rich.markup import escape as RichMarkupEscapeFunc

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
    shared_state._set_rich_components(
        RichConsoleImp, RichPanelImp, RichTextImp, 
        RichConfirmImp, RichPromptImp, RichIntPromptImp, 
        RichLoggingHandlerImp, RichTableImp, RichPaddingImp
    )

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
        if shared_state.log:
            shared_state.log.info("Nova System Setup exited via SystemExit.")
        else: print("INFO: Nova System Setup exited via SystemExit.", flush=True)
        clean_script_exit = True 
    except Exception as e_main:
        if shared_state.log:
            # Importa la funzione di escape o usa un fallback
            try:
                from rich.markup import escape as rich_escape_func
            except ImportError:
                rich_escape_func = lambda text: str(text).replace('[', r'\[').replace(']', r'\]')
                if shared_state.log: shared_state.log.warning("rich.markup.escape not found, using basic escape for exception logging.")

            # Fai l'escape del messaggio dell'eccezione
            escaped_exception_message = rich_escape_func(str(e_main))
            
            # Logga il messaggio con l'escape, mantenendo il traceback originale
            shared_state.log.exception(f"[bold red]Unhandled critical error in main: {escaped_exception_message}[/]",
                                       exc_info=e_main) # Passa l'eccezione originale per il traceback
        else: 
            print(f"CRITICAL ERROR (logger N/A): {e_main}", file=sys.stderr, flush=True)
        
        if shared_state.console:
            shared_state.console.print_exception(show_locals=True, max_frames=8) # Questo stamperà il traceback di e_main
            # Per il Panel, usiamo anche qui l'escape se e_main fosse incluso nel testo del Panel
            # Ma qui stampiamo solo un messaggio generico e il percorso del log.
            panel_text = f"A critical error occurred. Please check the logs (if available) at {shared_state.LOG_FILE_PATH} and the console output above."
            shared_state.console.print(RichPanelImport(panel_text, title="[bold red]NOVA SETUP FAILED CRITICALLY[/]", border_style="red"))
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
            escaped_log_path = RichMarkupEscapeFunc(str(final_log_file_path))
            shared_state.log.info(f"--- Nova Setup execution finished. Full log at [link=file://{escaped_log_path}]{escaped_log_path}[/link] ---")

if __name__ == "__main__":
    main()
