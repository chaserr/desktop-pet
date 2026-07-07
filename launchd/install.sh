#!/usr/bin/env bash
# Install/uninstall the launchd job that wakes the pet on the work-hour schedule.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_DIR="$(cd "$HERE/.." && pwd)"
VENV_PY="$SCRIPT_DIR/.venv/bin/python"
TEMPLATE="$HERE/com.desktop-pet.reminder.plist.template"
PLIST_DST="$HOME/Library/LaunchAgents/com.desktop-pet.reminder.plist"

usage() {
    echo "Usage: $0 [install|uninstall|status]"
    exit 1
}

do_install() {
    if [ ! -x "$VENV_PY" ]; then
        echo "ERROR: venv python not found at $VENV_PY"
        echo "       run: python3 -m venv $SCRIPT_DIR/.venv && $SCRIPT_DIR/.venv/bin/pip install -r $SCRIPT_DIR/requirements.txt"
        exit 1
    fi
    mkdir -p "$(dirname "$PLIST_DST")"
    sed -e "s|__SCRIPT_DIR__|$SCRIPT_DIR|g" -e "s|__VENV_PY__|$VENV_PY|g" "$TEMPLATE" > "$PLIST_DST"
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    launchctl load -w "$PLIST_DST"
    echo "installed: $PLIST_DST"
    echo "log:       /tmp/desktop-pet-reminder.log"
    echo "next fire: hour :00 (10,11,14,15,16,17,18) on workdays"
}

do_uninstall() {
    if [ -f "$PLIST_DST" ]; then
        launchctl unload "$PLIST_DST" 2>/dev/null || true
        rm -f "$PLIST_DST"
        echo "removed: $PLIST_DST"
    else
        echo "not installed"
    fi
}

do_status() {
    if launchctl list | grep -q com.desktop-pet.reminder; then
        echo "loaded"
        launchctl list com.desktop-pet.reminder 2>/dev/null || true
    else
        echo "not loaded"
    fi
    [ -f /tmp/desktop-pet-reminder.log ] && echo "--- last 20 lines of log ---" && tail -n 20 /tmp/desktop-pet-reminder.log
    [ -f /tmp/desktop-pet-reminder.err ] && echo "--- last 20 lines of err ---" && tail -n 20 /tmp/desktop-pet-reminder.err
}

case "${1:-}" in
    install)   do_install ;;
    uninstall) do_uninstall ;;
    status)    do_status ;;
    *)         usage ;;
esac
