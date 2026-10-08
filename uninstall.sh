#!/bin/bash
# Echo Weather Uninstaller
set -euo pipefail

INSTALL_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
DESKTOP_DIR="$DATA_DIR/applications"
ICON_DIR="$DATA_DIR/icons/hicolor/scalable/apps"
APP_DIR="$DATA_DIR/echo-weather"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/echo-weather"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/echo-weather"

BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${BOLD}Echo Weather Uninstaller${NC}"
echo
echo "The following will be removed:"
echo "  $INSTALL_DIR/echo-weather"
echo "  $DESKTOP_DIR/com.echo.weather.desktop"
echo "  $ICON_DIR/com.echo.weather.svg"
echo "  $APP_DIR/"
echo
echo "The following will be KEPT (your settings and cache):"
echo "  $CONFIG_DIR"
echo "  $CACHE_DIR"
echo

read -rp "Proceed with uninstall? [y/N] " answer
case "$answer" in
    [yY][eE][sS]|[yY]) ;;
    *)
        echo "Uninstall cancelled."
        exit 0
        ;;
esac

echo "Removing files..."
rm -f  "$INSTALL_DIR/echo-weather"
rm -f  "$DESKTOP_DIR/com.echo.weather.desktop"
rm -f  "$ICON_DIR/com.echo.weather.svg"
rm -rf "$APP_DIR"

if command -v update-desktop-database > /dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache > /dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$DATA_DIR/icons/hicolor" 2>/dev/null || true
fi

echo
echo -e "${GREEN}Echo Weather has been uninstalled.${NC}"
echo
echo "Your configuration is preserved at: $CONFIG_DIR"
echo "To also remove it, run:"
echo -e "  ${RED}rm -rf $CONFIG_DIR $CACHE_DIR${NC}"
