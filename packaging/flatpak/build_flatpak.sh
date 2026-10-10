#!/usr/bin/env bash
# Echo Weather Flatpak Builder and Test Runner
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$REPO_ROOT/build-flatpak"
REPO_DIR="$REPO_ROOT/repo-flatpak"
APP_ID="io.github.dezaetterg.EchoWeather"

echo "=== Echo Weather Flatpak Build ==="

# Check flatpak builder
if command -v flatpak-builder >/dev/null 2>&1; then
    BUILDER="flatpak-builder"
elif flatpak list --app | grep -q "org.flatpak.Builder"; then
    BUILDER="flatpak run org.flatpak.Builder"
else
    echo "Error: flatpak-builder not found."
    echo "Please install flatpak-builder via your package manager or with:"
    echo "  flatpak install --user flathub org.flatpak.Builder"
    exit 1
fi

echo "Using builder: $BUILDER"

# 1. Build and install locally for user
echo "Building $APP_ID from local sources..."
$BUILDER --user --install --force-clean "$BUILD_DIR" "$SCRIPT_DIR/${APP_ID}.local.yml"

echo "=== Build and installation successful! ==="
echo "To run the application inside Flatpak sandbox, execute:"
echo "  flatpak run $APP_ID"
