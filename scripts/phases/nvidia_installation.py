import os

def main():
    commands = [
        "sudo dnf install kernel-devel kernel-headers gcc make dkms acpid libglvnd-glx libglvnd-opengl libglvnd-devel pkgconfig",
        "sudo dnf install https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm",
        "sudo dnf install https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm",
        "sudo dnf makecache",
        "sudo dnf install akmod-nvidia xorg-x11-drv-nvidia-cuda",
        "sudo grub2-mkconfig -o /boot/grub2/grub.cfg",
        "gsettings set org.gnome.mutter experimental-features [\"kms-modifiers\"]"
    ]

    for command in commands:
        os.system(command)

if __name__ == "__main__":
    main()
