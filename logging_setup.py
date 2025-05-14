# fedora_config_app/logging_setup.py
# English: This file configures the logging for the application.

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_FILE_NAME = "fedora_config_app.log"
LOG_DIR = "logs" # Optional: place logs in a subdirectory

def setup_logging(log_level=logging.INFO) -> logging.Logger:
    """
    Configures and returns a logger instance.
    Logs will be written to a file and also printed to the console for ERROR and CRITICAL.
    """
    # Create log directory if it doesn't exist
    if not os.path.exists(LOG_DIR):
        try:
            os.makedirs(LOG_DIR)
        except OSError as e:
            print(f"Error creating log directory {LOG_DIR}: {e}")
            # Fallback to current directory if subdir creation fails
            log_file_path = LOG_FILE_NAME
    else:
        log_file_path = os.path.join(LOG_DIR, LOG_FILE_NAME)
    
    if not os.path.exists(LOG_DIR): # If log dir still doesn't exist after attempt
        log_file_path = LOG_FILE_NAME


    # Get the root logger
    logger = logging.getLogger("FedoraConfigApp")
    logger.setLevel(log_level)

    # Prevent multiple handlers if called multiple times (e.g., in testing)
    if logger.hasHandlers():
        logger.handlers.clear()

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
    )

    # File Handler - for writing logs to a file
    # Rotates logs: 1MB per file, keeping 5 backup files
    try:
        file_handler = RotatingFileHandler(log_file_path, maxBytes=1*1024*1024, backupCount=5)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level) # Log everything from INFO upwards to file
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Error setting up file handler for logging: {e}")
        # This is critical, if logging to file fails, we should know.

    # Console Handler - for printing critical messages to console
    # This could be redundant if Rich is used for all user-facing messages,
    # but good for catching early configuration errors or if Rich isn't available.
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING) # Only show warnings and above on console via logging
    logger.addHandler(console_handler)
    
    logger.info("Logging setup complete. Logging to %s", log_file_path)
    return logger

# Global logger instance, configured on first import
# This way, other modules can just `from logging_setup import logger`
logger = setup_logging()

if __name__ == "__main__":
    # Example usage of the logger
    logger.debug("This is a debug message (won't show by default).")
    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.critical("This is a critical message.")