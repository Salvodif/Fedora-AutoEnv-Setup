# Fedora AutoEnv Setup 🚀✨

![Logo](assets/logo.png)

<div align="center">
     <p align="center">
    <a href="https://www.python.org/downloads/">
      <img src="https://img.shields.io/badge/python-3.x-blue.svg" alt="Python Version">
    </a>
    <a href="LICENSE">
      <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT">
    </a>
    <a href="https://github.com/salvodif/Fedora-AutoEnv-Setup/stargazers">
      <img src="https://img.shields.io/github/stars/salvodif/TomeTrove?style=social" alt="GitHub Stars">
    </a>
    <a href="https://github.com/salvodif/Fedora-AutoEnv-Setup/issues">
      <img src="https://img.shields.io/github/issues/salvodif/TomeTrove" alt="GitHub Issues">
    </a>
    <a href="https://github.com/salvodif/Fedora-AutoEnv-Setup/network/members">
      <img src="https://img.shields.io/github/forks/salvodif/TomeTrove?style=social" alt="GitHub Forks">
    </a>
  </p>

</div>

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
│ ├── 📜 logger_utils.py # Utility for application logging
│ ├── ⚙️ system_utils.py # Utility for running system commands
│ ├── 1️⃣ phase1_system_preparation.py # Logic for Phase 1
│ ├── 2️⃣ phase2_basic_installation.py # Logic for Phase 2
│ ├── 3️⃣ phase3_terminal_enhancement.py # Logic for Phase 3
│ ├── 🎨 phase4_gnome_configuration.py # Logic for Phase 4
│ ├── 🎮 phase5_nvidia_installation.py # Logic for Phase 5
│ ├── 🧩 phase6_additional_packages.py # Logic for Phase 6
└── 📖 README.md # This file (You are here!)
```

## ✅ Prerequisites

*   **OS:** Fedora Linux 🐧 (This tool is tailored for Fedora).
*   **Python:** Python 3.6+ 🐍.
*   **Python Packages:**
    *   `rich`: For the enhanced and colorful console output.
    Install them easily using `pip`:
    ```bash
    sudo pip3 install rich
    ```

*   **🔑 Sudo Privileges:** The main `install.py` script **must** be run with `sudo`. Many operations (package installation, system-wide configuration changes, modifying user shells) require root access.

## 🔧 Configuration (`packages.json`)

The `packages.json` file is the heart ❤️ of `Fedora-AutoEnv-Setup`. This JSON file dictates precisely what actions are performed in each setup phase.

**Example Snippet:**
```json
{
  "phase1_system_preparation": {
    "dnf_packages": [
      "dnf5",
      "dnf5-plugins"
    ]
  },
  "phase2_basic_configuration": {
    "dnf_packages": [
      "git",
      "curl",
      "zsh"
    ],
    "dnf_swap_ffmpeg": {
      "from": "ffmpeg-free",
      "to": "ffmpeg"
    },
    "nerd_fonts_to_install": {
        "Hack": "https://github.com/ryanoasis/nerd-fonts/releases/download/v3.2.1/Hack.zip"
    }
  },
  "phase3_terminal_enhancement": {
    "omz": "sh -c \"$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh) --unattended\"",
    "atuin_install": "cargo install atuin",
    "zsh_autosuggestions_clone": "git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-autosuggestions"
  }
}
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
    sudo pip3 install rich
    ```
    (Or use `pip3 install --user rich` for a local user installation, ensuring `~/.local/bin` is in your `PATH`).

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
*   **`scripts/config_loader.py` (The Config Guardian 🤫):**
    *   Loads and parses the main configuration file, `packages.json`, which defines all phases, packages, and commands.
    *   Searches for `packages.json` first in the project root directory, then in the current working directory.
    *   Handles errors like file not found or JSON parsing issues gracefully, returning an empty configuration if problems occur.
    *   Provides `get_phase_data` to extract specific phase configurations.
*   **`scripts/console_output.py` (The Visual Artist ✨):**
    *   Wraps the `rich` library to provide clear, styled, and interactive terminal output.
    *   Offers functions for various message types (info ℹ️, warning ⚠️, error ❌, success ✅), section formatting (`print_step`, `print_sub_step`, `print_panel`, `print_rule`), and user interaction (`ask_question`, `confirm_action`).
*   **`scripts/logger_utils.py` (The Log Keeper 📜):**
    *   Responsible for setting up and configuring the application-wide logger (`app_logger`).
    *   Provides centralized log formatting, file logging (to `fedora_autoenv_setup.log`), and optional console logging.
    *   Ensures consistent logging behavior across all modules of the application.
*   **`scripts/system_utils.py` (The System Toolkit 🛠️):**
    *   Provides a comprehensive suite of utility functions for system interactions.
    *   Core function `run_command` executes shell commands with options for running as a specific user (via `sudo -Hn -u <user> bash -c "COMMAND"`), capturing output, and robust error handling.
    *   Includes helpers for user and environment information: `get_target_user` (determines the non-root user, often `SUDO_USER`), `get_user_home_dir`.
    *   Manages files and directories: `backup_system_file`, `ensure_dir_exists`.
    *   Handles user shell management: `get_user_shell`, `ensure_shell_in_etc_shells`, `set_default_shell`.
    *   Wraps package manager operations:
        *   DNF: `install_dnf_packages`, `install_dnf_groups`, `swap_dnf_packages`, `upgrade_system_dnf`, `clean_dnf_cache`, `is_package_installed_rpm`.
        *   Pip: `install_pip_packages` (user and system-wide).
        *   Flatpak: `ensure_flathub_remote_exists`, `install_flatpak_apps`.
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
    *   Installs core DNF packages specified in `packages.json` (e.g., `dnf5`, `flatpak`).
    *   Configures DNF for performance and behavior by setting `max_parallel_downloads`, `fastestmirror`, `defaultyes` (auto-yes for prompts), and `keepcache` in `dnf.conf`.
    *   Sets up **RPM Fusion** (free and non-free) repositories automatically based on the detected Fedora version.
    *   Configures system DNS using servers from `packages.json` or defaulting to Google Public DNS; handles `systemd-resolved` or direct `/etc/resolv.conf` modification.
    *   Cleans DNF metadata (`dnf clean all`) and performs a full system update (`dnf upgrade -y`).
    *   Ensures the **Flathub** Flatpak repository is set up system-wide.
    *   Allows interactive setting of the system **hostname**.
*   **Phase 2: Basic System Package Configuration** 📦
    *   Installs essential general DNF packages specified in `packages.json` (e.g., `git`, `curl`, `unzip`, `fontconfig`).
    *   Configures **media codecs** based on `packages.json`:
        *   Swaps `ffmpeg-free` with the full `ffmpeg` from RPM Fusion if configured.
        *   Installs specified DNF sound and video groups (e.g., `@multimedia`, `@sound-and-video`).
    *   Installs specified Flatpak applications 📦 (system-wide) from `packages.json`.
    *   Downloads and installs specified Nerd Fonts ✒️ to the target user's font directory (`~/.local/share/fonts`), then refreshes the font cache (`fc-cache -fv`).
*   **Phase 3: Terminal Enhancement** 💻✨
    *   Checks if Zsh is installed. If it is, but not the default shell, it prompts the user to set Zsh as **default** (using `chsh`). This step also ensures Zsh is listed in `/etc/shells`.
    *   Installs **Oh My Zsh** if not already present, using the command specified by the `omz` key in `packages.json`. The script attempts a non-interactive install (setting `RUNZSH=no CHSH=no` for the OMZ installer).
    *   Installs user-defined **Oh My Zsh plugins, themes, and other terminal tools** by executing shell commands from `packages.json`. These commands are run as the target user, with `$HOME` and `$ZSH_CUSTOM` variables substituted. Git clone commands for plugins may be skipped if the target directory already exists.
    *   Copies pre-configured dotfiles to the target user's home directory, backing up existing ones:
        *   `.zshrc` (from project's `zsh/` directory) is copied if Zsh is the default shell and Zsh enhancements are proceeding.
        *   `.nanorc` (from project's `nano/` directory) is copied.
*   **Phase 4: GNOME Configuration & Extensions** 🎨🖼️
    *   Installs DNF packages relevant to GNOME (e.g., `gnome-tweaks`) as specified in `packages.json`.
    *   Installs user-defined Pip packages (run as the target user) from `packages.json` (e.g., this *could* include `gnome-extensions-cli` if the user adds it).
    *   Installs **GNOME Shell Extensions** of `type: "git"` defined in `packages.json`:
        *   Clones the extension's Git repository.
        *   Optionally runs a build command specified in the configuration.
        *   Moves the extension files to the target user's `~/.local/share/gnome-shell/extensions/UUID/` directory.
        *   **Note:** This process only *installs* the extension files. Enabling the extension requires manual user action (e.g., via the GNOME Extensions app/website or `gnome-extensions-cli` if installed separately).
    *   Installs specified Flatpak applications system-wide from `packages.json` (e.g., GNOME Extension Manager, which can then be used to enable extensions).
    *   Applies system-wide **Dark Mode** 🌙 by setting `org.gnome.desktop.interface color-scheme 'prefer-dark'` and `gtk-theme 'Adwaita-dark'` for the target user via GSettings.
*   **Phase 5: NVIDIA Driver Installation** 🎮🖥️
    *   Prompts the user for **confirmation** before proceeding, warning about GPU compatibility.
    *   Checks if NVIDIA drivers (standard `akmod-nvidia` or `akmod-nvidia-open`) appear to be already installed.
    *   Performs a full system upgrade (`dnf upgrade -y`) and advises a **reboot** if the kernel was updated, before proceeding with driver installation.
    *   Enables the RPM Fusion non-free **tainted** repository by installing the package specified in `packages.json`, if configured.
    *   Allows user selection between **standard proprietary** NVIDIA drivers (from `dnf_packages_standard` list in config) or **open kernel module** drivers (via `dnf_swap_open_drivers` config) if both pathways are configured.
    *   Installs the chosen NVIDIA drivers (`akmod-nvidia` and `xorg-x11-drv-nvidia-cuda`, or swaps to/installs `akmod-nvidia-open`).
    *   Advises the user to **wait** for kernel modules to build and provides a command to check.
    *   Strongly recommends a system **REBOOT** to complete the driver installation.
*   **Phase 6: Additional User Packages** 🧩🌐
    *   Installs a list of additional **DNF packages** as specified in `packages.json`.
    *   Installs DNF packages requiring **custom repository configurations** 🛠️📦 as defined under `custom_repo_dnf_packages` in `packages.json`. For each such package, the script:
        *   Optionally checks if a specified indicator package (via `check_if_installed_pkg`) is already present.
        *   Executes a list of `repo_setup_commands` (e.g., to import GPG keys, add .repo files).
        *   Installs the target DNF package (via `dnf_package_to_install`).
    *   Installs a list of additional **Flatpak applications** (system-wide from Flathub by default) as specified in `packages.json`.

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
