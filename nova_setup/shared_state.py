from pathlib import Path
from typing import Optional
import logging as std_logging

# These will be populated by install.py after rich is ensured and imported.
# This is a bit of a workaround for dynamic rich import.
# Modules importing shared_state will get these rich components.
# If a module is imported *before* install.py populates these, they will be None.
# install.py ensures they are populated before modules that use them heavily are called.
Console = None
Panel = None
Text = None
Confirm = None
Prompt = None
IntPrompt = None
RichHandler = None
Table = None
Padding = None

# Global application state
console: Optional[Console] = None
log: Optional[std_logging.Logger] = None

SCRIPT_DIR: Path = Path(".") # Will be updated by initialize_script_base_paths
TARGET_USER: str = ""
TARGET_USER_HOME: Path = Path(".")
LOG_FILE_PATH: Path = Path(".") # Will be updated by initialize_script_logging_and_user
IS_FEDORA: bool = False

# Configuration constants (can also be loaded from a config file in future)
ZSHRC_SOURCE_FILE_NAME: str = ".zshrc"
NANORC_SOURCE_FILE_NAME: str = ".nanorc"
ZSHRC_SUBDIRECTORY: str = "zsh"
NANORC_SUBDIRECTORY: str = "nano"
LOG_FILE_NAME: str = "nova_setup.log" # Base log file name

# Derived paths - will be set after SCRIPT_DIR is known
ZSHRC_SOURCE_PATH: Optional[Path] = None
NANORC_SOURCE_PATH: Optional[Path] = None

# Package lists
DNF_PACKAGES_BASE: list[str] = [
    "git", "curl", "cargo", "zsh",
    "python3", "python3-pip", "stow", "dnf-plugins-core", 
    "powerline-fonts", "btop", "bat", "fzf",
    "google-chrome-stable",
]

OMZ_PLUGINS: list[dict[str, str]] = [
    {"name": "zsh-autosuggestions", "url": "https://github.com/zsh-users/zsh-autosuggestions"},
    {"name": "zsh-syntax-highlighting", "url": "https://github.com/zsh-users/zsh-syntax-highlighting.git"},
    {"name": "you-should-use", "url": "https://github.com/MichaelAquilina/zsh-you-should-use.git"},
    {"name": "zsh-eza", "url": "https://github.com/z-shell/zsh-eza"},
    {"name": "fzf-tab", "url": "https://github.com/Aloxaf/fzf-tab"}
]

CARGO_TOOLS: list[str] = ["eza", "du-dust"]

SCRIPTED_TOOLS: list[dict[str, str]] = [
    {"name": "zoxide", "check_command": "zoxide --version", "url": "https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh", "method": "sh"},
    {"name": "atuin", "check_command": "atuin --version", "url": "https://setup.atuin.sh", "method": "bash"},
]

GNOME_EXTENSIONS_CONFIG: list[dict[str, str]] = [
    {"name": "User Themes", "uuid": "user-theme@gnome-shell-extensions.gcampax.github.com", "dnf_package": "gnome-shell-extension-user-themes"},
    {"name": "Blur My Shell", "uuid": "blur-my-shell@aunetx", "dnf_package": "gnome-shell-extension-blur-my-shell"},
    {"name": "Burn My Windows", "uuid": "burn-my-windows@schneegans.github.com", "dnf_package": "gnome-shell-extension-burn-my-windows"},
    {"name": "Vitals (System Monitor)", "uuid": "Vitals@CoreCoding.com", "dnf_package": "gnome-shell-extension-vitals"},
    {"name": "Caffeine", "uuid": "caffeine@patapon.info", "dnf_package": "gnome-shell-extension-caffeine"},
]

GNOME_MANAGEMENT_DNF_PACKAGES: list[str] = [
    "gnome-tweaks",
    "gnome-shell-extension-user-themes",
    "gnome-extensions-app",
    "extension-manager"
]

# To be populated by install.py after rich is verified and imported
# This allows other modules to use `from nova_setup.shared_state import Console, Panel, etc.`
def _set_rich_components(console_imp, panel_imp, text_imp, confirm_imp, prompt_imp, int_prompt_imp, rich_handler_imp, table_imp, padding_imp):
    global Console, Panel, Text, Confirm, Prompt, IntPrompt, RichHandler, Table, Padding
    Console, Panel, Text, Confirm, Prompt, IntPrompt, RichHandler, Table, Padding = \
        console_imp, panel_imp, text_imp, confirm_imp, prompt_imp, int_prompt_imp, rich_handler_imp, table_imp, padding_imp

# Helper to access Rich components if they were set
def get_rich_components():
    if not Console: # Check if a core component is None
        # This means install.py didn't call _set_rich_components yet, or rich failed.
        # This situation should ideally be avoided by careful import order in install.py.
        raise ImportError("Rich components not yet initialized in shared_state. Ensure install.py populates them before use.")
    return Console, Panel, Text, Confirm, Prompt, IntPrompt, RichHandler, Table, Padding