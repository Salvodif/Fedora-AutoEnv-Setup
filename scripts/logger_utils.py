# Fedora-AutoEnv-Setup/scripts/logger_utils.py
import logging
import sys
from pathlib import Path

LOG_FILENAME = "fedora_autoenv_setup.log"
PROJECT_ROOT = Path(__file__).resolve().parent.parent # Fedora-AutoEnv-Setup/

def setup_logger(
    log_level=logging.INFO,
    log_to_file=True,
    log_file_path=None,
    log_to_console=False, # Set to False if console_output.py handles most user-facing console messages
    console_log_level=logging.WARNING # Only show warnings and above on console via this logger
):
    """
    Configures and returns a logger instance.
    """
    logger = logging.getLogger("FedoraAutoEnvSetup")
    logger.setLevel(log_level) # Set the base level for the logger

    # Prevent adding multiple handlers if called multiple times (e.g., in tests or reloads)
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s"
    )

    if log_to_file:
        if log_file_path is None:
            log_file_path = PROJECT_ROOT / LOG_FILENAME
        
        file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
        file_handler.setLevel(log_level) # Log all levels (from logger's base) to file
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout) # Or sys.stderr for errors
        console_handler.setLevel(console_log_level) # More restrictive level for console
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # If no handlers are configured (e.g., both log_to_file and log_to_console are False),
    # add a NullHandler to prevent "No handlers could be found" warnings.
    if not logger.hasHandlers():
        logger.addHandler(logging.NullHandler())

    return logger

# Initialize a default logger instance for easy import
# You can reconfigure it in install.py if needed
app_logger = setup_logger()

# Example usage in other modules:
# from scripts.logger_utils import app_logger
# app_logger.info("This is an info message.")
# app_logger.error("This is an error message.")