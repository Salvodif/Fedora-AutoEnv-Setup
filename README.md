# Fedora AutoEnv Setup 🚀✨

`Fedora-AutoEnv-Setup` is a Python-based automation tool designed to streamline the post-installation setup and configuration of a Fedora Linux environment. It empowers users to define and execute a series of setup phases, installing packages, configuring system settings, and setting up user-specific enhancements in an orderly, repeatable, and customizable manner.

## 🌟 Features

*   **🧩 Phased Setup:** Organizes complex setup tasks into distinct, manageable, and logical phases.
*   **⚙️ Configuration-Driven:** Utilizes a central `packages.json` file to define packages, commands, and specific settings for each phase, making customization straightforward.
*   **🔗 Dependency Management:** Intelligently ensures phases are run in the correct order by respecting defined inter-dependencies.
*   **💾 Status Tracking:** Remembers the completion status of each phase in an `install_status.json` file, allowing users to easily resume or re-run specific parts of the setup.
*   **🖥️ User-Friendly CLI:** Provides a clear, interactive command-line menu (via `install.py`) for selecting and executing setup phases.
*   **🎨 Rich Console Output:** Leverages the `rich` library for beautifully clear and styled terminal output, making it easy to distinguish between informational messages ℹ️, warnings ⚠️, and errors ❌.
*   **👤 User-Specific Configuration:** Adeptly handles tasks like setting the default shell (e.g., Zsh) and copying personalized dotfiles for the target user, correctly identified via `SUDO_USER`.
*   **🧱 Modular Scripting:** Each phase's core logic is neatly encapsulated in its own Python script within the `scripts/` directory, promoting maintainability and extensibility.

## 📂 Project Structure
```
Fedora-AutoEnv-Setup/
├── 🚀 install.py # Main entry point script for the user
├── 📄 packages.json # Main configuration file for all phases
├── 💾 install_status.json # (Generated) Tracks completion status of phases
├── 📁 nano/ # Directory for nano configuration files
│ └── .nanorc # Example: your custom nanorc
├── 📁 zsh/ # Directory for Zsh configuration files
│ └── .zshrc # Example: your custom zshrc
├── 📁 scripts/ # Contains scripts for individual phases and utilities
│ ├── 🛠️ config_loader.py # Utility to load packages.json
│ ├── ✨ console_output.py # Utility for styled terminal output using Rich
│ ├── ⚙️ system_utils.py # Utility for running system commands
│ ├── 1️⃣ phase1_system_preparation.py # Logic for Phase 1
│ ├── 2️⃣ phase2_basic_installation.py # Logic for Phase 2
│ ├── 3️⃣ phase3_terminal_enhancement.py # Logic for Phase 3
│ └── ... # (Other phase scripts as developed)
└── 📖 README.md # This file (You are here!)
```

## ✅ Prerequisites

*   **OS:** Fedora Linux 🐧 (This tool is tailored for Fedora).
*   **Python:** Python 3.6+ 🐍.
*   **Python Packages:**
    *   `PyYAML`: For parsing the `packages.json` configuration file.
    *   `rich`: For the enhanced and colorful console output.
    Install them easily using `pip`:
    ```bash
    sudo pip3 install PyYAML rich
    ```
    Alternatively, for a user-local installation (ensure `~/.local/bin` is in your `PATH`):
    ```bash
    pip3 install --user PyYAML rich
    ```
*   **🔑 Sudo Privileges:** The main `install.py` script **must** be run with `sudo`. Many operations (package installation, system-wide configuration changes, modifying user shells) require root access.

## 🔧 Configuration (`packages.json`)

The `packages.json` file is the heart ❤️ of `Fedora-AutoEnv-Setup`. This YAML file dictates precisely what actions are performed in each setup phase.

**Example Snippet:**
```yaml
# --- Phase 1: System Preparation ---
phase1_system_preparation:
  dnf_packages:
    - "dnf5"
    - "dnf5-plugins"

# --- Phase 2: Basic System Package Configuration ---
phase2_basic_configuration:
  dnf_packages:
    - "git"
    - "curl"
    - "zsh"
  # ... other package types (e.g., dnf_groups_multimedia) and configurations ...

# --- Phase 3: Terminal Enhancement ---
phase3_terminal_enhancement:
  # Key-value pairs where the value is a command string to be executed.
  # These commands are run as the target user.
  atuin_install: "cargo install atuin"
  zsh_autosuggestions_clone: "git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions"
  # ... other terminal tools and Zsh plugins ...
```

  You can (and should!) customize this file extensively to match your desired setup – add or remove packages, define different commands, or even structure entirely new phases.
  Ensure that commands intended for user-specific setup (like Zsh plugin installations) are compatible with being executed via `sudo -u <user> bash -c COMMAND`.

## 🎨 Dotfile Customization

Personalize your terminal experience! This project supports deploying your custom dotfiles for `zsh` and `nano`:

*   Place your custom `.zshrc` file inside the `Fedora-AutoEnv-Setup/zsh/` directory. 📄
*   Place your custom `.nanorc` file inside the `Fedora-AutoEnv-Setup/nano/` directory. 📄

During `Phase 3: Terminal Enhancement`, these files will be automatically copied to the target user's home directory. Existing files with the same names will be backed up (e.g., `~/.zshrc` becomes `~/.zshrc.backup_Fedora-AutoEnv-Setup`).

## ▶️ Usage Guide

1.  **📥 Clone the Repository:**
    Get the latest version of the project:
    ```bash
    git clone <your-repository-url>
    cd Fedora-AutoEnv-Setup
    ```

2.  **✍️ Customize Configuration (Crucial Step!):**
    This is where you tailor the setup to your exact preferences:
    *   **Edit `packages.json`:** This is your primary control panel. Define the software, commands, and specific settings you want for each phase.
    *   **Prepare Your Dotfiles:**
        *   If you have a personalized Zsh configuration, copy your `.zshrc` file into the `Fedora-AutoEnv-Setup/zsh/` directory.
        *   For a custom Nano text editor setup, place your `.nanorc` file into the `Fedora-AutoEnv-Setup/nano/` directory.

3.  **🐍 Install Python Dependencies (if needed):**
    If you haven't installed these already for other projects:
    ```bash
    sudo pip3 install PyYAML rich
    ```
    (Or use `pip3 install --user PyYAML rich` for a local user installation, ensuring `~/.local/bin` is in your `PATH`).

4.  **🚀 Run the Installer:**
    Execute the `install.py` script with `sudo`. **Key Point:** Run this command from the terminal session of the *regular user* whose environment you are setting up (e.g., your main desktop user). The script intelligently uses the `SUDO_USER` environment variable to identify this target user for all user-specific configurations (like shell changes and dotfile deployment).
    ```bash
    sudo python3 install.py
    ```
    Alternatively, if you've made `install.py` executable (e.g., `chmod +x install.py`):
    ```bash
    sudo ./install.py
    ```

5.  **🖱️ Navigate the Interactive Menu:**
    The script will greet you with a user-friendly, interactive menu:
    *   Phases with unmet dependencies will appear as "🔒 `[yellow]Locked[/yellow]`".
    *   Successfully completed phases will be proudly marked "✅ `[green](Completed)[/green]`".
    *   Phases that are ready for execution will show as "➡️ `[cyan](Available)[/cyan]`".
    *   Simply enter the number corresponding to the phase you wish to run.
    *   You have the flexibility to re-run completed phases (the script will ask for confirmation).
    *   Enter 'q' to gracefully exit the installer at any time.

    *(Note: Colors shown above are illustrative of the terminal's output style; they won't render as actual colors within this Markdown document.)*

## 🛠️ How It All Works (Under the Hood)

*   **`install.py` (The Conductor 🎶):**
    *   Defines and loads phase structures, including their human-readable names, descriptions, and critical dependencies.
    *   Manages the `install_status.json` file, which diligently tracks the completion status of each individual phase. This enables resuming setups or selectively re-running parts.
    *   Presents the interactive Text User Interface (TUI) menu, guiding the user smoothly through the available setup options.
    *   Upon user selection, it invokes the appropriate handler function for the chosen phase (these handlers are mapped within `install.py`'s central `PHASES` dictionary) and smartly passes it the global application configuration (which was loaded from `packages.json`).
*   **`scripts/config_loader.py` (The YAML Whisperer 🤫):**
    *   Its sole, focused responsibility is to load and parse the `packages.json` file, transforming its structured data into a readily usable Python dictionary for the rest of the application.
*   **`scripts/console_output.py` (The Visual Artist ✨):**
    *   Provides a convenient and powerful wrapper around the `rich` library. This ensures all terminal output is not just functional but also beautifully styled, clear, and consistent. It offers distinct visual cues for different message types: informational ℹ️, warnings ⚠️, errors ❌, and step progression ➡️.
*   **`scripts/system_utils.py` (The Command Master ⚙️):**
    *   A vital collection of essential utility functions, with `run_command` as its flagship. This function serves as a robust and flexible wrapper around Python's `subprocess.run` module, specifically designed for executing shell commands with enhanced capabilities:
        *   Seamlessly running commands under the context of a different user (via `sudo -Hn -u <user> bash -c "COMMAND"`).
        *   Flexibly capturing command output for later inspection or live-streaming it directly to the console.
        *   Comprehensive error checking and user-friendly reporting to aid in troubleshooting.
*   **Phase-Specific Scripts (`scripts/phase<N>_*.py`) (The Dedicated Workers 🧩):**
    *   Each of these Python scripts diligently encapsulates all the specialized logic required for a particular setup phase (e.g., `phase1_system_preparation.py` handles initial system readiness).
    *   They typically expose a main `run_phase<N>(app_config)` function, which acts as the designated entry point called by the `install.py` orchestrator.
    *   Within this function, they methodically:
        *   Fetch their phase-specific configuration details from the global `app_config` dictionary (often using `config_loader.get_phase_data`).
        *   Execute a carefully ordered sequence of sub-tasks. These frequently involve calls to `system_utils.run_command` for a diverse range of operations, including DNF package installations, system-wide configurations, or the execution of custom shell commands defined in `packages.json`.
        *   Perform necessary file manipulations, such as editing critical system files (e.g., `/etc/dnf/dnf.conf`, `/etc/systemd/resolved.conf`) or copying user-specific dotfiles.
        *   For tasks that directly impact a specific user's environment (like altering their default shell or installing Zsh plugins into their home directory), they accurately determine the target user (usually via the `SUDO_USER` environment variable) and expertly leverage the `run_as_user` capability of `system_utils.run_command`.

### 🚀 Current Phases Implemented

*   **Phase 1: System Preparation** ⚙️
    *   Installs core DNF packages (e.g., `dnf5`, `flatpak` if specified).
    *   Configures DNF for **performance** (`max_parallel_downloads`, `fastestmirror`).
    *   Sets up **RPM Fusion** (free and non-free) repositories.
    *   Configures DNS to use Google's public DNS servers (via `systemd-resolved` if active, or fallback).
    *   Cleans DNF metadata and performs a full system update (`dnf upgrade -y`).
    *   Sets up the **Flathub** repository system-wide for Flatpak.
    *   Allows interactive setting of the system **hostname**.
*   **Phase 2: Basic System Package Configuration** 📦
    *   Installs essential general DNF packages (e.g., `git`, `curl`, `zsh`, `python3-pip`).
    *   Configures **media codecs**:
        *   Installs DNF multimedia groups (e.g., `@multimedia`).
        *   Swaps `ffmpeg-free` with the full `ffmpeg` from RPM Fusion.
        *   Applies DNF group upgrade options for multimedia packages.
        *   Installs DNF sound and video groups (e.g., `@sound-and-video`).
*   **Phase 3: Terminal Enhancement** 💻✨
    *   Checks for Zsh installation and sets it as the **default shell** for the target user (typically `SUDO_USER`).
    *   Installs user-defined terminal enhancement tools and Zsh plugins via shell commands (e.g., `atuin`, `eza`, `zoxide`, `zsh-autosuggestions`, `zsh-syntax-highlighting`) run as the target user.
    *   Copies pre-configured `.zshrc` and `.nanorc` files to the target user's home directory, backing up existing ones.
*   **Phase 4: GNOME Configuration & Extensions** 🎨🖼️
    *   Installs DNF packages relevant to GNOME (e.g., `gnome-tweaks`, `gnome-shell-extensions`).
    *   Ensures `gnome-extensions-cli` is installed via `pip` for the target user.
    *   Installs and enables **GNOME Shell Extensions** for the target user based on `packages.json`. Supports:
        *   Extensions from `extensions.gnome.org` (EGO) via UUID or numerical ID.
        *   Extensions from Git repositories via cloning and running a specified install script.
    *   Installs specified Flatpak applications system-wide (e.g., GNOME Extension Manager).
*   **Phase 5: NVIDIA Driver Installation** 🎮🖥️
    *   Prompts the user for **confirmation** before proceeding, warning about GPU compatibility.
    *   Checks if NVIDIA drivers appear to be already installed.
    *   Performs a system update (`dnf update -y`) and advises a **reboot** if the kernel was updated before driver installation.
    *   Enables the RPM Fusion non-free **tainted** repository if configured.
    *   Allows user selection between **standard proprietary** NVIDIA drivers or **open kernel module** drivers if both are configured.
    *   Installs the chosen NVIDIA drivers (`akmod-nvidia` and `xorg-x11-drv-nvidia-cuda`, or swaps to/installs `akmod-nvidia-open`).
    *   Advises the user to **wait** for kernel modules to build and provides a command to check.
    *   Strongly recommends a system **REBOOT** to complete the driver installation.
*   **Phase 6: Additional User Packages** 🧩🌐
    *   Installs a list of additional **DNF packages** as specified in the configuration.
    *   Installs a list of additional **Flatpak applications** (system-wide from Flathub) as specified in the configuration.

## 🙌 Contributing

We love contributions! If you're inspired to add new phases, refine existing ones, or enhance the core tool, please follow these steps:
1.  Fork the repository 🍴 (`git clone ... && cd ...`)
2.  Create your feature branch (`git checkout -b feature/MyAwesomeFeature`)
3.  Commit your masterpiece (`git commit -m 'feat: Add MyAwesomeFeature'`)
4.  Push to your branch (`git push origin feature/MyAwesomeFeature`)
5.  Open a Pull Request 📥 on GitHub.

Please ensure your code is clean, well-commented, and adheres to the project's style.

## 📜 License

This project is distributed under the MIT License. See the `LICENSE` file for more details.

## ⚠️ Disclaimer

This tool is powerful and modifies system configurations, installs software, and can alter user environments. While developed with care, unforeseen issues can occur.

**‼️ ALWAYS back up your important data and system, or test thoroughly in a virtual machine or non-critical environment before running `Fedora-AutoEnv-Setup` on a primary or production system. ‼️**

Use this tool at your own risk.
The authors and contributors are not responsible for any damage, data loss, or other adverse effects that may result from its use.