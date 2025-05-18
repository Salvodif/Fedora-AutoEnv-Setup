# Fedora Auto Environment Setup - Manual Installation Guide

This guide provides step-by-step terminal commands to replicate the setup performed by the automated scripts. Execute these commands carefully in your terminal.

**Prerequisites:**
*   A fresh Fedora (GNOME Desktop recommended) installation.
*   Internet access.
*   Basic familiarity with the Linux terminal.
*   Run commands prefixed with `sudo` with administrator privileges.
*   For user-specific configurations, ensure you are running commands as that user, or be mindful of commands that affect `$HOME` or user-specific services. When the original script uses `SUDO_USER`, this guide will indicate that a step should be performed by the primary non-root user.

---

## ⚙️ Phase 1: System Preparation

This initial phase prepares your Fedora system by installing essential tools, configuring DNF for better performance, setting up crucial software repositories, ensuring reliable DNS, and updating your system.

### STEP 1️⃣: Install Core DNF Packages  foundational_tools:
These packages include an updated DNF (DNF5), Flatpak for sandboxed applications, and other utilities.
```bash
sudo dnf install -y dnf5 dnf5-plugins flatpak
```

✨ Done! Core tools are now available.

---

## STEP 2️⃣: Configure DNF Performance & Behavior 🚀

Optimize DNF for faster downloads and set some convenient default behaviors.

# Backup your existing DNF configuration (always a good idea!)
sudo cp -pf /etc/dnf/dnf.conf /etc/dnf/dnf.conf.backup_$(date +%F_%T)

# You can manually edit /etc/dnf/dnf.conf using 'sudo nano /etc/dnf/dnf.conf'
# Ensure the following lines are present under the [main] section:
#
# fastestmirror=True
# max_parallel_downloads=10
# defaultyes=True
# keepcache=True
#
# Or, attempt to add/update them with these commands:
```bash
CONF_FILE="/etc/dnf/dnf.conf"
echo "Ensuring DNF settings in $CONF_FILE..."
# Remove old entries if they exist to avoid duplicates
sudo sed -i '/^fastestmirror=/d' $CONF_FILE
sudo sed -i '/^max_parallel_downloads=/d' $CONF_FILE
sudo sed -i '/^defaultyes=/d' $CONF_FILE
sudo sed -i '/^keepcache=/d' $CONF_FILE
# Add new entries
echo "fastestmirror=True" | sudo tee -a $CONF_FILE > /dev/null
echo "max_parallel_downloads=10" | sudo tee -a $CONF_FILE > /dev/null
echo "defaultyes=True" | sudo tee -a $CONF_FILE > /dev/null
echo "keepcache=True" | sudo tee -a $CONF_FILE > /dev/null
```

✅ DNF is now tuned for speed! Please manually verify /etc/dnf/dnf.conf if you used the automated commands.

---

## STEP 3️⃣: Setup RPM Fusion Repositories 🧩
Access a wider range of software, including multimedia codecs and proprietary drivers.
