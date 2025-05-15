# Fedora-AutoEnv-Setup/scripts/console_output.py

from typing import Any, Optional
from rich.console import Console
from rich.text import Text
from rich.style import Style
from rich.prompt import Prompt, Confirm, InvalidResponse
from rich.rule import Rule
from rich.padding import Padding
from rich.panel import Panel

# Initialize a global console object
console = Console(highlight=False) # highlight=False to prevent Rich from trying to auto-highlight

# --- Predefined Styles (can be expanded) ---
# We will mostly use markup, but styles can be useful for complex components
INFO_STYLE = Style(color="blue")
WARNING_STYLE = Style(color="yellow")
ERROR_STYLE = Style(color="red", bold=True)
SUCCESS_STYLE = Style(color="green")
STEP_STYLE = Style(color="cyan", bold=True)
SUB_STEP_STYLE = Style(color="bright_blue")
PROMPT_STYLE = Style(color="magenta")

# --- Output Functions ---

def print_info(message: Any, icon: bool = True):
    """Prints an informational message."""
    prefix = "[bold blue]ℹ️ INFO:[/] " if icon else ""
    console.print(f"{prefix}{message}")

def print_warning(message: Any, icon: bool = True):
    """Prints a warning message."""
    prefix = "[bold yellow]⚠️ WARNING:[/] " if icon else ""
    console.print(f"{prefix}{message}")

def print_error(message: Any, icon: bool = True, exit_after: bool = False, exit_code: int = 1):
    """Prints an error message. Optionally exits the program."""
    prefix = "[bold red]❌ ERROR:[/] " if icon else ""
    console.print(f"{prefix}[bold red]{message}[/]")
    if exit_after:
        sys.exit(exit_code) # Make sure to import sys if you use this in a script that needs it

def print_success(message: Any, icon: bool = True):
    """Prints a success message."""
    prefix = "[bold green]✅ SUCCESS:[/] " if icon else ""
    console.print(f"{prefix}{message}")

def print_step(title: str, char: str = "="):
    """Prints a major step title, underlined."""
    console.print(Rule(f"[bold magenta]{title}[/]", style="magenta", characters=char))

def print_sub_step(message: str, indent: int = 2):
    """Prints a sub-step message, slightly indented."""
    console.print(Padding(f"[bright_blue]❯[/] {message}", (0, 0, 0, indent)))

def print_panel(content: Any, title: Optional[str] = None, style: str = "blue", padding=(1,2)):
    """Prints content within a Rich panel."""
    console.print(Panel(content, title=title, border_style=style, padding=padding, expand=False))

def print_rule(title: Optional[str] = None, style: str = "dim white", char: str = "-"):
    """Prints a horizontal rule."""
    if title:
        console.print(Rule(f"[{style}]{title}[/]", style=style, characters=char))
    else:
        console.print(Rule(style=style, characters=char))

# --- Input Functions ---

def ask_question(prompt_message: str, default: Optional[str] = None, password: bool = False, choices: Optional[list[str]] = None) -> str:
    """
    Asks a question to the user and returns the answer.

    Args:
        prompt_message (str): The message to display for the prompt.
        default (Optional[str]): The default value if the user presses Enter.
        password (bool): If True, input will be hidden.
        choices (Optional[list[str]]): A list of valid choices.

    Returns:
        str: The user's input.
    """
    full_prompt = Text.assemble(
        (f"❓ {prompt_message}", PROMPT_STYLE),
    )
    return Prompt.ask(full_prompt, default=default, password=password, choices=choices)

def confirm_action(prompt_message: str, default: bool = False) -> bool:
    """
    Asks a yes/no confirmation question.

    Args:
        prompt_message (str): The confirmation message.
        default (bool): The default choice (True for yes, False for no).

    Returns:
        bool: True if the user confirms, False otherwise.
    """
    full_prompt = Text.assemble(
        (f"🤔 {prompt_message}", PROMPT_STYLE),
        (" (y/n)", "dim white")
    )
    return Confirm.ask(full_prompt, default=default)

