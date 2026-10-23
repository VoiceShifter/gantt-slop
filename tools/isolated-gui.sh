#!/usr/bin/env bash
# Both a private X server and Qt's non-windowing plugin: never use the desktop.
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
unset WAYLAND_DISPLAY WAYLAND_SOCKET DBUS_SESSION_BUS_ADDRESS SESSION_MANAGER
export QT_QPA_PLATFORM=offscreen
export QT_QUICK_BACKEND=software
export QT_QPA_PLATFORMTHEME=generic
exec xvfb-run -a -s '-screen 0 1920x1080x24 -nolisten tcp' "$@"
