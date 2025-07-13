<p align="center">
  <img src="assets/logo.png" alt="Fedora AutoEnv Setup Logo" width="200"/>
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

1. **Clona il repository:**
   ```bash
   git clone https://github.com/your-username/Fedora-AutoEnv-Setup.git
   cd Fedora-AutoEnv-Setup
   ```

## Config (`packages.json`)

Ecco una breve panoramica della struttura di `packages.json`:

- `"dnf_settings"`: un oggetto contenente coppie chiave-valore per le impostazioni in `/etc/dnf/dnf.conf`.
- `"dnf_packages"`: un elenco di pacchetti DNF da installare.
- `"flatpak_apps"`: un dizionario in cui le chiavi sono gli ID delle applicazioni Flatpak e i valori sono i loro nomi descrittivi.
- `"terminal_packages"`: un elenco di pacchetti DNF per il potenziamento del terminale (ad es. `ghostty`, `fish`).
- `"nerd_fonts"`: un dizionario per specificare i caratteri Nerd da installare, con i nomi dei caratteri come chiavi e gli URL di download come valori.
- `"gnome_configuration"`: una sezione facoltativa per i pacchetti relativi a GNOME.
- `"nvidia_installation"`: una sezione facoltativa per i pacchetti di driver NVIDIA.

### Esempio `packages.json`:
```json
{
  "dnf_settings": {
    "max_parallel_downloads": 10,
    "fastestmirror": true
  },
  "dnf_packages": [
    "git",
    "curl",
    "vim"
  ],
  "flatpak_apps": {
    "com.spotify.Client": "Spotify"
  },
  "terminal_packages": [
    "fish"
  ]
}
```

## Contribuire

I contributi sono benvenuti! Se hai idee per miglioramenti o nuove funzionalità, sentiti libero di aprire un problema o inviare una richiesta pull.

## Licenza

Questo progetto è concesso in licenza con la licenza MIT. Per i dettagli, vedere il file [LICENSE](LICENSE).