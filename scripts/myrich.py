# myrich.py
from rich.console import Console
from rich.theme import Theme
from rich.text import Text

# Custom theme (optional, but can make things prettier)
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "error": "bold red",
    "success": "green",
    "highlight": "bold blue"
})

console = Console(theme=custom_theme)

def print_info(message: str):
    """Prints an informational message."""
    console.print(f"[info]INFO:[/] {message}")

def print_warning(message: str):
    """Prints a warning message."""
    console.print(f"[warning]WARNING:[/] {message}")

def print_error(message: str):
    """Prints an error message."""
    console.print(f"[error]ERROR:[/] {message}")

def print_success(message: str):
    """Prints a success message."""
    console.print(f"[success]SUCCESS:[/] {message}")

def print_step(step_number: int, description: str):
    """Prints a formatted step."""
    console.print(f"\n[highlight]Step {step_number}: {description}[/]")

def print_header(title: str):
    """Prints a prominent header."""
    console.rule(f"[bold white on blue] {title} [/]", style="blue")
    console.print() # Add a blank line after the header

def print_with_emoji(emoji: str, message: str, style: str = ""):
    """Prints a message prefixed with an emoji."""
    if style:
        console.print(f"{emoji} [{style}]{message}[/]")
    else:
        console.print(f"{emoji} {message}")

if __name__ == '__main__':
    # Example usage (for testing myrich.py directly)
    print_header("Rich Utilities Test")
    print_info("This is an information message.")
    print_warning("This is a warning message.")
    print_error("This is an error message.")
    print_success("This operation was successful.")
    print_step(1, "Initialize something.")
    print_with_emoji("🚀", "Launching the rocket!", "highlight")
    print_with_emoji("✅", "Task completed.", "success")