#!/usr/bin/env bash
# backup_nightly.sh — STUB for phase 0; full implementation lands in phase 13.
#
# Planned phase 13 behaviour:
#   - pg_dump --format=custom of the ede database, gzip
#   - tar.gz of /data/pdfs
#   - upload to Backblaze B2 free tier (rclone) or attach to a private GitHub release
#   - rotate: keep 7 daily, 4 weekly, 6 monthly
#
# For now this script only logs that it ran, so cron wiring can be tested.

set -euo pipefail

LOG_FILE="${BACKUP_LOG:-$HOME/.ede_backup.log}"
printf '{"ts":"%s","status":"stub","note":"backup not implemented until phase 13"}\n' \
  "$(date -u --iso-8601=seconds)" >> "$LOG_FILE"
