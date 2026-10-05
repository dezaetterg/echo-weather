#!/bin/bash
# Echo Weather Installer
set -e

INSTALL_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
DESKTOP_DIR="$DATA_DIR/applications"
ICON_DIR="$DATA_DIR/icons/hicolor/scalable/apps"
APP_DIR="$DATA_DIR/echo-weather"

mkdir -p "$INSTALL_DIR" "$DESKTOP_DIR" "$ICON_DIR" "$APP_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing Echo Weather to $APP_DIR..."

# Copy application files (excluding git, tests, cache)
if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
        --exclude='.git*' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='.ruff_cache' \
        --exclude='tests' \
        --exclude='scratch' \
        "$SCRIPT_DIR/" "$APP_DIR/"
else
    cp -r "$SCRIPT_DIR"/*.py "$SCRIPT_DIR"/*.css "$APP_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR"/assets "$SCRIPT_DIR"/data "$SCRIPT_DIR"/detail_cards "$SCRIPT_DIR"/models "$SCRIPT_DIR"/providers "$SCRIPT_DIR"/services "$APP_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/echo-weather" "$APP_DIR/" 2>/dev/null || true
fi

# Copy launcher to bin
cp "$SCRIPT_DIR/echo-weather" "$INSTALL_DIR/echo-weather"
chmod +x "$INSTALL_DIR/echo-weather"

# Copy desktop entry
cp "$SCRIPT_DIR/com.echo.weather.desktop" "$DESKTOP_DIR/com.echo.weather.desktop"

# Copy app icon
if [ -f "$SCRIPT_DIR/assets/icons/weather/clear-day.svg" ]; then
    cp "$SCRIPT_DIR/assets/icons/weather/clear-day.svg" "$ICON_DIR/com.echo.weather.svg"
fi

# Update desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

# Update icon cache
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$DATA_DIR/icons/hicolor" 2>/dev/null || true
fi

echo "========================================================"
echo " Echo Weather installed successfully!"
echo " Command: $INSTALL_DIR/echo-weather"
echo " You can launch it from your desktop app menu or CLI."
echo "========================================================"
