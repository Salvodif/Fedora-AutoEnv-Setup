# My Personal Dotfiles & Fedora Setup Automator 🚀

This repository contains my personal configuration files (dotfiles) and an automation script (`install.py`) to set up my preferred environment on a fresh **Fedora Workstation** installation. The goal is to keep my development and shell environment consistent and quickly deployable.

## 🌟 What `install.py` Automates

The `install.py` script is designed to take a fresh Fedora installation and configure it with the tools and settings I use daily. Here's a breakdown of what it does:

1.  **<img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/fedora/fedora-original.svg" width="16" height="16" alt="Fedora Logo" /> System Preparation (Fedora Focused):**
    *   Checks if running on Fedora.
    *   Performs a system update and upgrade (`dnf update -y && dnf upgrade -y`).
    *   Checks for critical dependencies like `git` and `curl`.

2.  **📦 Essential Packages (via DNF):**
    *   Installs a curated list of packages:
        *   `git`, `curl`, `stow`, `dnf-plugins-core`
        *   `cargo` (Rust's package manager, for installing Rust-based tools)
        *   `powerline-fonts` (for better terminal aesthetics with some Zsh themes)
        *   `btop` (modern resource monitor)
        *   `bat` (a `cat` clone with syntax highlighting and Git integration)
        *   `fzf` (command-line fuzzy finder)
        *   `gnome-extensions-app`, `gnome-shell-extension-manager` (for GNOME desktop users)

3.  **🚀 Zsh & Oh My Zsh Ecosystem:**
    *   Installs **Oh My Zsh** automatically.
    *   Clones and sets up the following **Oh My Zsh plugins**:
        *   `zsh-autosuggestions`
        *   `zsh-syntax-highlighting`
        *   `you-should-use`
        *   `zsh-eza`
        *   `fzf-tab`

4.  **🦀 Modern CLI Tools (via Cargo & Scripts):**
    *   Installs **Cargo-based tools**:
        *   `eza` (a modern replacement for `ls`)
        *   `du-dust` (a more intuitive version of `du`)
    *   Installs tools via their **official installation scripts**:
        *   `zoxide` (a smarter `cd` command)
        *   `atuin` (magical shell history with sync capabilities)

5.  **⚙️ Dotfile Deployment:**
    *   Copies the `zsh/.zshrc` from this repository to `~/.zshrc`.
    *   Copies the `nano/.nanorc` from this repository to `~/.nano/nanorc`.
    *   Backs up any existing `.zshrc` or `nanorc` files before overwriting.

6.  **🛠️ GNOME Utilities (for GNOME Desktop):**
    *   Installs `gnome-extensions-app` and `gnome-shell-extension-manager` for easier GNOME Shell extension management.
    *   (Future development: direct installation/management of specific extensions via the script).

7.  **✅ Post-Installation Checks:**
    *   Verifies the installation of key tools.

## 📁 Repository Structure
```markdown
.
├── install.py # The main Python setup script
├── zsh/
│ └── .zshrc # Source Zsh configuration (deployed by install.py)
├── nano/
│ └── .nanorc # Source Nano configuration (deployed by install.py)
├── LICENSE # The MIT License file for this project
└── README.md # This file
```


## 📋 Prerequisites (for running `install.py`)

*   **Operating System:** Fedora Linux (Workstation with GNOME is the primary target).
*   **Permissions:** `sudo` access (the script must be run as root).
*   **Python 3:** With the `rich` library and its dependencies (the script attempts to guide if missing, but pre-installation is smoother).
*   **Internet Connection:** To download packages, Oh My Zsh, plugins, and tools.

## 🚀 How to Use `install.py`

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Salvodif/dotfiles.git
    cd dotfiles
    ```
    (You can clone it anywhere, e.g., `~/dotfiles` or `~/Downloads/dotfiles`)

2.  **Review the script (Optional but Recommended):**
    Take a look at `install.py` to understand what it will do.

3.  **Run the script with `sudo`:**
    ```bash
    sudo python3 install.py
    ```
    The script will:
    *   Detect the original user who ran `sudo` (e.g., `blackpraedicator`).
    *   Perform all installations and configurations for that user.
    *   Present a menu for different actions (e.g., "Perform Initial Environment Setup").

4.  **Follow the on-screen menu and prompts.**

## 📄 About the Deployed Dotfiles

The `install.py` script will deploy the following configuration files. Here's what they contain:

### 1. Zsh (`zsh/.zshrc`)

My Zsh configuration aims for productivity and a pleasant user experience. It's built upon **Oh My Zsh**.

**Key Features & Tools Configured (and installed by `install.py` if missing):**

*   **Oh My Zsh:** Framework for managing Zsh configuration.
    *   **Theme:** `random` (selects a random theme on startup).
    *   **Update Mode:** `reminder` (reminds to update Oh My Zsh).
*   **Plugins (installed by `install.py`):**
    *   `git`: Adds many Git aliases and functions.
    *   `zsh-autosuggestions`: Suggests commands as you type based on history.
    *   `zsh-syntax-highlighting`: Provides syntax highlighting for commands in the shell.
    *   `you-should-use`: Reminds you to use existing aliases for commands you type.
    *   `zsh-eza`: Integrates `eza`.
    *   `fzf-tab`: Replaces Zsh's default completion selection with `fzf`.
*   **Command Aliases:**
    *   `df` -> `dust`
    *   `top` -> `btop`
    *   `cat` -> `bat`
*   **Essential Tools Integrated (installed by `install.py`):**
    *   `fzf`: Command-line fuzzy finder.
    *   `zoxide`: A "smarter cd" command.
    *   `atuin`: Magical shell history.
*   **Custom PATH additions:**
    *   `$HOME/.local/bin`
    *   `$HOME/.cargo/bin`
*   **Perl local::lib setup:** Configured for a local Perl environment (see "Important Notes" below).
*   **Custom fzf-tab source:** Sourced directly from its plugin directory.

### 2. Nano (`nano/.nanorc`)

Configuration for the GNU nano text editor.

**Key Features:**

*   Includes a comprehensive set of syntax highlighting rules for various file types from `/usr/share/nano/` (these are generally installed by default with `nano` on Fedora).

## 💡 Important Notes

*   **Username Specifics:** The Perl environment variables in `.zshrc` (`PERL5LIB`, etc.) are hardcoded for the user `blackpraedicator` and path `~/perl5`. If your username is different or you don't use this Perl setup, you should **manually edit `zsh/.zshrc` in this repository *before* running `install.py`**, or edit `~/.zshrc` *after* the script has run.
*   **Log Files:** The `install.py` script creates log files in the target user's home directory:
    *   `~/enhanced_setup_python.log` (detailed operations log)
    *   `~/setup_script_console_output.txt` (copy of the console output)
*   **Idempotency:** The script tries to be somewhat idempotent (e.g., it won't reinstall Oh My Zsh if already present, and checks for existing commands). However, re-running the full setup might still re-trigger some downloads or configurations.

## 🛠️ Manual Dotfile Management (Alternative/Legacy)

Previously, these dotfiles were intended for manual installation using symbolic links. If you prefer not to use `install.py` or are on a non-Fedora system, you can still manually link them after installing all dependencies:

1.  Clone the repository: `git clone https://github.com/Salvodif/dotfiles.git ~/.dotfiles`
2.  Install Zsh config: `ln -s ~/.dotfiles/zsh/.zshrc ~/.zshrc` (backup existing first)
3.  Install Nano config: `mkdir -p ~/.nano && ln -s ~/.dotfiles/nano/.nanorc ~/.nano/nanorc` (backup existing first)
    *Make sure all prerequisites listed in the `.zshrc`'s comments (plugins, tools like eza, fzf, etc.) are manually installed first.*

## 🔮 Future Developments for `install.py`

*   More robust GNOME extension management.
*   Option to select which categories of tools/configs to install.
*   Better handling of non-Fedora systems (e.g., guiding package installation).

## 📜 License

This project is licensed under the MIT License.