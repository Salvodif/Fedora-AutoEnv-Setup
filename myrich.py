# fedora_config_app/myrich.py
# English: This file handles Rich text output for the terminal.

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.prompt import Prompt, Confirm

# Initialize a global console object
console = Console()

def print_header(title: str):
    """
    Prints a styled header.
    Args:
        title (str): The text for the header.
    """
    console.print(Rule(f"[bold cyan]{title}[/bold cyan]", style="cyan"))
    console.line()

def print_message(message: str, style: str = "info"):
    """
    Prints a styled message.
    Args:
        message (str): The message to print.
        style (str): The style of the message.
                     Can be "info", "success", "warning", "error".
    """
    prefix_map = {
        "info": "[bold blue][INFO][/bold blue]",
        "success": "[bold green][SUCCESS][/bold green]",
        "warning": "[bold yellow][WARNING][/bold yellow]",
        "error": "[bold red][ERROR][/bold red]",
    }
    prefix = prefix_map.get(style.lower(), "[INFO]")
    console.print(f"{prefix} {message}")

def print_panel(content: str, title: str = "Output", border_style: str = "green"):
    """
    Prints content within a styled panel.
    Args:
        content (str): The main content for the panel.
        title (str): Optional title for the panel.
        border_style (str): Style for the panel's border.
    """
    console.print(Panel(Text(content, justify="left"), title=title, border_style=border_style, expand=False))

def ask_question(prompt_text: str, choices: list = None, default=None) -> str:
    """
    Asks a question to the user with optional choices.
    Args:
        prompt_text (str): The question to ask.
        choices (list, optional): A list of valid choices. Defaults to None.
        default (any, optional): Default value if user presses Enter. Defaults to None.
    Returns:
        str: The user's answer.
    """
    return Prompt.ask(prompt_text, choices=choices, default=default)

def confirm_action(prompt_text: str, default: bool = False) -> bool:
    """
    Asks a yes/no confirmation question.
    Args:
        prompt_text (str): The confirmation question.
        default (bool): Default answer (True for yes, False for no).
    Returns:
        bool: True if user confirms, False otherwise.
    """
    return Confirm.ask(prompt_text, default=default)

if __name__ == "__main__":
    # Example usage
    print_header("My Rich Test")
    print_message("This is an informational message.")
    print_message("This is a success message.", style="success")
    print_message("This is a warning.", style="warning")
    print_message("This is an error!", style="error")
    print_panel("Some important content here.\nWith multiple lines.", title="Important Info")
    
    # name = ask_question("What is your name?", default="User")
    # print_message(f"Hello, {name}!", style="success")

    # proceed = confirm_action("Do you want to proceed?", default=True)
    # if proceed:
    #     print_message("Proceeding...", style="info")
    # else:
    #     print_message("Aborting.", style="warning")