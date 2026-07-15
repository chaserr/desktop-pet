#!/usr/bin/env bash
# One-click resume: removes the suspension marker so desktop-pet pops up again.
# Works from Terminal AND when double-clicked in Finder (.command extension).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
FILE="$HERE/data/suspended_until.txt"
if [ -f "$FILE" ]; then
    UNTIL="$(cat "$FILE")"
    rm -f "$FILE"
    echo "✓ resumed — was suspended until $UNTIL"
    echo "  desktop-pet will pop up again at the next scheduled reminder"
else
    echo "not suspended — nothing to resume"
fi
