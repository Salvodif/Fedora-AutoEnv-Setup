# Fedora-AutoEnv-Setup/scripts/console_output.py

import sys # Needed for sys.exit in print_error
from typing import Any, Optional, List # Added List for ask_question choices
from rich.console import Console
from rich.text import Text
from rich.style import Style
from rich.prompt import Prompt, Confirm # InvalidResponse is not directly used but good to know it exists
from rich.rule import Rule
from rich.padding import Padding
from rich.panel import Panel

# Initialize a global console object
# highlight=False to prevent Rich from trying to auto-highlight based on syntax.
# We use explicit markup for styling.
console = Console(highlight=False) 

# --- Predefined Styles (can be expanded, but markup is often more flexible) ---
# These are less used now that markup like "[bold red]...[/]" is preferred directly in messages.
# However, they can be useful for Rich components that accept a Style object.
INFO_STYLE = Style(color="blue")
WARNING_STYLE = Style(color="yellow")
ERROR_STYLE = Style(color="red", bold=True)
SUCCESS_STYLE = Style(color="green")
STEP_STYLE = Style(color="cyan", bold=True) # Often used with Rule characters too
SUB_STEP_STYLE = Style(color="bright_blue") # For messages like "❯ Sub-step details"
PROMPT_STYLE = Style(color="magenta") # For question prompts

# --- Output Functions ---

def print_info(message: Any, icon: bool = True):
    """Prints an informational message using Rich markup."""
    prefix = "[bold blue]ℹ️ INFO:[/] " if icon else ""
    console.print(f"{prefix}{message}")

def print_warning(message: Any, icon: bool = True):
    """Prints a warning message using Rich markup."""
    prefix = "[bold yellow]⚠️ WARNING:[/] " if icon else ""
    console.print(f"{prefix}{message}")

def print_error(
    message: Any, 
    icon: bool = True, 
    exit_after: bool = False, 
    exit_code: int = 1
):
    """
    Prints an error message using Rich markup. 
    Optionally exits the program with the given exit_code.
    """
    prefix = "[bold red]❌ ERROR:[/] " if icon else ""
    # Ensure the message itself is also styled if it's not already markup
    # However, callers usually provide markup: print_error(f"[bold red]{specific_error}[/]")
    # If message is plain string, let Rich style it with the prefix.
    # Forcing extra [bold red] around message might double-style if message is already markup.
    # The current approach relies on the prefix for the primary error styling.
    console.print(f"{prefix}[bold red]{message}[/]") # Ensure message part is also red and bold
    if exit_after:
        console.print(f"[dim red]Exiting with code {exit_code}...[/]")
        sys.exit(exit_code)

def print_success(message: Any, icon: bool = True):
    """Prints a success message using Rich markup."""
    prefix = "[bold green]✅ SUCCESS:[/] " if icon else ""
    console.print(f"{prefix}{message}")

def print_step(title: str, char: str = "="):
    """
    Prints a major step title, styled as a Rich Rule.
    Example: print_step("PHASE 1: System Preparation")
    """
    # Magenta is a common color for major steps/phases
    console.print(Rule(f"[bold magenta]{title}[/]", style="magenta", characters=char))

def print_sub_step(message: str, indent: int = 2):
    """
    Prints a sub-step message, slightly indented, with a leading marker.
    Example: print_sub_step("Configuring DNF performance...")
    """
    # Using Padding to achieve indentation. (top, right, bottom, left)
    console.print(Padding(f"[bright_blue]❯[/] {message}", (0, 0, 0, indent)))

def print_panel(
    content: Any, 
    title: Optional[str] = None, 
    style: str = "blue", # Border style
    padding: tuple = (1,2) # (vertical, horizontal) padding inside panel
):
    """
    Prints content within a Rich Panel.
    Content can be simple text or other Rich renderables.
    """
    console.print(
        Panel(
            content, 
            title=f"[bold]{title}[/]" if title else None, 
            border_style=style, 
            padding=padding, 
            expand=False # expand=False makes panel fit content
        )
    )

def print_rule(title: Optional[str] = None, style: str = "dim white", char: str = "-"):
    """
    Prints a horizontal rule, optionally with a title.
    Useful for visually separating sections of output.
    """
    if title:
        # Style the title within the rule if provided
        console.print(Rule(Text(title, style=style), style=style, characters=char))
    else:
        console.print(Rule(style=style, characters=char))

# --- Input Functions ---

def ask_question(
    prompt_message: str, 
    default: Optional[str] = None, 
    password: bool = False, 
    choices: Optional[List[str]] = None # List of allowed string choices
) -> str:
    """
    Asks a question to the user and returns the answer.
    Uses Rich Prompt for better user experience.

    Args:
        prompt_message (str): The message to display for the prompt.
        default (Optional[str]): The default value if the user presses Enter.
        password (bool): If True, input will be hidden (for passwords).
        choices (Optional[List[str]]): A list of valid string choices. If provided,
                                       input is restricted to these choices.

    Returns:
        str: The user's input.
    """
    # Assemble a Rich Text object for the prompt for consistent styling
    # Using a leading icon for prompts
    rich_prompt = Text.assemble(
        ("❓ ", "default"), # Default style for icon, or specific style if desired
        (f"{prompt_message}", PROMPT_STYLE),
    )
    
    # Prompt.ask handles default, password, and choices internally
    user_input = Prompt.ask(
        rich_prompt, 
        default=default, 
        password=password, 
        choices=choices
        # Rich handles InvalidResponse internally if choices are provided
    )
    return user_input

def confirm_action(prompt_message: str, default: bool = False) -> bool:
    """
    Asks a yes/no confirmation question.
    Uses Rich Confirm for y/n style prompts.

    Args:
        prompt_message (str): The confirmation message.
        default (bool): The default choice (True for yes, False for no).

    Returns:
        bool: True if the user confirms (yes), False otherwise (no).
    """
    # Assemble a Rich Text object for the prompt
    # Using a leading icon for confirmations
    rich_prompt = Text.assemble(
        ("🤔 ", "default"), 
        (f"{prompt_message}", PROMPT_STYLE),
        (" (y/n)", "dim white") # Hint for y/n
    )
    
    # Confirm.ask handles the y/n logic and default value
    confirmation = Confirm.ask(rich_prompt, default=default)
    return confirmation

# Example Usage (can be run if this file is executed directly)
if __name__ == "__main__":
    print_step("Demonstrating Console Output Utilities")

    print_info("This is an informational message.")
    print_info("This is an info message without an icon.", icon=False)
    print_warning("This is a warning message.")
    print_success("This is a success message!")
    
    print_rule("Sub-steps and Panels")
    print_sub_step("This is the first sub-step.")
    print_sub_step("This is another sub-step, indented further.", indent=4)
    
    panel_content = Text.assemble(
        ("This is some content inside a panel.\n", "default"),
        ("It can have multiple lines and [bold green]styles[/].", "default")
    )
    print_panel(panel_content, title="Important Notice", style="yellow", padding=(1,1))

    print_rule("User Input")
    try:
        name = ask_question("What is your name?", default="User")
        print_info(f"Hello, {name}!")

        age = ask_question("What is your age (e.g., 1, 2, 3)?", choices=["1", "2", "3", "4", "5", "more"]) # Example with choices
        print_info(f"You selected age: {age}")

        # Password input will be hidden
        # secret = ask_question("Enter a secret password:", password=True)
        # if secret:
        #     print_info("Password received (not shown).")
        # else:
        #     print_warning("No password entered.")

        if confirm_action("Do you want to proceed with an example action?", default=True):
            print_success("User confirmed the action.")
        else:
            print_warning("User cancelled the action.")

        if confirm_action("Is this script helpful?", default=False):
            print_info("Glad to hear it!")
        else:
            print_info("Okay, noted.")
            
        # Example of an error that exits
        # print_error("This is a critical error, and the script will now exit.", exit_after=True, exit_code=5)
        # print_info("This line will not be reached if exit_after=True above.")

    except Exception as e:
        # This catch is for the __main__ example itself, not a general pattern for script errors
        print_error(f"An error occurred during the example: {e}")

    print_step("End of Demonstration")