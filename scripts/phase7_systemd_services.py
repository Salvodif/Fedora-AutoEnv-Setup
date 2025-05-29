import sys
import shlex
import shutil
import subprocess # For direct calls if system_utils.run_command isn't suitable for a specific case
from pathlib import Path
from typing import Dict, Any # Changed from List, Dict, Any to just Dict, Any as per phase6

# Adjust import path for shared modules, assuming this script is in Fedora-AutoEnv-Setup/scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent)) # Make sure this is correctly placed before this block

app_logger = None # Initialize to None
con = None        # Initialize to None

try:
    from scripts.logger_utils import app_logger # Attempt to import app_logger first
except ImportError as e_logger:
    # app_logger is NOT available if this block is hit.
    # Log this specific failure using a basic print to stderr, as neither con nor app_logger is guaranteed yet.
    print(f"CRITICAL ERROR in {Path(__file__).name}: Failed to import 'app_logger' from 'scripts.logger_utils'. Details: {e_logger}. File logging will be unavailable.", file=sys.stderr)
    # app_logger remains None. We don't exit yet; 'con' might still import and provide better user feedback.
except Exception as e_logger_other: # Catch any other unexpected error during app_logger import
    print(f"UNEXPECTED CRITICAL ERROR in {Path(__file__).name} during import of 'app_logger': {e_logger_other}. File logging will be unavailable.", file=sys.stderr)


try:
    from scripts import console_output as con # Attempt to import con
except ImportError as e_console:
    # con is NOT available if this block is hit.
    # If app_logger IS available (i.e., its import succeeded and it's not None), use it to log this failure.
    if app_logger: # Check if app_logger was successfully imported
        app_logger.critical(f"CRITICAL: Failed to import 'console_output as con'. Details: {e_console}. Essential console output is unavailable. Script cannot continue.", exc_info=True)
    else:
        # Neither app_logger nor con is available. This is the last resort print.
        print(f"CRITICAL ERROR in {Path(__file__).name}: Failed to import 'console_output as con'. Details: {e_console}. Neither logger nor console utilities are available. Script cannot continue.", file=sys.stderr)
    
    # Since console output (con) is critical for user interaction and feedback, exit if it fails to load.
    sys.exit(1) # Exit directly, as con is not available to call con.print_error(..., exit_after=True)
except Exception as e_console_other: # Catch any other unexpected error during con import
    if app_logger:
        app_logger.critical(f"UNEXPECTED CRITICAL ERROR in {Path(__file__).name} during import of 'console_output as con': {e_console_other}. Script cannot continue.", exc_info=True)
    else:
        print(f"UNEXPECTED CRITICAL ERROR in {Path(__file__).name} during import of 'console_output as con': {e_console_other}. Script cannot continue.", file=sys.stderr)
    sys.exit(1)


# --- At this point, 'con' MUST be available, or the script would have exited. ---

# Check if app_logger failed to import (it would still be None). 
# If so, use 'con' (which is now guaranteed to be available) to report this.
if app_logger is None:
    # This message indicates that the earlier print to stderr about app_logger import failure occurred.
    # con.print_error will provide a more user-friendly and consistently styled message.
    con.print_error(
        f"Logger utility ('app_logger' in {Path(__file__).name}) failed to initialize due to an import error. "
        "Logging to file will not function. Please review console error messages above for specific details."
    )
    # Optional: Exit if file logging is absolutely critical
    # con.print_error("Exiting because file logging is a critical requirement.", exit_after=True)

# --- The rest of the script (run_phase7 function, etc.) follows below ---
# Ensure that all uses of app_logger in the rest of the script are conditional, e.g.:
# if app_logger:
#     app_logger.info("This is a log message.")
# Or, implement a fallback mechanism if app_logger is None.

# Placeholder for the main function for this phase
def run_phase7(app_config: Dict[str, Any]) -> bool:
    """Executes Phase 7: Systemd Services Deployment."""
    app_logger.info("Starting Phase 7: Systemd Services Deployment.")
    con.print_step("PHASE 7: Systemd Services Deployment")
    overall_success = True

    # --- File Deployment Logic START ---
    con.print_sub_step("Deploying systemd and script files...")

    try:
        source_dir = Path(__file__).resolve().parent.parent / "systemd_scripts"
        if not source_dir.is_dir():
            app_logger.error(f"Source directory '{source_dir}' not found. Cannot deploy files.")
            con.print_error(f"Critical error: Source directory '{source_dir}' not found. Skipping Phase 7 file deployment.")
            # overall_success is already True, so we need to set it to False here
            overall_success = False 
            # Then, skip the rest of the file deployment and systemd logic.
            # This requires jumping to the end of the function, past systemd steps.
            # For simplicity in this subtask, we'll let it fall through, 
            # but the 'if overall_success:' checks below will prevent further action.
            # A more robust solution might involve a dedicated 'return False' here.


        if overall_success: # Proceed only if source_dir was found
            target_script_dir = Path.home() / "scripts"
            target_systemd_dir = Path.home() / ".config" / "systemd" / "user"

            # Files to deploy: (source_filename, target_dir, is_executable)
            files_to_deploy = [
                ("kdrive-backup.zsh", target_script_dir, True),
                ("rsync-backup.service", target_systemd_dir, False),
                ("rsync-backup.timer", target_systemd_dir, False),
            ]

            # Create target directories
            for target_dir in {target_script_dir, target_systemd_dir}:
                app_logger.info(f"Ensuring target directory exists: {target_dir}")
                # Assuming system_utils.create_directory_if_not_exists handles errors internally
                # or returns False on failure. If it raises an exception, this try-except
                # block for the whole deployment section will catch it.
                # For this subtask, we'll use Path.mkdir directly with logging.
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    con.print_info(f"Directory ensured: {target_dir}")
                except OSError as e:
                    app_logger.error(f"Failed to create directory {target_dir}: {e}", exc_info=True)
                    con.print_error(f"Could not create directory {target_dir}. Error: {e}")
                    overall_success = False
                    break # Stop if a directory can't be created
            
            if not overall_success: # If directory creation failed
                 # Jump to the end of function for final status report
                 pass # Let it fall through to the final status report block

            if overall_success: # Proceed if directories are okay
                for filename, target_dir, is_executable in files_to_deploy:
                    source_file = source_dir / filename
                    target_file = target_dir / filename

                    if not source_file.is_file():
                        app_logger.error(f"Source file not found: {source_file}")
                        con.print_error(f"Missing source file: {source_file}. Cannot deploy.")
                        overall_success = False
                        continue # Skip this file

                    app_logger.info(f"Deploying {filename} to {target_file}...")
                    con.print_info(f"Copying {filename} to {target_file}...")
                    try:
                        shutil.copy2(source_file, target_file)
                        app_logger.info(f"Successfully copied {filename} to {target_file}.")
                        con.print_success(f"Copied {filename} to {target_file}.")

                        if is_executable:
                            app_logger.info(f"Making {target_file} executable...")
                            # Use shlex.quote for safety if filename could have spaces/special chars
                            chmod_command = f"chmod +x {shlex.quote(str(target_file))}"
                            # Assuming system_utils.run_command exists and is robust.
                            # For this subtask, let's use subprocess directly to show the principle
                            # if system_utils.run_command wasn't fully specified for its return.
                            process_result = subprocess.run(chmod_command, shell=True, capture_output=True, text=True, check=False)
                            if process_result.returncode == 0:
                                app_logger.info(f"Successfully made {target_file} executable.")
                                con.print_success(f"Made {target_file} executable.")
                            else:
                                app_logger.error(f"Failed to make {target_file} executable. Error: {process_result.stderr}")
                                con.print_error(f"chmod +x {target_file} failed: {process_result.stderr}")
                                overall_success = False
                    
                    except FileNotFoundError:
                        app_logger.error(f"Error: Source file {source_file} not found during copy.", exc_info=True)
                        con.print_error(f"Error copying {filename}: source file not found.")
                        overall_success = False
                    except Exception as e:
                        app_logger.error(f"Failed to deploy {filename} to {target_file}: {e}", exc_info=True)
                        con.print_error(f"Error copying {filename}: {e}")
                        overall_success = False
    
    except Exception as e:
        app_logger.error(f"An unexpected error occurred during file deployment: {e}", exc_info=True)
        con.print_error(f"An unexpected error in file deployment: {e}")
        overall_success = False

    # --- File Deployment Logic END ---

    # --- Systemd Enabling Logic START ---
    if overall_success: # Only proceed if file deployment was successful
        con.print_sub_step("Enabling systemd services...")
        
        try:
            # Reload systemd daemon
            con.print_info("Reloading systemd user daemon...")
            app_logger.info("Executing: systemctl --user daemon-reload")
            # Assuming system_utils.run_command returns an object with a 'returncode' attribute
            # and logs its own execution details if print_fn_info is provided.
            # If check=True is supported and raises an error, the try-except will catch it.
            # For this task, we'll follow the plan's specification of check=False and inspect returncode.
            reload_result = system_utils.run_command(
                "systemctl --user daemon-reload",
                logger=app_logger,
                print_fn_info=None, # To avoid double printing if run_command also prints
                print_fn_error=con.print_error, # For run_command internal errors
                shell=True, # systemctl might be better run via shell depending on setup
                check=False # We will check returncode manually
            )

            if reload_result.returncode == 0:
                app_logger.info("systemctl daemon-reload completed successfully.")
                con.print_success("Systemd user daemon reloaded successfully.")
            else:
                app_logger.error(f"systemctl daemon-reload failed. RC: {reload_result.returncode}, Stderr: {reload_result.stderr}")
                con.print_error(f"Failed to reload systemd user daemon. Return code: {reload_result.returncode}")
                overall_success = False

            # Enable and start the timer, only if daemon-reload was successful
            if overall_success:
                con.print_info("Enabling and starting rsync-backup.timer...")
                app_logger.info("Executing: systemctl --user enable --now rsync-backup.timer")
                enable_result = system_utils.run_command(
                    "systemctl --user enable --now rsync-backup.timer",
                    logger=app_logger,
                    print_fn_info=None,
                    print_fn_error=con.print_error,
                    shell=True,
                    check=False
                )

                if enable_result.returncode == 0:
                    app_logger.info("systemctl enable --now rsync-backup.timer completed successfully.")
                    con.print_success("rsync-backup.timer enabled and started successfully.")
                else:
                    app_logger.error(f"systemctl enable --now rsync-backup.timer failed. RC: {enable_result.returncode}, Stderr: {enable_result.stderr}")
                    con.print_error(f"Failed to enable/start rsync-backup.timer. Return code: {enable_result.returncode}")
                    overall_success = False
        
        except Exception as e:
            app_logger.error(f"An unexpected error occurred during systemd operations: {e}", exc_info=True)
            con.print_error(f"An unexpected error in systemd operations: {e}")
            overall_success = False

    # --- Systemd Enabling Logic END ---

    if overall_success:
        app_logger.info("Phase 7: Systemd Services Deployment completed successfully.")
        con.print_success("Phase 7: Systemd Services Deployment completed successfully.")
    else:
        app_logger.error("Phase 7: Systemd Services Deployment encountered errors.")
        con.print_error("Phase 7: Systemd Services Deployment completed with errors. Please review logs.")
        
    return overall_success
