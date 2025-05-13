#!/usr/bin/env python3

import sys
import subprocess
import importlib
import logging as std_logging # Usato prima che Rich sia pronto e per FileHandler
from pathlib import Path

# Questi sono placeholder. Le vere classi Rich verranno importate e assegnate dopo il check.
# Non sono usati direttamente in questo file dopo l'assegnazione a shared_state,
# ma servono per chiarezza su cosa _set_rich_components si aspetta.
RichConsoleClass = None
RichPanelClass = None
RichTextClass = None
RichConfirmClass = None
RichPromptClass = None
RichIntPromptClass = None
RichLoggingHandlerClass = None
RichTableClass = None
RichPaddingClass = None

def _ensure_rich_library() -> bool:
    """
    Checks for the 'rich' library. Installs/upgrades it if necessary.
    Returns True if rich is available and loaded, False otherwise.
    Uses standard print() for output as rich console is not yet available.
    """
    rich_module_obj = None
    try:
        # Tentativo di importare rich
        rich_module_obj = importlib.import_module("rich")
        current_version_str = getattr(rich_module_obj, "__version__", "unknown")
        print(f"Python 'rich' library found (v{current_version_str}). Checking for updates...", flush=True)
        
        # Se la versione è sconosciuta, consideralo come un motivo per tentare un aggiornamento/ricarica
        force_reload_due_to_unknown_version = current_version_str == "unknown"

        try:
            # Tenta di aggiornare rich
            pip_command = [sys.executable, "-m", "pip", "install", "--upgrade", "rich"]
            pip_run_result = subprocess.run(pip_command, check=True, capture_output=True, text=True, timeout=60)
            
            # Determina se un aggiornamento o una nuova installazione è avvenuta
            was_actually_updated_or_installed = "Successfully installed rich" in pip_run_result.stdout or \
                                                ("Requirement already satisfied" not in pip_run_result.stdout and \
                                                 "already up-to-date" not in pip_run_result.stdout)

            if was_actually_updated_or_installed or force_reload_due_to_unknown_version:
                 print("Python 'rich' library may have been updated or version was initially unknown. Reloading for consistency...", flush=True)
                 # Svuota i moduli rich da sys.modules per forzare una ricarica pulita
                 for module_key in list(sys.modules.keys()):
                     if module_key.startswith('rich'):
                         del sys.modules[module_key]
                 rich_module_obj = importlib.import_module("rich") # Ricarica fresca
                 new_version_str = getattr(rich_module_obj, "__version__", "still unknown")
                 print(f"Python 'rich' library reloaded (new version: {new_version_str}).", flush=True)
                 if new_version_str == "still unknown" and current_version_str == "unknown":
                     # Se era unknown e rimane unknown, potrebbe esserci un problema persistente
                     print("Warning: 'rich' version remains 'unknown' after reload. Installation might be problematic or metadata missing.", file=sys.stderr, flush=True)
            else:
                print("Python 'rich' library is up-to-date.", flush=True)
            return True # rich è disponibile
        except subprocess.TimeoutExpired:
            print("Warning: Timeout occurred while trying to upgrade 'rich'. Proceeding with the currently installed version (if any).", file=sys.stderr, flush=True)
            return True # rich era già importato, quindi è utilizzabile
        except subprocess.CalledProcessError as e_pip_upgrade:
            print(f"Warning: Could not upgrade 'rich' (pip command failed: {e_pip_upgrade.stderr.strip()}). Proceeding with the currently installed version (if any).", file=sys.stderr, flush=True)
            return True # rich era già importato
        except Exception as e_upgrade_general:
            print(f"Warning: An unexpected error occurred while trying to upgrade 'rich': {e_upgrade_general}. Proceeding with the currently installed version (if any).", file=sys.stderr, flush=True)
            return True # rich era già importato
    except ImportError: # rich non è installato
        print("Python 'rich' library not found. Attempting to install it...", flush=True)
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "rich"], check=True, capture_output=True, text=True, timeout=60)
            print("Python 'rich' library installed successfully. Attempting to load it...", flush=True)
            rich_module_obj = importlib.import_module("rich") # Prova ad importarlo ora
            print(f"Python 'rich' library loaded (version: {getattr(rich_module_obj, '__version__', 'unknown')}).", flush=True)
            return True # Installato e importato con successo
        except subprocess.TimeoutExpired:
            print("ERROR: Timeout occurred while trying to install 'rich'.", file=sys.stderr, flush=True)
            print("Please install 'rich' manually (e.g., 'python3 -m pip install rich') and then re-run this script.", file=sys.stderr, flush=True)
            return False
        except subprocess.CalledProcessError as e_pip_install:
            print(f"ERROR: Failed to install 'rich' library using pip: {e_pip_install.stderr.strip()}", file=sys.stderr, flush=True)
            print("Please install 'rich' manually and then re-run this script.", file=sys.stderr, flush=True)
            return False
        except ImportError: # Fallimento dell'import dopo l'installazione (molto strano)
            print("ERROR: 'rich' was reportedly installed by pip, but it still cannot be imported.", file=sys.stderr, flush=True)
            print("Please check your Python environment or try re-running the script after ensuring 'rich' is importable.", file=sys.stderr, flush=True)
            return False
        except Exception as e_install_general:
            print(f"ERROR: An unexpected error occurred while trying to install 'rich': {e_install_general}", file=sys.stderr, flush=True)
            return False
    # Fallback finale, anche se la logica sopra dovrebbe coprire tutti i casi
    return bool(rich_module_obj)


def main():
    # Queste variabili globali sono solo per passare i TIPI importati a shared_state.
    # Non sono usate direttamente come istanze in questo file dopo essere state passate.
    global RichConsoleClass, RichPanelClass, RichTextClass, RichConfirmClass, RichPromptClass
    global RichIntPromptClass, RichLoggingHandlerClass, RichTableClass, RichPaddingClass

    if not _ensure_rich_library():
        sys.exit(1) # _ensure_rich_library stampa già i dettagli dell'errore

    # Importa i componenti Rich dinamicamente ora che 'rich' è sicuramente disponibile
    from rich.console import Console as ActualRichConsole
    from rich.panel import Panel as ActualRichPanel
    from rich.text import Text as ActualRichText
    from rich.prompt import Confirm as ActualRichConfirm, Prompt as ActualRichPrompt, IntPrompt as ActualRichIntPrompt
    from rich.logging import RichHandler as ActualRichLogHandler
    from rich.table import Table as ActualRichTable
    from rich.padding import Padding as ActualRichPadding
    
    # Assegna le classi importate alle variabili globali (placeholder) definite all'inizio del file
    # Questo è fatto principalmente per chiarezza e per passarle a shared_state._set_rich_components
    RichConsoleClass, RichPanelClass, RichTextClass, RichConfirmClass, RichPromptClass, \
    RichIntPromptClass, RichLoggingHandlerClass, RichTableClass, RichPaddingClass = \
        ActualRichConsole, ActualRichPanel, ActualRichText, ActualRichConfirm, ActualRichPrompt, \
        ActualRichIntPrompt, ActualRichLogHandler, ActualRichTable, ActualRichPadding

    # Importa shared_state solo ORA, dopo che i tipi Rich sono pronti per essere passati
    from nova_setup import shared_state
    
    # Popola i TIPI dei componenti Rich in shared_state
    shared_state._set_rich_components(
        RichConsoleClass, RichPanelClass, RichTextClass, 
        RichConfirmClass, RichPromptClass, RichIntPromptClass, 
        RichLoggingHandlerClass, RichTableClass, RichPaddingClass
    )
    
    # Inizializza l'ISTANZA globale shared_state.console usando la CLASSE Console da shared_state
    # (che è stata appena impostata da _set_rich_components)
    shared_state.console = shared_state.Console(record=True, log_time=False, log_path=False)
    
    # Configura il logger principale per usare RichHandler con l'istanza console
    std_logging.basicConfig(
        level="DEBUG", # Il root logger cattura tutto da DEBUG in su
        format="%(message)s", # RichHandler si occuperà della formattazione effettiva
        datefmt="[%X]", # Formato data/ora per i log (usato da RichHandler)
        handlers=[shared_state.RichHandler( # Usa la CLASSE RichHandler da shared_state
            console=shared_state.console, 
            rich_tracebacks=True, 
            markup=True, 
            show_path=False, 
            show_level=True, # Mostra il livello del log (INFO, ERROR, etc.) sulla console
            log_time_format="[%X]" # Formato ora specifico per RichHandler
        )]
    )
    shared_state.log = std_logging.getLogger("nova-setup") # Ottieni un logger specifico per l'applicazione
    shared_state.log.setLevel(std_logging.INFO) # Imposta il livello per l'output su console a INFO (FileHandler avrà il suo)

    # Importa gli altri moduli del pacchetto nova_setup ORA che shared_state è parzialmente inizializzato
    from nova_setup import ui
    from nova_setup.system_config import initialize_script_base_paths # Per impostare SCRIPT_DIR

    initialize_script_base_paths() # Imposta shared_state.SCRIPT_DIR e i percorsi dei file sorgente

    clean_script_exit_flag = False
    try:
        # Completa l'inizializzazione (utente, percorsi log, ecc.) e avvia il menu principale
        ui.initialize_script_logging_and_user() 
        clean_script_exit_flag = ui.display_main_menu()
    except SystemExit:
        # Cattura sys.exit() chiamato esplicitamente (es. dall'opzione "Exit" del menu)
        if shared_state.log:
            shared_state.log.info("Nova System Setup exited via SystemExit.")
        else: # Fallback se il logger non è disponibile
            print("INFO: Nova System Setup exited via SystemExit.", flush=True)
        clean_script_exit_flag = True # Considera un'uscita pulita
    except Exception as e_unhandled_main:
        # Gestione di eccezioni critiche non catturate altrove
        if shared_state.log:
            shared_state.log.exception(f"[bold red]Unhandled critical error in main execution: {e_unhandled_main}[/]",
                                       exc_info=e_unhandled_main) # Assicura che il traceback sia loggato
        else: 
            print(f"CRITICAL ERROR (logger not available): {e_unhandled_main}", file=sys.stderr, flush=True)
        
        if shared_state.console: # Se la console Rich è disponibile, stampa l'eccezione
            shared_state.console.print_exception(show_locals=True, max_frames=8)
            # Usa la CLASSE Panel da shared_state per creare il pannello
            panel_error_text = f"A critical error occurred. Please check logs at {shared_state.LOG_FILE_PATH} and console output."
            shared_state.console.print(shared_state.Panel(panel_error_text, title="[bold red]NOVA SETUP FAILED CRITICALLY[/]", border_style="red"))
        sys.exit(1) # Esci con codice di errore
    finally:
        # Blocco finally per assicurare che l'output della console e i messaggi finali vengano gestiti
        final_log_file_path_obj = shared_state.LOG_FILE_PATH # Questo è un oggetto Path
        console_output_file_path_obj = shared_state.SCRIPT_DIR / "nova_setup_console_output.txt"
        
        # Salva l'output della console se non è stata un'uscita "pulita" tramite l'opzione Exit del menu
        # (display_main_menu salva autonomamente se l'opzione "Exit" viene scelta)
        if shared_state.console and not clean_script_exit_flag: 
            try:
                # Salva solo se il file non esiste già, per evitare di sovrascrivere un salvataggio precedente
                # fatto da un'uscita pulita dal menu.
                if not console_output_file_path_obj.exists(): 
                    shared_state.console.save_text(console_output_file_path_obj)
                    if shared_state.log: 
                        shared_state.log.info(f"Console output (abrupt exit path or non-menu exit) saved to {console_output_file_path_obj}")
            except Exception as e_save_console_final: 
                # Logga l'errore nel salvataggio dell'output della console
                if shared_state.log: 
                    shared_state.log.error(f"Error saving console output in main's finally block: {e_save_console_final}")
                else: 
                    print(f"ERROR: Failed to save console output in main's finally block: {e_save_console_final}", file=sys.stderr, flush=True)
        
        # Messaggio di log finale
        if shared_state.log:
            try:
                # Importa la funzione di escape corretta da rich.markup
                from rich.markup import escape as escape_markup_function
            except ImportError:
                # Fallback molto semplice se rich.markup.escape non è disponibile
                escape_markup_function = lambda text_to_escape: str(text_to_escape).replace('[', r'\[').replace(']', r'\]')
                shared_state.log.warning("rich.markup.escape not found in install.py (finally block), using basic fallback for log path link.")

            escaped_log_path_str = escape_markup_function(str(final_log_file_path_obj))
            shared_state.log.info(f"--- Nova Setup execution finished. File log (WARNING+): [link=file://{escaped_log_path_str}]{escaped_log_path_str}[/link] ---")
        else: 
            print(f"INFO: Nova Setup execution finished. Log file expected at: {final_log_file_path_obj}", flush=True)

if __name__ == "__main__":
    main()