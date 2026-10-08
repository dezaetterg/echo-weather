#!/bin/bash
# Echo Weather Installer
set -euo pipefail

# --- Paths ---
INSTALL_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
DESKTOP_DIR="$DATA_DIR/applications"
ICON_DIR="$DATA_DIR/icons/hicolor/scalable/apps"
APP_DIR="$DATA_DIR/echo-weather"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/echo-weather"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/echo-weather"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Colors ---
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BOLD='\033[1m'
NC='\033[0m'

# --- Helpers ---
info()    { echo -e "  ${GREEN}*${NC} $*"; }
warn()    { echo -e "  ${YELLOW}!${NC} $*"; }
error()   { echo -e "  ${RED}ERROR:${NC} $*" >&2; }
section() { echo -e "\n${BOLD}$*${NC}"; }

# --- Dependency check ---
section "Checking dependencies..."

DEPS_OK=true

check_python() {
    if ! command -v python3 > /dev/null 2>&1; then
        error "python3 not found."
        echo    "  Install it with:"
        echo    "    apt:    sudo apt install python3"
        echo    "    dnf:    sudo dnf install python3"
        echo    "    pacman: sudo pacman -S python"
        DEPS_OK=false
        return
    fi
    info "python3 found: $(python3 --version)"
}

check_python_gi() {
    if ! python3 -c "import gi" 2>/dev/null; then
        error "python3-gi (PyGObject) not found."
        echo    "  Install it with:"
        echo    "    apt:    sudo apt install python3-gi"
        echo    "    dnf:    sudo dnf install python3-gobject"
        echo    "    pacman: sudo pacman -S python-gobject"
        DEPS_OK=false
        return
    fi
    info "python3-gi found."
}

check_adwaita() {
    if ! python3 -c "import gi; gi.require_version('Adw', '1'); from gi.repository import Adw" 2>/dev/null; then
        error "libadwaita GObject introspection data (gir1.2-adw-1) not found."
        echo    "  Install it with:"
        echo    "    apt:    sudo apt install gir1.2-adw-1"
        echo    "    dnf:    sudo dnf install libadwaita"
        echo    "    pacman: sudo pacman -S libadwaita"
        DEPS_OK=false
        return
    fi
    info "libadwaita (Adw 1) found."
}

check_gtk4() {
    if ! python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk" 2>/dev/null; then
        error "GTK4 GObject introspection data (gir1.2-gtk-4.0) not found."
        echo    "  Install it with:"
        echo    "    apt:    sudo apt install gir1.2-gtk-4.0"
        echo    "    dnf:    sudo dnf install gtk4"
        echo    "    pacman: sudo pacman -S gtk4"
        DEPS_OK=false
        return
    fi
    info "GTK 4 found."
}

check_python
check_python_gi
check_adwaita
check_gtk4

if [ "$DEPS_OK" = false ]; then
    echo
    error "One or more required dependencies are missing. Please install them and re-run this script."
    exit 1
fi

# --- Pre-installation summary ---
section "Installation plan:"
echo    "  Application data : $APP_DIR"
echo    "  Launcher         : $INSTALL_DIR/echo-weather"
echo    "  Desktop entry    : $DESKTOP_DIR/com.echo.weather.desktop"
echo    "  Icon             : $ICON_DIR/com.echo.weather.svg"
echo    "  Config directory : $CONFIG_DIR  (preserved if exists)"
echo    "  Cache directory  : $CACHE_DIR   (preserved if exists)"
echo

read -rp "Proceed with installation? [y/N] " answer
case "$answer" in
    [yY][eE][sS]|[yY]) ;;
    *)
        echo "Installation cancelled."
        exit 0
        ;;
esac

# --- Create directories ---
section "Creating directories..."
mkdir -p "$INSTALL_DIR" "$DESKTOP_DIR" "$ICON_DIR" "$APP_DIR" "$CONFIG_DIR" "$CACHE_DIR"
info "Directories ready."

# --- Copy application files ---
section "Copying application files..."

if command -v rsync > /dev/null 2>&1; then
    rsync -a \
        --exclude='.git' \
        --exclude='.gitignore' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='.ruff_cache' \
        --exclude='tests/' \
        --exclude='dist/' \
        --exclude='packaging/' \
        --exclude='scratch/' \
        "$SCRIPT_DIR/" "$APP_DIR/"
    info "Files copied with rsync."
else
    # Fallback: copy individual items
    for item in *.py *.css echo-weather assets data detail_cards models providers services; do
        src="$SCRIPT_DIR/$item"
        if [ -e "$src" ]; then
            cp -r "$src" "$APP_DIR/"
        fi
    done
    info "Files copied with cp."
fi

# --- Launcher ---
section "Installing launcher..."
cp "$SCRIPT_DIR/echo-weather" "$INSTALL_DIR/echo-weather"
chmod +x "$INSTALL_DIR/echo-weather"
info "Launcher installed to $INSTALL_DIR/echo-weather"

# --- Desktop entry ---
section "Installing desktop entry..."
if [ ! -f "$SCRIPT_DIR/com.echo.weather.desktop" ]; then
    error "Desktop entry file not found: $SCRIPT_DIR/com.echo.weather.desktop"
    exit 1
fi
cp "$SCRIPT_DIR/com.echo.weather.desktop" "$DESKTOP_DIR/com.echo.weather.desktop"
info "Desktop entry installed."

# --- Icon ---
section "Installing icon..."
ICON_SRC=""
for candidate in \
    "$SCRIPT_DIR/assets/icons/com.echo.weather.svg" \
    "$SCRIPT_DIR/assets/icons/weather/clear-day.svg"
do
    if [ -f "$candidate" ]; then
        ICON_SRC="$candidate"
        break
    fi
done

if [ -n "$ICON_SRC" ]; then
    cp "$ICON_SRC" "$ICON_DIR/com.echo.weather.svg"
    info "Icon installed from $ICON_SRC"
else
    warn "No icon file found - skipping icon installation."
fi

# --- Update caches ---
section "Updating desktop/icon caches..."
if command -v update-desktop-database > /dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null && info "Desktop database updated." || warn "update-desktop-database failed (non-fatal)."
fi
if command -v gtk-update-icon-cache > /dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$DATA_DIR/icons/hicolor" 2>/dev/null && info "Icon cache updated." || warn "gtk-update-icon-cache failed (non-fatal)."
fi

# --- Done ---
PYTHON_VER=$(python3 --version)
GTK_VER=$(python3 -c "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk; print(f'{Gtk.MAJOR_VERSION}.{Gtk.MINOR_VERSION}.{Gtk.MICRO_VERSION}')" 2>/dev/null || echo "unknown")
ADW_VER=$(python3 -c "import gi; gi.require_version('Adw','1'); from gi.repository import Adw; print(Adw.VERSION_STRING)" 2>/dev/null || echo "unknown")

echo
echo -e "${BOLD}========================================================"
echo    " Echo Weather installed successfully!"
echo    "--------------------------------------------------------"
echo    " Command : echo-weather"
echo    " Runtime : $PYTHON_VER | GTK $GTK_VER | Adw $ADW_VER"
echo    "--------------------------------------------------------"
echo    " If '$INSTALL_DIR' is not in your PATH, add this"
echo    " line to your ~/.bashrc or ~/.zshrc:"
echo    "   export PATH=\"\$HOME/.local/bin:\$PATH\""
echo -e "========================================================${NC}"
