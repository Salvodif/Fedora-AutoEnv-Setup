import sys
import shlex
import shutil
import subprocess # For direct calls if system_utils.run_command isn't suitable for a specific case
from pathlib import Path
from typing import Dict, Any # Changed from List, Dict, Any to just Dict, Any as per phase6

# Adjust import path for shared modules, assuming this script is in Fedora-AutoEnv-Setup/scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from scripts import console_output as con
    from scripts import system_utils
    from scripts.logger_utils import app_logger
except ImportError as e:
    # Fallback for direct execution or if path adjustment is not perfect
    print(f"Error importing shared modules: {e}. Ensure PYTHONPATH is set correctly or script is run from project root.")
    # Define dummy logger/console functions if needed for basic operation or to highlight the error
    class DummyLogger:
        def info(self, msg): print(f"INFO: {msg}")
        def error(self, msg, exc_info=None): print(f"ERROR: {msg}")
        def warning(self, msg): print(f"WARNING: {msg}")
        def debug(self, msg): print(f"DEBUG: {msg}")
    app_logger = DummyLogger()

    class DummyConsole:
        def print_step(self, msg): print(f"STEP: {msg}")
        def print_sub_step(self, msg): print(f"SUB_STEP: {msg}")
        def print_info(self, msg): print(f"INFO: {msg}")
        def print_success(self, msg): print(f"SUCCESS: {msg}")
        def print_warning(self, msg): print(f"WARNING: {msg}")
        def print_error(self, msg): print(f"ERROR: {msg}")
    con = DummyConsole()
    # It's often better to re-raise or exit if core components can't be imported
    # For now, this allows the script structure to be laid out.
    # Consider exiting if these are critical: sys.exit(1) 

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
