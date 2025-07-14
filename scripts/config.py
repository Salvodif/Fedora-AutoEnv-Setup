# Fedora-AutoEnv-Setup/scripts/config.py

from pathlib import Path
import logging

# --- Constants ---
STATUS_FILE_NAME = "install_status.json"
CONFIG_FILE_NAME = "packages.json"

# Path to the status file (in the same directory as install.py)
STATUS_FILE_PATH = Path(__file__).parent.parent / STATUS_FILE_NAME

def setup_logger():
    """Sets up the application logger."""
    log_dir = Path.home() / ".config" / "fedora-autoenv-setup"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "fedora_autoenv_setup.log"

    logger = logging.getLogger("FedoraAutoEnvSetup")
    logger.setLevel(logging.DEBUG)

    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger

app_logger = setup_logger()

# --- Phases Configuration ---
# Import phase handlers here to avoid circular dependencies
from scripts.phases import system_preparation, basic_installation, gnome_configuration, nvidia_installation, additional_packages

PHASES = {
    "system_preparation": {
        "name": "Phase 1: System Preparation ⚙️",
        "description": "Initial system checks, DNF configuration, RPM Fusion, DNS, system update, Flathub, and hostname.",
        "dependencies": [],
        "handler": system_preparation.run
    },
    "basic_installation": {
        "name": "Phase 2: Basic System Package Configuration 📦",
        "description": "Install essential CLI tools, Python, Ghostty, media codecs, etc.",
        "dependencies": ["system_preparation"],
        "handler": basic_installation.run
    },
    "gnome_configuration": {
        "name": "Phase 4: GNOME Configuration & Extensions 🎨🖼️",
        "description": "Install GNOME Tweaks, Extension Manager, and configured extensions.",
        "dependencies": ["system_preparation", "basic_installation"],
        "handler": gnome_configuration.run
    },
    "nvidia_installation": {
        "name": "Phase 5: NVIDIA Driver Installation 🎮🖥️",
        "description": "Install NVIDIA proprietary or open kernel drivers. Requires compatible GPU and user confirmation.",
        "dependencies": ["system_preparation"],
        "handler": nvidia_installation.run
    },
    "additional_packages": {
        "name": "Phase 6: Additional User Packages 🧩🌐",
        "description": "Install user-selected applications from DNF and Flatpak.",
        "dependencies": ["system_preparation", "basic_installation"],
        "handler": additional_packages.run
    },
}
