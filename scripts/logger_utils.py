# Fedora-AutoEnv-Setup/scripts/logger_utils.py
import logging
import sys
from pathlib import Path
from typing import Optional

# Define the project root consistently.
# __file__ is .../Fedora-AutoEnv-Setup/scripts/logger_utils.py
# .resolve() makes it absolute.
# .parent is .../Fedora-AutoEnv-Setup/scripts/
# .parent.parent is .../Fedora-AutoEnv-Setup/
PROJECT_ROOT = Path(__file__).resolve().parent.parent 
LOG_FILENAME = "fedora_autoenv_setup.log" # Default log filename

def setup_logger(
    logger_name: str = "FedoraAutoEnvSetup", # Allow custom logger names if needed
    log_level: int = logging.INFO, # Overall minimum level for the logger and file handler
    log_to_file: bool = True,
    log_file_path: Optional[Path] = None, # Allow overriding the default log file path
    log_to_console: bool = False, # Default to False, as console_output.py handles most user messages
    console_log_level: int = logging.WARNING # If console logging via this logger is on, its level
) -> logging.Logger:
    """
    Configures and returns a logger instance.

    Args:
        logger_name (str): The name for the logger instance.
        log_level (int): The base logging level for the logger itself and the file handler.
                         Messages below this level will be ignored by both.
        log_to_file (bool): Whether to enable logging to a file.
        log_file_path (Optional[Path]): Absolute path to the log file. 
                                        If None and log_to_file is True, defaults to 
                                        PROJECT_ROOT / LOG_FILENAME.
        log_to_console (bool): Whether to enable logging to the console via this logger.
                               Generally False if console_output.py is primary for user messages.
        console_log_level (int): The logging level for the console handler (if enabled).
                                 Typically higher (e.g., WARNING) than file log_level.

    Returns:
        logging.Logger: The configured logger instance.
    """
    logger = logging.getLogger(logger_name)
    
    # Set the *absolute minimum* level this logger will process. 
    # Handlers can have higher levels, but not lower than this.
    logger.setLevel(log_level) 

    # Prevent adding multiple handlers if this function is called multiple times 
    # for the same logger name (e.g., in tests or if modules re-initialize it).
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s"
    )

    if log_to_file:
        if log_file_path is None:
            # Default log file path: <project_root>/fedora_autoenv_setup.log
            effective_log_file_path = PROJECT_ROOT / LOG_FILENAME
        else:
            effective_log_file_path = log_file_path
        
        # Ensure the directory for the log file exists
        try:
            effective_log_file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # Fallback: if we can't create the log directory (e.g. permissions),
            # print an error and disable file logging for this setup.
            # This should not use console_output.py to avoid circular dependencies
            # if console_output itself tries to use the logger.
            sys.stderr.write(f"ERROR [logger_utils]: Could not create log directory {effective_log_file_path.parent}. File logging disabled. Error: {e}\n")
            log_to_file = False # Disable file logging if dir creation fails

        if log_to_file: # Re-check as it might have been disabled
            file_handler = logging.FileHandler(effective_log_file_path, mode='a', encoding='utf-8')
            # File handler should log everything the logger is configured for (or more specific if desired)
            file_handler.setLevel(log_level) 
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            # Initial log message to confirm file logging is active
            # (only if logger is at INFO or lower, and this is an INFO message)
            if logger.isEnabledFor(logging.INFO):
                 logger.info(f"File logging initialized to: {effective_log_file_path}")


    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout) # Or sys.stderr for specific error streams
        # Console handler typically has a more restrictive level (e.g., WARNING, ERROR)
        console_handler.setLevel(console_log_level) 
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        if logger.isEnabledFor(logging.INFO): # Check against console_log_level effectively
             if console_log_level <= logging.INFO:
                logger.info("Console logging via Python 'logging' module is enabled.")
    
    # If no handlers are configured at all (e.g., both log_to_file and log_to_console are False),
    # add a NullHandler to prevent the "No handlers could be found for logger X" warning
    # that Python's logging module emits if a logger is used without any handlers.
    if not logger.hasHandlers():
        logger.addHandler(logging.NullHandler())
        # No need to log this, as it's a silent handler.
        # sys.stderr.write(f"INFO [logger_utils]: No file or console handlers configured for logger '{logger_name}'. Added NullHandler.\n")


    return logger

# Initialize a default application logger instance for easy import into other modules.
# This can be reconfigured by the main script (e.g., install.py) if needed
# by calling setup_logger() again with different parameters for the same logger name.
app_logger = setup_logger()
