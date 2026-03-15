#!/usr/bin/env bash
# ============================================================
#  Axora CLI Agent — Uninstaller
# ============================================================
set -euo pipefail

VENV_DIR="${AXORA_VENV_DIR:-$HOME/.axora/venv}"
CONFIG_DIR="${AXORA_CONFIG_DIR:-$HOME/.axora}"
WRAPPER="/usr/local/bin/axora"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[axora]${RESET} $*"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET} $*"; }

echo ""
echo -e "${RED}Axora Uninstaller${RESET}"
echo ""

read -p "Remove Axora venv ($VENV_DIR)? [y/N] " -n 1 -r; echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  rm -rf "$VENV_DIR"
  success "Removed $VENV_DIR"
fi

read -p "Remove config dir ($CONFIG_DIR)? WARNING: deletes API keys! [y/N] " -n 1 -r; echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  rm -rf "$CONFIG_DIR"
  success "Removed $CONFIG_DIR"
fi

# Remove wrapper
if [[ -f "$WRAPPER" ]]; then
  if [[ -w "/usr/local/bin" ]]; then
    rm "$WRAPPER"
  else
    sudo rm "$WRAPPER" 2>/dev/null || warn "Could not remove $WRAPPER (try sudo)"
  fi
  success "Removed $WRAPPER"
fi

# Remove shell lines
for RC in "$HOME/.bashrc" "$HOME/.zshrc"; do
  if [[ -f "$RC" ]] && grep -q "Axora CLI Agent" "$RC" 2>/dev/null; then
    # Remove the block
    sed -i '/# Axora CLI Agent/,/^$/d' "$RC" 2>/dev/null || \
      warn "Could not auto-clean $RC — remove the Axora block manually"
    success "Cleaned $RC"
  fi
done

echo ""
echo -e "${GREEN}Axora uninstalled.${RESET}"
