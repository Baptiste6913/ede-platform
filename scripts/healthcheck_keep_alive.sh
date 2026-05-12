#!/usr/bin/env bash
# healthcheck_keep_alive.sh — Oracle Always Free anti-reclaim activity stub.
#
# Oracle reclaims idle Always Free compute after 7 days. We need to look "active":
#  - generate ~5 minutes of light CPU usage every 6h
#  - touch a small file
#  - log a JSON line for audit
#
# This script is invoked by cron (installed by oracle_bootstrap.sh).

set -euo pipefail

DURATION_SECONDS="${KEEP_ALIVE_DURATION_SECONDS:-300}"
LOG_FILE="${KEEP_ALIVE_LOG:-$HOME/.ede_keep_alive.log}"
TOUCH_FILE="${KEEP_ALIVE_TOUCHFILE:-$HOME/.ede_keep_alive.last}"

start_ts=$(date -u +%s)
end_ts=$(( start_ts + DURATION_SECONDS ))

# Light CPU activity: bound by wallclock, not raw loops, to avoid burning power needlessly.
# Run two parallel `yes` piped to md5sum at nice 19 for the duration.
nice -n 19 timeout "${DURATION_SECONDS}s" bash -c 'yes | md5sum >/dev/null' &
pid1=$!
nice -n 19 timeout "${DURATION_SECONDS}s" bash -c 'yes | md5sum >/dev/null' &
pid2=$!

wait "$pid1" "$pid2" 2>/dev/null || true

now=$(date -u +%s)
duration=$(( now - start_ts ))

touch "$TOUCH_FILE"

printf '{"ts":"%s","duration_s":%d,"end_target":%d}\n' \
  "$(date -u --iso-8601=seconds)" "$duration" "$end_ts" \
  >> "$LOG_FILE"
