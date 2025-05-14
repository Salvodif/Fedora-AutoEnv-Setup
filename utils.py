# utils.py
import subprocess
import logging
from myrich import console, print_info, print_error # Assuming myrich is in the same path

def run_command(command: list[str],
                check: bool = True,
                capture_output: bool = False,
                text: bool = True, # Changed default to True for text mode
                shell: bool = False, # Add shell=True option if needed for specific commands
                cwd: str = None): # Add current working directory option
    """
    Helper function to run a shell command.
    Logs errors to the logging system and prints to Rich console.
    """
    command_str = ' '.join(command) if isinstance(command, list) else command
    print_info(f"Executing: {command_str}")
    try:
        process = subprocess.run(
            command,
            check=check,
            capture_output=capture_output,
            text=text,
            shell=shell,
            cwd=cwd
        )
        if capture_output:
            # Log stdout/stderr only if there's significant output or for debugging
            # For successful commands, often stdout is not needed in the main log
            # but can be useful for the user to see via Rich.
            if process.stdout and len(process.stdout.strip()) > 0 :
                console.print(f"[dim cyan]Output:\n{process.stdout.strip()}[/dim cyan]")
            if process.stderr and len(process.stderr.strip()) > 0:
                 # stderr might contain warnings even on success
                console.print(f"[dim yellow]Stderr:\n{process.stderr.strip()}[/dim yellow]")

            return process.stdout, process.stderr, process.returncode
        return True # Or process.returncode for more detailed success/failure
    except subprocess.CalledProcessError as e:
        error_message = f"Command '{command_str}' failed with return code {e.returncode}."
        stderr_output = e.stderr.strip() if e.stderr else ""
        stdout_output = e.stdout.strip() if e.stdout else ""

        if stderr_output:
            error_message += f"\nStderr: {stderr_output}"
            print_error(f"Stderr: {stderr_output}")
        if stdout_output and not stderr_output: # Sometimes errors go to stdout
             error_message += f"\nStdout: {stdout_output}"
             print_error(f"Stdout: {stdout_output}")

        print_error(f"Command '{command_str}' failed.")
        logging.error(error_message)
        if capture_output:
            return e.stdout, e.stderr, e.returncode
        return False # Or e.returncode
    except FileNotFoundError:
        error_message = f"Command not found: {command[0] if isinstance(command, list) else command.split()[0]}. Is it installed and in PATH?"
        print_error(error_message)
        logging.error(error_message)
        if capture_output:
            return None, "FileNotFoundError", 1 # Simulate a failure structure
        return False
    except Exception as e:
        error_message = f"An unexpected error occurred while running '{command_str}': {e}"
        print_error(error_message)
        logging.error(error_message, exc_info=True)
        if capture_output:
            return None, str(e), 1
        return False