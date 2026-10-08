#!/bin/bash
# Echo Weather Installer
# Standalone installer with system detection and dependency auto-resolution.
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

# --- Color Definitions (ANSI 256 + standard) ---
C_CYAN='\033[38;5;51m'
C_SKY='\033[38;5;75m'
C_BLUE='\033[38;5;33m'
C_GOLD='\033[38;5;220m'
C_AMBER='\033[38;5;208m'
C_WHITE='\033[1;37m'
C_GREEN='\033[38;5;48m'
C_RED='\033[38;5;196m'
C_YELLOW='\033[38;5;226m'
C_DIM='\033[38;5;245m'
C_BOLD='\033[1m'
C_RESET='\033[0m'

# --- Helpers ---
info()    { echo -e "  ${C_GREEN}[✓]${C_RESET} $*"; }
warn()    { echo -e "  ${C_YELLOW}[!]${C_RESET} $*"; }
err()     { echo -e "  ${C_RED}[✗]${C_RESET} $*" >&2; }
item()    { echo -e "  ${C_SKY}•${C_RESET} $*"; }
section() { echo -e "\n${C_BOLD}${C_SKY}$*${C_RESET}"; }

# --- Check non-interactive argument ---
AUTO_CONFIRM=false
for arg in "$@"; do
    case "$arg" in
        -y|--yes)
            AUTO_CONFIRM=true
            ;;
    esac
done

# --- Print Colorful CLI Banner ---
print_banner() {
    echo
    echo -e "\033[0m \033[0m \033[0m \033[0m \033[0m\033[38;2;215;235;255m▄\033[0m\033[38;2;255;255;255m▄\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[0m\033[38;2;255;255;255m▄\033[0m\033[38;2;255;255;255m▄\033[0m \033[0m \033[0m \033[0m \033[0m \033[0m  \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[38;2;255;184;0m\033[48;2;255;184;0m▀\033[38;2;255;184;0m\033[48;2;255;184;0m▀\033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m   \033[1;37mE C H O   W E A T H E R\033[0m"
    echo -e "\033[0m \033[0m \033[0m\033[38;2;215;235;255m▄\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[0m \033[0m \033[0m \033[0m \033[0m  \033[0m \033[0m \033[0m \033[0m\033[38;2;255;210;0m▄\033[0m\033[38;2;255;184;0m▄\033[0m \033[0m \033[0m \033[0m \033[38;2;255;185;0m\033[48;2;255;183;0m▀\033[38;2;255;185;0m\033[48;2;255;183;0m▀\033[0m \033[0m \033[0m \033[0m \033[0m\033[38;2;255;184;0m▄\033[0m\033[38;2;255;210;0m▄\033[0m \033[0m \033[0m \033[0m   \033[38;5;245mMeteorological Suite for Linux\033[0m"
    echo -e "\033[0m \033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[0m\033[38;2;145;185;225m▀\033[0m\033[38;2;215;235;255m▄\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[0m\033[38;2;255;255;255m▄\033[0m \033[0m  \033[0m \033[0m \033[0m \033[0m\033[38;2;255;184;0m▀\033[38;2;255;219;0m\033[48;2;255;187;0m▀\033[38;2;255;183;0m\033[48;2;255;185;0m▀\033[0m \033[0m\033[38;2;255;201;0m▄\033[0m\033[38;2;255;203;0m▄\033[0m\033[38;2;255;196;0m▄\033[0m\033[38;2;255;192;0m▄\033[0m\033[38;2;255;189;0m▄\033[0m\033[38;2;255;180;0m▄\033[0m \033[38;2;255;184;0m\033[48;2;255;185;0m▀\033[38;2;255;218;0m\033[48;2;255;187;0m▀\033[0m\033[38;2;255;184;0m▀\033[0m \033[0m \033[0m \033[0m "
    echo -e "\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;145;185;225m▀\033[38;2;215;235;255m\033[48;2;145;185;225m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[0m\033[38;2;215;235;255m▀\033[0m\033[38;2;215;235;255m▀\033[0m \033[0m\033[38;2;215;235;255m▄\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[0m\033[38;2;255;255;255m▄\033[0m  \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m\033[38;2;255;198;0m▄\033[38;2;255;201;0m\033[48;2;255;226;0m▀\033[38;2;255;225;0m\033[48;2;255;215;0m▀\033[38;2;255;214;0m\033[48;2;255;219;0m▀\033[38;2;255;207;0m\033[48;2;255;215;0m▀\033[38;2;255;200;0m\033[48;2;255;205;0m▀\033[38;2;255;196;0m\033[48;2;255;195;0m▀\033[38;2;255;198;0m\033[48;2;255;185;0m▀\033[38;2;255;174;0m\033[48;2;255;191;0m▀\033[0m\033[38;2;255;167;0m▄\033[0m \033[0m \033[0m \033[0m \033[0m \033[0m   \033[38;5;75mEcosystem : \033[1;37mEcho Desktop\033[0m"
    echo -e "\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;145;185;225m▀\033[38;2;145;185;225m\033[48;2;145;185;225m▀\033[0m\033[38;2;145;185;225m▀\033[0m \033[0m \033[0m \033[0m \033[38;2;145;185;225m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[0m  \033[0m\033[38;2;255;183;0m▄\033[0m\033[38;2;255;186;0m▄\033[0m\033[38;2;255;196;0m▄\033[0m\033[38;2;255;183;0m▄\033[0m \033[38;2;255;198;0m\033[48;2;255;197;0m▀\033[38;2;255;215;0m\033[48;2;255;207;0m▀\033[38;2;255;219;0m\033[48;2;255;215;0m▀\033[38;2;255;227;0m\033[48;2;255;219;0m▀\033[38;2;255;219;0m\033[48;2;255;214;0m▀\033[38;2;255;208;0m\033[48;2;255;205;0m▀\033[38;2;255;197;0m\033[48;2;255;196;0m▀\033[38;2;255;187;0m\033[48;2;255;185;0m▀\033[38;2;255;181;0m\033[48;2;255;175;0m▀\033[38;2;255;165;0m\033[48;2;255;166;0m▀\033[0m \033[0m\033[38;2;255;186;0m▄\033[0m\033[38;2;255;195;0m▄\033[0m\033[38;2;255;186;0m▄\033[0m\033[38;2;255;183;0m▄\033[0m   \033[38;5;75mPlatform  : \033[1;37mLinux (All Distros & DEs)\033[0m"
    echo -e "\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;145;185;225m▀\033[38;2;145;185;225m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[0m \033[0m \033[0m \033[0m \033[0m \033[38;2;255;255;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[0m  \033[0m\033[38;2;255;183;0m▀\033[0m\033[38;2;255;186;0m▀\033[0m\033[38;2;255;196;0m▀\033[0m\033[38;2;255;183;0m▀\033[0m \033[38;2;255;193;0m\033[48;2;255;183;0m▀\033[38;2;255;200;0m\033[48;2;255;197;0m▀\033[38;2;255;205;0m\033[48;2;255;195;0m▀\033[38;2;255;208;0m\033[48;2;255;197;0m▀\033[38;2;255;205;0m\033[48;2;255;196;0m▀\033[38;2;255;199;0m\033[48;2;255;191;0m▀\033[38;2;255;191;0m\033[48;2;255;184;0m▀\033[38;2;255;181;0m\033[48;2;255;176;0m▀\033[38;2;255;172;0m\033[48;2;255;172;0m▀\033[38;2;255;163;0m\033[48;2;255;157;0m▀\033[0m \033[0m\033[38;2;255;186;0m▀\033[0m\033[38;2;255;195;0m▀\033[0m\033[38;2;255;186;0m▀\033[0m\033[38;2;255;183;0m▀\033[0m   \033[38;5;75mEngine    : \033[1;37mPyGObject + Cairo\033[0m"
    echo -e "\033[38;2;215;235;255m\033[48;2;145;185;225m▀\033[38;2;255;255;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;145;185;225m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[0m \033[0m \033[0m \033[0m \033[38;2;215;235;255m\033[48;2;145;185;225m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[0m  \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m\033[38;2;255;177;0m▀\033[38;2;255;199;0m\033[48;2;255;172;0m▀\033[38;2;255;185;0m\033[48;2;255;191;0m▀\033[38;2;255;186;0m\033[48;2;255;180;0m▀\033[38;2;255;185;0m\033[48;2;255;175;0m▀\033[38;2;255;181;0m\033[48;2;255;172;0m▀\033[38;2;255;176;0m\033[48;2;255;171;0m▀\033[38;2;255;168;0m\033[48;2;255;175;0m▀\033[38;2;255;175;0m\033[48;2;255;155;0m▀\033[0m\033[38;2;255;154;0m▀\033[0m \033[0m \033[0m \033[0m \033[0m \033[0m "
    echo -e "\033[0m \033[0m\033[38;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[0m \033[0m  \033[0m \033[0m \033[0m \033[0m\033[38;2;255;184;0m▄\033[38;2;255;187;0m\033[48;2;255;219;0m▀\033[38;2;255;185;0m\033[48;2;255;183;0m▀\033[0m \033[0m\033[38;2;255;170;0m▀\033[0m\033[38;2;255;170;0m▀\033[0m\033[38;2;255;165;0m▀\033[0m\033[38;2;255;162;0m▀\033[0m\033[38;2;255;161;0m▀\033[0m\033[38;2;255;157;0m▀\033[0m \033[38;2;255;185;0m\033[48;2;255;184;0m▀\033[38;2;255;187;0m\033[48;2;255;218;0m▀\033[0m\033[38;2;255;184;0m▄\033[0m \033[0m \033[0m \033[0m "
    echo -e "\033[0m \033[0m \033[0m\033[38;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;255;255;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;145;185;225m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[0m\033[38;2;215;235;255m▀\033[0m \033[0m \033[0m  \033[0m \033[0m \033[0m \033[0m\033[38;2;255;210;0m▀\033[0m\033[38;2;255;184;0m▀\033[0m \033[0m \033[0m \033[0m \033[38;2;255;186;0m\033[48;2;255;183;0m▀\033[38;2;255;186;0m\033[48;2;255;183;0m▀\033[0m \033[0m \033[0m \033[0m \033[0m\033[38;2;255;184;0m▀\033[0m\033[38;2;255;210;0m▀\033[0m \033[0m \033[0m \033[0m      \033[38;5;244m[Echo]\033[0m            \033[38;5;244m[Weather]\033[0m"
    echo -e "\033[0m \033[0m \033[0m \033[0m \033[0m \033[0m\033[38;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;145;185;225m▀\033[38;2;215;235;255m\033[48;2;145;185;225m▀\033[38;2;255;255;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;255;255;255m▀\033[38;2;255;255;255m\033[48;2;215;235;255m▀\033[38;2;255;255;255m\033[48;2;215;235;255m▀\033[38;2;215;235;255m\033[48;2;215;235;255m▀\033[0m\033[38;2;145;185;225m▀\033[0m\033[38;2;145;185;225m▀\033[0m \033[0m \033[0m \033[0m \033[0m  \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[38;2;255;184;0m\033[48;2;255;184;0m▀\033[38;2;255;184;0m\033[48;2;255;184;0m▀\033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m \033[0m "
    echo
}

# --- System Detection ---
detect_system() {
    DISTRO_NAME="Linux"
    DISTRO_ID="unknown"
    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        DISTRO_NAME="${PRETTY_NAME:-$NAME}"
        DISTRO_ID="${ID:-unknown}"
    fi

    DESKTOP_ENV="${XDG_CURRENT_DESKTOP:-${DESKTOP_SESSION:-Unknown}}"
    ARCH_NAME="$(uname -m)"

    # Detect package manager
    PKG_MGR="unknown"
    if command -v apt-get > /dev/null 2>&1; then
        PKG_MGR="apt"
    elif command -v dnf > /dev/null 2>&1; then
        PKG_MGR="dnf"
    elif command -v pacman > /dev/null 2>&1; then
        PKG_MGR="pacman"
    elif command -v zypper > /dev/null 2>&1; then
        PKG_MGR="zypper"
    fi
}

print_system_info() {
    section "Host Environment:"
    item "Distribution : ${C_WHITE}${DISTRO_NAME}${C_RESET} (${ARCH_NAME})"
    item "Desktop Env  : ${C_WHITE}${DESKTOP_ENV}${C_RESET}"
    item "Pkg Manager  : ${C_WHITE}${PKG_MGR}${C_RESET}"
    item "Supported DE : ${C_GREEN}All Environments${C_RESET} (GNOME, Cinnamon, KDE, XFCE, MATE, LXQt, COSMIC, Tiling WMs)"
}

# --- Dependencies Verification & Auto-Resolve ---
check_and_resolve_dependencies() {
    section "Checking Dependencies:"

    MISSING_REQUIRED=()
    ADW_MISSING=false

    # 1. Python 3
    if command -v python3 > /dev/null 2>&1; then
        PY_VER="$(python3 --version 2>&1 | awk '{print $2}')"
        info "Python 3 (${PY_VER}) found."
    else
        err "Python 3 not found."
        MISSING_REQUIRED+=("python3")
    fi

    # 2. PyGObject (python3-gi)
    if python3 -c "import gi" 2>/dev/null; then
        info "PyGObject (python3-gi) found."
    else
        err "PyGObject (python3-gi) not found."
        MISSING_REQUIRED+=("gi")
    fi

    # 3. GTK 4
    if python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk" 2>/dev/null; then
        GTK_VER="$(python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk; print(f'{Gtk.MAJOR_VERSION}.{Gtk.MINOR_VERSION}.{Gtk.MICRO_VERSION}')" 2>/dev/null || echo '4.x')"
        info "GTK 4 (${GTK_VER}) found."
    else
        err "GTK 4 (gir1.2-gtk-4.0 / gtk4) not found."
        MISSING_REQUIRED+=("gtk4")
    fi

    # 4. Cairo
    if python3 -c "import cairo" 2>/dev/null; then
        info "Cairo (python3-cairo) found."
    else
        err "Cairo (python3-cairo / pycairo) not found."
        MISSING_REQUIRED+=("cairo")
    fi

    # 5. Libadwaita (OPTIONAL - supported in GNOME, fallback across all other DEs)
    if python3 -c "import gi; gi.require_version('Adw', '1'); from gi.repository import Adw" 2>/dev/null; then
        ADW_VER="$(python3 -c "import gi; gi.require_version('Adw', '1'); from gi.repository import Adw; print(Adw.VERSION_STRING)" 2>/dev/null || echo '1.x')"
        info "libadwaita (${ADW_VER}) found. Native Adwaita styling active."
    else
        ADW_MISSING=true
        warn "libadwaita (gir1.2-adw-1) not installed."
        echo -e "      ${C_DIM}Note: Echo Weather works across all desktop environments (GNOME, Cinnamon, KDE, XFCE, MATE, tiling WMs) via GTK 4.${C_RESET}"
    fi

    # Handle Missing Required Dependencies
    if [ ${#MISSING_REQUIRED[@]} -gt 0 ]; then
        echo
        err "Required system packages are missing."
        suggest_and_install_packages true "${MISSING_REQUIRED[@]}"
    fi

    # Offer to install optional libadwaita if only it is missing
    if [ "$ADW_MISSING" = true ]; then
        suggest_optional_adwaita
    fi
}

# Map missing tokens to distro packages
get_distro_packages() {
    local target_pkg="$1"
    case "$PKG_MGR" in
        apt)
            case "$target_pkg" in
                python3) echo "python3" ;;
                gi)      echo "python3-gi" ;;
                gtk4)    echo "gir1.2-gtk-4.0" ;;
                cairo)   echo "python3-gi-cairo python3-cairo" ;;
                adw)     echo "gir1.2-adw-1" ;;
            esac
            ;;
        dnf)
            case "$target_pkg" in
                python3) echo "python3" ;;
                gi)      echo "python3-gobject" ;;
                gtk4)    echo "gtk4" ;;
                cairo)   echo "python3-cairo" ;;
                adw)     echo "libadwaita" ;;
            esac
            ;;
        pacman)
            case "$target_pkg" in
                python3) echo "python" ;;
                gi)      echo "python-gobject" ;;
                gtk4)    echo "gtk4" ;;
                cairo)   echo "python-cairo" ;;
                adw)     echo "libadwaita" ;;
            esac
            ;;
        *)
            echo "$target_pkg"
            ;;
    esac
}

suggest_and_install_packages() {
    local is_required="$1"
    shift
    local missing_items=("$@")

    local install_list=""
    for m in "${missing_items[@]}"; do
        pkgs="$(get_distro_packages "$m")"
        install_list="$install_list $pkgs"
    done
    install_list="$(echo "$install_list" | xargs)"

    echo -e "\n  ${C_BOLD}Required package command:${C_RESET}"
    case "$PKG_MGR" in
        apt)    echo "    sudo apt install -y $install_list" ;;
        dnf)    echo "    sudo dnf install -y $install_list" ;;
        pacman) echo "    sudo pacman -S --needed $install_list" ;;
        *)      echo "    Install: $install_list" ;;
    esac
    echo

    if [ "$PKG_MGR" != "unknown" ]; then
        if [ "$AUTO_CONFIRM" = true ]; then
            answer="y"
        else
            read -rp "  Install missing dependencies automatically via sudo? [y/N]: " answer
        fi
        case "$answer" in
            [yY][eE][sS]|[yY])
                echo -e "  ${C_SKY}Running package manager...${C_RESET}"
                case "$PKG_MGR" in
                    apt)    sudo apt-get update && sudo apt-get install -y $install_list ;;
                    dnf)    sudo dnf install -y $install_list ;;
                    pacman) sudo pacman -S --needed --noconfirm $install_list ;;
                esac
                # Recheck
                echo -e "  ${C_GREEN}Dependencies installed. Continuing installation...${C_RESET}"
                return
                ;;
        esac
    fi

    if [ "$is_required" = true ]; then
        err "Required dependencies are not satisfied. Please install them and re-run install.sh."
        exit 1
    fi
}

suggest_optional_adwaita() {
    local adw_pkg
    adw_pkg="$(get_distro_packages "adw")"

    if [ "$PKG_MGR" != "unknown" ]; then
        echo
        echo -e "  ${C_SKY}Optional:${C_RESET} Install libadwaita for full GNOME style integration."
        echo -e "  Manual command: ${C_DIM}sudo $PKG_MGR install $adw_pkg${C_RESET}"

        if [ "$AUTO_CONFIRM" = true ]; then
            answer="n"
        else
            read -rp "  Install optional libadwaita ($adw_pkg) now? [y/N]: " answer
        fi
        case "$answer" in
            [yY][eE][sS]|[yY])
                echo -e "  ${C_SKY}Installing libadwaita...${C_RESET}"
                case "$PKG_MGR" in
                    apt)    sudo apt-get install -y $adw_pkg ;;
                    dnf)    sudo dnf install -y $adw_pkg ;;
                    pacman) sudo pacman -S --needed --noconfirm $adw_pkg ;;
                esac
                info "libadwaita installed successfully."
                ;;
            *)
                info "Continuing in GTK 4 fallback mode (universal support for all DEs)."
                ;;
        esac
    fi
}

# --- Show Target Paths ---
show_target_plan() {
    section "Installation Target Layout:"
    echo -e "  ${C_DIM}┌───────────────────────────────────────────────────────────────────────────┐${C_RESET}"
    echo -e "  ${C_DIM}│${C_RESET}  ${C_BOLD}Launcher Binary${C_RESET}  : ${C_WHITE}$INSTALL_DIR/echo-weather${C_RESET}"
    echo -e "  ${C_DIM}│${C_RESET}  ${C_BOLD}Application Core${C_RESET} : ${C_WHITE}$APP_DIR${C_RESET}"
    echo -e "  ${C_DIM}│${C_RESET}  ${C_BOLD}Desktop Entry${C_RESET}    : ${C_WHITE}$DESKTOP_DIR/com.echo.weather.desktop${C_RESET}"
    echo -e "  ${C_DIM}│${C_RESET}  ${C_BOLD}Application Icon${C_RESET} : ${C_WHITE}$ICON_DIR/com.echo.weather.svg${C_RESET}"
    echo -e "  ${C_DIM}│${C_RESET}  ${C_BOLD}User Config${C_RESET}      : ${C_WHITE}$CONFIG_DIR${C_RESET}"
    echo -e "  ${C_DIM}│${C_RESET}  ${C_BOLD}Forecast Cache${C_RESET}   : ${C_WHITE}$CACHE_DIR${C_RESET}"
    echo -e "  ${C_DIM}└───────────────────────────────────────────────────────────────────────────┘${C_RESET}"
    echo

    if [ "$AUTO_CONFIRM" = false ]; then
        read -rp "  Proceed with installation? [Y/n]: " answer
        case "$answer" in
            [nN][oO]|[nN])
                echo "Installation cancelled by user."
                exit 0
                ;;
        esac
    fi
}

# --- Installation Steps ---
perform_installation() {
    section "Installing Echo Weather:"

    # 1. Directories
    mkdir -p "$INSTALL_DIR" "$DESKTOP_DIR" "$ICON_DIR" "$APP_DIR" "$CONFIG_DIR" "$CACHE_DIR"
    info "Target directories initialized."

    # 2. Copy application files
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
    else
        for item in *.py *.css echo-weather assets data detail_cards models providers services; do
            src="$SCRIPT_DIR/$item"
            if [ -e "$src" ]; then
                cp -r "$src" "$APP_DIR/"
            fi
        done
    fi
    info "Application source files and assets deployed."

    # 3. Launcher
    cp "$SCRIPT_DIR/echo-weather" "$INSTALL_DIR/echo-weather"
    chmod +x "$INSTALL_DIR/echo-weather"
    info "Command launcher installed to $INSTALL_DIR/echo-weather"

    # 4. Desktop entry
    if [ -f "$SCRIPT_DIR/com.echo.weather.desktop" ]; then
        cp "$SCRIPT_DIR/com.echo.weather.desktop" "$DESKTOP_DIR/com.echo.weather.desktop"
        info "Desktop application shortcut registered."
    else
        warn "Desktop entry template missing - skipping."
    fi

    # 5. Icon
    ICON_SRC=""
    for candidate in \
        "$SCRIPT_DIR/assets/echo_weather_logo.svg" \
        "$SCRIPT_DIR/assets/icons/weather/clear-day.svg" \
        "$SCRIPT_DIR/assets/icons/com.echo.weather.svg"; do
        if [ -f "$candidate" ]; then
            ICON_SRC="$candidate"
            break
        fi
    done

    if [ -n "$ICON_SRC" ]; then
        cp "$ICON_SRC" "$ICON_DIR/com.echo.weather.svg"
        chmod 644 "$ICON_DIR/com.echo.weather.svg"
        info "Application icon installed."
    else
        warn "No icon found - skipping icon installation."
    fi

    # 6. Update desktop & icon caches
    if command -v update-desktop-database > /dev/null 2>&1; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null && info "Desktop database updated." || true
    fi
    if command -v gtk-update-icon-cache > /dev/null 2>&1; then
        gtk-update-icon-cache -f -t "$DATA_DIR/icons/hicolor" 2>/dev/null && info "Icon cache updated." || true
    fi
}

# --- Summary Card ---
print_summary() {
    local py_v gtk_v adw_mode
    py_v="$(python3 --version 2>&1 | awk '{print $2}')"
    gtk_v="$(python3 -c "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk; print(f'{Gtk.MAJOR_VERSION}.{Gtk.MINOR_VERSION}.{Gtk.MICRO_VERSION}')" 2>/dev/null || echo '4.x')"

    if python3 -c "import gi; gi.require_version('Adw','1')" 2>/dev/null; then
        adw_mode="Libadwaita (GNOME / Modern GTK 4)"
    else
        adw_mode="Pure GTK 4 (Cinnamon / KDE / XFCE / All DEs)"
    fi

    echo
    echo -e "  ${C_GREEN}${C_BOLD}========================================================================${C_RESET}"
    echo -e "  ${C_WHITE}${C_BOLD}                 Echo Weather successfully installed!                  ${C_RESET}"
    echo -e "  ${C_GREEN}------------------------------------------------------------------------${C_RESET}"
    echo -e "  ${C_BOLD}Terminal Command${C_RESET} : ${C_SKY}echo-weather${C_RESET}"
    echo -e "  ${C_BOLD}Application Menu${C_RESET} : Search for ${C_WHITE}\"Echo Weather\"${C_RESET} in your launcher"
    echo -e "  ${C_BOLD}Active Runtime  ${C_RESET} : Python ${py_v} | GTK ${gtk_v} | ${adw_mode}"
    echo -e "  ${C_BOLD}Compatibility   ${C_RESET} : ${C_GREEN}Universal${C_RESET} (all Linux distros and desktop environments)"
    echo -e "  ${C_GREEN}========================================================================${C_RESET}"

    # Verify if ~/.local/bin is in PATH
    case ":$PATH:" in
        *":$INSTALL_DIR:"*) ;;
        *)
            echo
            warn "'$INSTALL_DIR' is not in your current PATH."
            echo -e "      To run '${C_WHITE}echo-weather${C_RESET}' directly from any terminal, add this to ${C_WHITE}~/.bashrc${C_RESET} or ${C_WHITE}~/.zshrc${C_RESET}:"
            echo -e "      ${C_SKY}export PATH=\"\$HOME/.local/bin:\$PATH\"${C_RESET}"
            ;;
    esac
    echo
}

# --- Main Entrypoint ---
main() {
    print_banner
    detect_system
    print_system_info
    check_and_resolve_dependencies
    show_target_plan
    perform_installation
    print_summary
}

main "$@"
