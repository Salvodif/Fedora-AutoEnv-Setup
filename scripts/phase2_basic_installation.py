# In install.py
# ... (other imports)
from scripts import phase1_system_preparation
from scripts import phase2_basic_installation # New import
# ...

PHASES = {
    "phase1_system_preparation": {
        "name": "Phase 1: System Preparation",
        "description": "Initial system checks, DNS, DNF, RPMFusion, Flatpak, Hostname.",
        "dependencies": [],
        "handler": phase1_system_preparation.run_phase1
    },
    "phase2_basic_configuration": {
        "name": "Phase 2: Basic System Package Configuration",
        "description": "Install essential CLI tools, Python, Zsh, Media Codecs, etc.",
        "dependencies": ["phase1_system_preparation"], # Depends on Phase 1
        "handler": phase2_basic_installation.run_phase2 # Use the new handler
    },
    # ... altre fasi ...
}

# ... (resto di install.py) ...
# Assicurati che app_config sia passato all'handler:
# success = phase_to_run_info["handler"](app_config) # Già presente