#!/bin/zsh
# Nightly encrypted backup of the project's raw data (traces, sqlite, run folders that git ignores)
# to the netcup server "german". Code and reports are on GitHub; this covers everything else.
# archive/ is excluded: the stopped Merrow thread never changes.
#
# Repository password: macOS Keychain item "restic-judgment-action-gap" (account "backup").
# Keep a copy of it in your password manager: without it the backup cannot be read.

set -u
PROJECT="/Users/user/Projects/Move38/Measuring the Judgment-Action Gap in Large Language Models"
HERE="${0:A:h}"
export RESTIC_REPOSITORY="sftp:german:/srv/restic/judgment-action-gap"
export RESTIC_PASSWORD_COMMAND="/usr/bin/security find-generic-password -s restic-judgment-action-gap -a backup -w"
RESTIC=/opt/homebrew/bin/restic
MIN_FREE_GB=5          # the server also runs the VPN: never fill its disk
UPLOAD_KIB=4096        # ~4 MB/s, leaves bandwidth for VPN users

log() { print -r -- "$(date '+%F %T') $*"; }

free_gb=$(/usr/bin/ssh -o BatchMode=yes -o ConnectTimeout=15 german "df -BG --output=avail / | tail -1 | tr -dc 0-9")
if [[ -z "$free_gb" ]]; then log "server unreachable, skipping"; exit 1; fi
if (( free_gb < MIN_FREE_GB )); then
  log "only ${free_gb}G free on german (< ${MIN_FREE_GB}G), skipping"
  /usr/bin/osascript -e "display notification \"Only ${free_gb} GB free on german\" with title \"restic backup skipped\"" 2>/dev/null
  exit 1
fi

log "backup start (${free_gb}G free on german)"
"$RESTIC" backup "$PROJECT" \
  --exclude-file "$HERE/excludes.txt" \
  --exclude-caches --one-file-system \
  --limit-upload "$UPLOAD_KIB" \
  --tag nightly --compression auto --quiet || { log "backup FAILED"; exit 1; }

"$RESTIC" forget --tag nightly --keep-daily 14 --keep-weekly 8 --keep-monthly 12 --prune \
  --limit-upload "$UPLOAD_KIB" --quiet || log "forget/prune failed"

# Read back a sample of the data every Sunday so a broken repository is noticed early.
if [[ $(date +%u) == 7 ]]; then
  "$RESTIC" check --read-data-subset 5% --quiet && log "check ok" || log "check FAILED"
fi
log "backup done"
