# My Personal Dotfiles

This repository contains my personal configuration files (dotfiles) for various applications.
The goal is to keep my development and shell environment consistent across different machines.

## Current Structure
```
dotfiles/
├── nano/
│ └── nanorc.txt # Configuration for GNU nano editor
├── zsh/
│ └── zshrc.txt # Configuration for Zsh shell
└── README.md # This file
```

## Contents

### 1. Zsh (`zsh/.zshrc`)

My Zsh configuration aims for productivity and a pleasant user experience. It's built upon **Oh My Zsh**.

**Key Features & Tools:**

*   **Oh My Zsh:** Framework for managing Zsh configuration.
    *   **Theme:** `random` (selects a random theme on startup).
    *   **Update Mode:** `reminder` (reminds to update Oh My Zsh).
*   **Plugins:**
    *   `git`: Adds many Git aliases and functions.
    *   `zsh-autosuggestions`: Suggests commands as you type based on history.
    *   `zsh-syntax-highlighting`: Provides syntax highlighting for commands in the shell.
    *   `you-should-use`: Reminds you to use existing aliases for commands you type.
    *   `zsh-eza`: Integrates `eza` (a modern `ls` replacement) with Zsh.
    *   `fzf-tab`: Replaces Zsh's default completion selection with `fzf`.
*   **Command Aliases:**
    *   `df` -> `dust` (modern `du` alternative)
    *   `top` -> `btop` (modern `top` alternative)
    *   `cat` -> `bat` (modern `cat` alternative with syntax highlighting)
*   **Essential Tools Integrated:**
    *   `fzf`: Command-line fuzzy finder (heavily used by `fzf-tab` and for history).
    *   `zoxide`: A "smarter cd" command that learns your habits.
    *   `atuin`: Magical shell history, syncing across machines.
*   **Custom PATH additions:**
    *   `$HOME/.local/bin`
    *   `$HOME/.cargo/bin` (for Rust binaries)
*   **Perl local::lib setup:** Configured for a local Perl environment in `~/perl5`.
*   **Custom fzf-tab source:** Sourced directly.

**Prerequisites/Dependencies for Zsh:**

1.  **Zsh Shell:** Must be installed.
2.  **Oh My Zsh:** Installation instructions: [https://ohmyz.sh/](https://ohmyz.sh/)
3.  **Fonts:** Some themes (especially `agnoster` if it's randomly selected) require Powerline-patched fonts for special characters.
4.  **Plugins:**
    *   **zsh-autosuggestions:**
        ```bash
        git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions
        ```
    *   **zsh-syntax-highlighting:**
        ```bash
        git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting
        ```
    *   **you-should-use:**
        ```bash
        git clone https://github.com/MichaelHoste/zsh-you-should-use.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/you-should-use
        ```
    *   **zsh-eza:** (Assumes `eza` is installed)
        ```bash
        git clone https://github.com/z-shell/zsh-eza ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-eza
        ```
    *   **fzf-tab:** (Your config sources it directly, ensure it's present)
        ```bash
        # If not already there, clone it:
        # mkdir -p ~/.oh-my-zsh/custom/plugins
        # git clone https://github.com/Aloxaf/fzf-tab ~/.oh-my-zsh/custom/plugins/fzf-tab
        ```
5.  **External Tools to Install:**
    *   `eza`: (e.g., `sudo apt install eza`, `brew install eza`, or from source)
    *   `dust`: (e.g., `cargo install dust`)
    *   `btop`: (e.g., `sudo apt install btop`, `brew install btop`, or from source)
    *   `bat`: (e.g., `sudo apt install bat`, `brew install bat`, or from source. Often needs to be aliased as `batcat` on Debian/Ubuntu, then `alias cat=batcat`)
    *   `fzf`: (e.g., `sudo apt install fzf`, `brew install fzf`)
    *   `zoxide`: (Installation instructions: [https://github.com/ajeetdsouza/zoxide#installation](https://github.com/ajeetdsouza/zoxide#installation))
    *   `atuin`: (Installation instructions: [https://atuin.sh/docs/install](https://atuin.sh/docs/install))
    *   (Optional) `perl` and `cpanm` if you intend to use the Perl local library setup.

### 2. Nano (`nano/.nanorc`)

Configuration for the GNU nano text editor.

**Key Features:**

*   Includes a comprehensive set of syntax highlighting rules for various file types from `/usr/share/nano/`.

**Prerequisites/Dependencies for Nano:**

1.  **GNU nano:** Must be installed.
2.  Syntax highlighting files: These are typically installed by default with `nano` in `/usr/share/nano/`. If not, you might need to install a package like `nano-syntax-highlighting` or ensure your `nano` installation is complete.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Salvodif/dotfiles.git ~/.dotfiles
    cd ~/.dotfiles
    ```

2.  **Install Zsh configuration:**
    *   First, ensure all prerequisites listed above for Zsh are installed (Oh My Zsh, plugins, external tools).
    *   Backup your existing `~/.zshrc` if you have one:
        ```bash
        mv ~/.zshrc ~/.zshrc.backup
        ```
    *   Create a symbolic link:
        ```bash
        ln -s ~/.dotfiles/zsh/zshrc.txt ~/.zshrc
        ```
    *   Restart your shell or source the new config: `source ~/.zshrc`

3.  **Install Nano configuration:**
    *   Backup your existing `~/.nanorc` if you have one:
        ```bash
        mv ~/.nanorc ~/.nanorc.backup
        ```
    *   Create a symbolic link:
        ```bash
        ln -s ~/.dotfiles/nano/nanorc.txt ~/.nanorc
        ```

## Management

Currently, installation is manual via symbolic links. For more complex setups or managing dotfiles across multiple machines, consider using tools like:

*   [GNU Stow](https://www.gnu.org/software/stow/)
*   [Chezmoi](https://www.chezmoi.io/)
*   A custom shell script

## Customization

Feel free to fork this repository and adapt the configurations to your own needs.
The Zsh configuration, in particular, has many commented-out options that you can explore.

## Note

The Perl environment variables (PERL5LIB, etc.) are specific to a local Perl installation via `local::lib` into `/home/blackpraedicator/perl5`. Adjust or remove these if they don't apply to your setup. The paths will need to be changed if your username is not `blackpraedicator`.

## License

This project is licensed under the MIT License.
