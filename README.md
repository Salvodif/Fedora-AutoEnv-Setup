<p align="center">
  <img src="assets/logo.png" alt="Fedora AutoEnv Setup Logo" />
</p>

# Fedora AutoEnv Setup

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Badge">
  <img src="https://img.shields.io/badge/Shell_Script-121011?style=for-the-badge&logo=gnu-bash&logoColor=white" alt="Shell Script Badge">
  <img src="https://img.shields.io/badge/Fedora-51A2DA?style=for-the-badge&logo=fedora&logoColor=white" alt="Fedora Badge">
</p>

Fedora AutoEnv Setup is a streamlined, configuration-driven tool to automate the setup of a Fedora environment. It simplifies the installation of packages, configuration of system settings, and setup of development tools through a single, easy-to-use script.

## Key Features

- 🚀 **Simplified Installation**: A single command to start the entire setup process.
- ⚙️ **Configuration-Driven**: Easily customize your setup by modifying the `packages.json` file. No need to dig through scripts.
- 🤖 **Automated Processes**: Handles DNF configuration, RPM Fusion setup, package installation (DNF and Flatpak), Nerd Fonts, and more.
- 🖱️ **Interactive and Optional Sections**: Confirm major installation steps like GNOME configuration and NVIDIA driver installation.
- 🧹 **Clean and Organized**: A minimal set of files makes it easy to understand and maintain.
- 📝 **Robust Logging**: All operations are logged to `fedora_autoenv_setup.log` for easy debugging.

## Prerequisite

- 🖥️ A fresh installation of Fedora Workstation.
- 🌐 An active internet connection.
- 🔒 You must run the script with `sudo`.


## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/Fedora-AutoEnv-Setup.git
   cd Fedora-AutoEnv-Setup
   ```

## Config (`packages.json`)

Here is a brief overview of the `packages.json` structure, which is organized by phases:

- **`phase1_system_preparation`**: Essential system packages and configurations.
- **`phase2_basic_configuration`**: Core development tools, fonts, and terminal applications like `ghostty` and `fish`.
- **`phase3_gnome_configuration`**: GNOME-specific packages, extensions, and settings.
- **`phase4_nvidia_installation`**: NVIDIA driver packages.
- **`phase5_additional_packages`**: Optional user applications from various sources.

Each phase section can contain:
- `dnf_packages`: A list of DNF packages to install.
- `flatpak_apps`: A dictionary of Flatpak application IDs and their descriptions.
- Other phase-specific keys, such as `dnf_swap_ffmpeg` or `nerd_fonts_to_install`.

### Example `packages.json` Snippet:
```json
{
  "phase1_system_preparation": {
    "dnf_packages": [
      "dnf5",
      "flatpak"
    ]
  },
  "phase2_basic_configuration": {
    "dnf_packages": [
      "git",
      "curl",
      "ghostty",
      "fish"
    ],
    "flatpak_apps": {
      "com.github.tchx84.Flatseal": "Flatseal"
    }
  }
}
```

## Contributing

Contributions are welcome! If you have ideas for improvements or new features, feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License. For details, see the [LICENSE](LICENSE) file.
