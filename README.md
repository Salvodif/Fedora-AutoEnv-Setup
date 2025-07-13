
#  Fedora AutoEnv Setup

Fedora AutoEnv Setup è uno strumento semplificato e basato sulla configurazione per automatizzare l'installazione di un ambiente Fedora. Semplifica l'installazione di pacchetti, la configurazione delle impostazioni di sistema e l'impostazione degli strumenti di sviluppo attraverso un unico script facile da usare.

## Key Features

- 🚀 **Installazione semplificata**: un unico comando per avviare l'intero processo di installazione.
- ⚙️ **Configuration-Driven**: personalizza facilmente la tua configurazione modificando il file `packages.json`. Non c'è bisogno di scavare negli script.
- 🤖 **Processi automatizzati**: gestisce la configurazione DNF, l'installazione di RPM Fusion, l'installazione di pacchetti (DNF e Flatpak), Nerd Fonts e altro ancora.
- 🖱️ **Sezioni interattive e facoltative**: conferma i principali passaggi di installazione come la configurazione di GNOME e l'installazione dei driver NVIDIA.
- 🧹 **Pulito e organizzato**: un set minimo di file ne facilita la comprensione e la manutenzione.
- 📝 **Registrazione robusta**: tutte le operazioni vengono registrate su `fedora_autoenv_setup.log` per un facile debug.

## Come funziona

Lo script `install.py` legge tutte le sue istruzioni dal file `packages.json`. Questo file è organizzato in sezioni logiche, che consentono di specificare:

- Impostazioni delle prestazioni DNF
- Pacchetti DNF e Flatpak da installare
- Font Nerd da scaricare e configurare
- Applicazioni e configurazioni del terminale
- Configurazioni opzionali dei driver GNOME e NVIDIA

Lo script esegue queste attività in sequenza, fornendo un feedback chiaro e registrando tutto lungo il percorso.

## Prerequisiti

- 🖥️ Una nuova installazione di Fedora Workstation.
- 🌐 Una connessione Internet attiva.
- 🔒 È necessario eseguire lo script con `sudo`.

## Utilizzo

1. **Clona il repository:**
   ```bash
   git clone https://github.com/your-username/Fedora-AutoEnv-Setup.git
   cd Fedora-AutoEnv-Setup
   ```

2. **Personalizza la tua configurazione (opzionale):**
   Apri il file `packages.json` e modificalo in modo che corrisponda alla configurazione desiderata. Puoi aggiungere o rimuovere pacchetti, modificare le impostazioni DNF o disabilitare intere sezioni.

3. **Esegui lo script di installazione:**
   ```bash
   sudo python3 install.py
   ```

Lo script ti guiderà attraverso il processo di installazione, chiedendo conferma per i passaggi principali.

## Configurazione (`packages.json`)

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