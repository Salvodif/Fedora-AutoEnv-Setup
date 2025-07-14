# Fedora-AutoEnv-Setup/scripts/phases/gnome_configuration.py
import json

def run(app_config):
    """
    Phase 4: GNOME Configuration
    """
    print("Running Phase 4: GNOME Configuration")

    with open('packages.json', 'r') as f:
        packages = json.load(f)

    gnome_extensions = packages.get('phase3_gnome_configuration', {}).get('gnome_extensions', {})

    if gnome_extensions:
        print("The following GNOME extensions are available:")
        for key, ext in gnome_extensions.items():
            print(f"  - {ext['name']}: {ext['url']}")
    else:
        print("No GNOME extensions found in packages.json")

    print("\nPlease install the extensions you want manually.")

    return True
