#!/bin/zsh

MOUNTPOINT="/run/media/blackpraedicator/ExtHDD"
LOGDIR="$HOME/scripts/backup-logs"
LOGFILE="$LOGDIR/backup_$(date +%F_%H-%M-%S).log"

if [[ ! -d "$MOUNTPOINT" ]]; then
  echo "⚠️  L'hard disk esterno non è montato: $MOUNTPOINT"
  echo "Collegalo e riprova."
  exit 1
fi

SOURCE=~/kDrive/
DEST=/run/media/blackpraedicator/ExtHDD/kDrive

rsync -av --delete --itemize-changes "$SOURCE" "$DEST" | \
  sed -e $'s/^>f.*$/\e[32m&\e[0m/' \
      -e $'s/^>f.*$/\e[33m&\e[0m/' \
      -e $'s/^\*deleting.*$/\e[31m&\e[0m/' | \
  tee -a "$LOGFILE"

notify-send "Backup completato" "Documenti sincronizzati su HDD esterno"

