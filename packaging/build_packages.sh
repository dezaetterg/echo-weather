#!/bin/bash
# Echo Weather Package Builder
# Generates release tarball (.tar.gz) and Debian package (.deb)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
PKG_VERSION="1.0.0"
DEB_REVISION="1"

mkdir -p "$DIST_DIR"

echo "=== 1. Building release tarball (echo-weather-${PKG_VERSION}.tar.gz) ==="
TARBALL="$DIST_DIR/echo-weather-${PKG_VERSION}.tar.gz"
rm -f "$TARBALL"

tar -czf "$TARBALL" \
    --exclude-vcs \
    --exclude='dist' \
    --exclude='scratch' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    --exclude='.venv' \
    --exclude='venv' \
    --transform "s,^,echo-weather-${PKG_VERSION}/," \
    -C "$ROOT_DIR" \
    .github assets data detail_cards models packaging providers services tests \
    CHANGELOG.md LICENSE README.md REFACTORING_PLAN.md SPECIFICATION.md \
    com.echo.weather.desktop config_manager.py echo-weather i18n.py \
    install.sh logger.py main.py pyproject.toml requirements-dev.txt \
    requirements.txt style.css ui.py uninstall.sh utils.py \
    weather_atmosphere.py weather_detail_sheet.py weather_overview_view.py

echo "Tarball created: $TARBALL"

echo "=== 2. Building Debian package (.deb) ==="
BUILD_ROOT="$(mktemp -d /tmp/echo-weather-deb.XXXXXX)"
trap 'rm -rf "$BUILD_ROOT"' EXIT

APP_DIR="$BUILD_ROOT/usr/share/echo-weather"
BIN_DIR="$BUILD_ROOT/usr/bin"
DESKTOP_DIR="$BUILD_ROOT/usr/share/applications"
ICON_DIR="$BUILD_ROOT/usr/share/icons/hicolor/scalable/apps"
DOC_DIR="$BUILD_ROOT/usr/share/doc/echo-weather"
DEBIAN_DIR="$BUILD_ROOT/DEBIAN"

mkdir -p "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR" "$DOC_DIR" "$DEBIAN_DIR"

# Copy DEBIAN control file
cp "$SCRIPT_DIR/debian/control" "$DEBIAN_DIR/control"

# Copy application source files
cp -r "$ROOT_DIR"/*.py "$ROOT_DIR"/*.css "$APP_DIR/"
cp -r "$ROOT_DIR/assets" "$ROOT_DIR/data" "$ROOT_DIR/detail_cards" "$ROOT_DIR/models" "$ROOT_DIR/providers" "$ROOT_DIR/services" "$APP_DIR/"

# Remove any bytecode in build root
find "$APP_DIR" -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$APP_DIR" -name "*.pyc" -delete 2>/dev/null || true

# Copy launcher to /usr/bin/echo-weather
cp "$ROOT_DIR/echo-weather" "$BIN_DIR/echo-weather"
chmod 755 "$BIN_DIR/echo-weather"

# Copy desktop file
cp "$ROOT_DIR/com.echo.weather.desktop" "$DESKTOP_DIR/com.echo.weather.desktop"
chmod 644 "$DESKTOP_DIR/com.echo.weather.desktop"

# Copy icon
if [ -f "$ROOT_DIR/assets/icons/weather/clear-day.svg" ]; then
    cp "$ROOT_DIR/assets/icons/weather/clear-day.svg" "$ICON_DIR/com.echo.weather.svg"
    chmod 644 "$ICON_DIR/com.echo.weather.svg"
fi

# Copy copyright and changelog
cp "$ROOT_DIR/LICENSE" "$DOC_DIR/copyright"
gzip -9c "$ROOT_DIR/CHANGELOG.md" > "$DOC_DIR/changelog.gz"
chmod 644 "$DOC_DIR/copyright" "$DOC_DIR/changelog.gz"

DEB_FILE="$DIST_DIR/echo-weather_${PKG_VERSION}-${DEB_REVISION}_all.deb"
dpkg-deb --build --root-owner-group "$BUILD_ROOT" "$DEB_FILE"

echo "Debian package created: $DEB_FILE"
echo "=== Packaging Complete! ==="
