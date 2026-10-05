#!/bin/bash
# Echo Weather Uninstaller
set -e

INSTALL_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
DESKTOP_DIR="$DATA_DIR/applications"
ICON_DIR="$DATA_DIR/icons/hicolor/scalable/apps"
APP_DIR="$DATA_DIR/echo-weather"

echo "Uninstalling Echo Weather..."

rm -f "$INSTALL_DIR/echo-weather"
rm -f "$DESKTOP_DIR/com.echo.weather.desktop"
rm -f "$ICON_DIR/com.echo.weather.svg"
rm -rf "$APP_DIR"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$DATA_DIR/icons/hicolor" 2>/dev/null || true
fi

echo "Echo Weather has been uninstalled."
