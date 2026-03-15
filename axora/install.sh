#!/usr/bin/env bash
# ============================================================
#  Axora CLI Agent — Automated Installer
#  Usage: bash install.sh [--dev] [--venv-dir <path>]
# ============================================================
set -euo pipefail

AXORA_VERSION="1.0.0"
VENV_DIR="${AXORA_VENV_DIR:-$HOME/.axora/venv}"
CONFIG_DIR="${AXORA_CONFIG_DIR:-$HOME/.axora}"
LOG_DIR="$CONFIG_DIR/logs"
DEV_MODE=false

# ─── Colors ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[axora]${RESET} $*"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET} $*"; }
error()   { echo -e "${RED}✗ ERROR:${RESET} $*" >&2; exit 1; }

# ─── Parse args ──────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --dev)        DEV_MODE=true ;;
    --venv-dir)   VENV_DIR="$2"; shift ;;
    --config-dir) CONFIG_DIR="$2"; LOG_DIR="$CONFIG_DIR/logs"; shift ;;
    -h|--help)
      echo "Usage: bash install.sh [--dev] [--venv-dir PATH] [--config-dir PATH]"
      exit 0 ;;
  esac
  shift
done

# ─── Banner ──────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}"
cat << 'EOF'
     █████╗ ██╗  ██╗ ██████╗ ██████╗  █████╗
    ██╔══██╗╚██╗██╔╝██╔═══██╗██╔══██╗██╔══██╗
    ███████║ ╚███╔╝ ██║   ██║██████╔╝███████║
    ██╔══██║ ██╔██╗ ██║   ██║██╔══██╗██╔══██║
    ██║  ██║██╔╝ ██╗╚██████╔╝██║  ██║██║  ██║
    ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
EOF
echo -e "${RESET}"
echo -e "    ${BOLD}Axora CLI Agent v${AXORA_VERSION} Installer${RESET}"
echo ""

# ─── Prerequisites ───────────────────────────────────────────
info "Checking prerequisites..."

# Python check
if command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null; then
  PYTHON=python
else
  error "Python 3.10+ is required but not found. Install from https://python.org"
fi

PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")

if [[ $PY_MAJOR -lt 3 ]] || [[ $PY_MAJOR -eq 3 && $PY_MINOR -lt 10 ]]; then
  error "Python 3.10+ required, found $PY_VERSION"
fi
success "Python $PY_VERSION detected"

# pip check
if ! $PYTHON -m pip --version &>/dev/null; then
  error "pip not found. Install pip and retry."
fi
success "pip available"

# ─── Directories ─────────────────────────────────────────────
info "Setting up directories..."
mkdir -p "$CONFIG_DIR" "$LOG_DIR"
chmod 700 "$CONFIG_DIR"
success "Config dir: $CONFIG_DIR"
success "Log dir:    $LOG_DIR"

# ─── Virtual Environment ─────────────────────────────────────
info "Creating virtual environment at $VENV_DIR ..."
if [[ -d "$VENV_DIR" ]]; then
  warn "venv already exists at $VENV_DIR — reusing"
else
  $PYTHON -m venv "$VENV_DIR"
  success "Virtual environment created"
fi

# Activate
source "$VENV_DIR/bin/activate"

# Upgrade pip/wheel
info "Upgrading pip and build tools..."
pip install --quiet --upgrade pip wheel setuptools

# ─── Install Axora ───────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info "Installing Axora and dependencies..."
if [[ "$DEV_MODE" == "true" ]]; then
  pip install -e "$SCRIPT_DIR[dev]"
  success "Installed in development (editable) mode"
else
  pip install "$SCRIPT_DIR"
  success "Installed Axora v${AXORA_VERSION}"
fi

# ─── Shell Integration ───────────────────────────────────────
info "Setting up shell integration..."

AXORA_BIN="$VENV_DIR/bin/axora"
SHELL_RC=""

if [[ -n "${BASH_VERSION:-}" ]] || [[ "$SHELL" == *bash* ]]; then
  SHELL_RC="$HOME/.bashrc"
elif [[ -n "${ZSH_VERSION:-}" ]] || [[ "$SHELL" == *zsh* ]]; then
  SHELL_RC="$HOME/.zshrc"
fi

EXPORT_LINES=$(cat <<EOF

# Axora CLI Agent
export AXORA_CONFIG_DIR="$CONFIG_DIR"
export PATH="$VENV_DIR/bin:\$PATH"
EOF
)

if [[ -n "$SHELL_RC" ]]; then
  if ! grep -q "Axora CLI Agent" "$SHELL_RC" 2>/dev/null; then
    echo "$EXPORT_LINES" >> "$SHELL_RC"
    success "Shell integration added to $SHELL_RC"
  else
    warn "Shell integration already present in $SHELL_RC"
  fi
else
  warn "Could not detect shell rc file. Add manually:"
  echo -e "${YELLOW}$EXPORT_LINES${RESET}"
fi

# ─── Wrapper script to /usr/local/bin (optional) ─────────────
WRAPPER="/usr/local/bin/axora"
if [[ -w "/usr/local/bin" ]] || command -v sudo &>/dev/null; then
  info "Installing global 'axora' wrapper to /usr/local/bin ..."
  WRAPPER_CONTENT="#!/usr/bin/env bash
export AXORA_CONFIG_DIR=\"$CONFIG_DIR\"
exec \"$AXORA_BIN\" \"\$@\"
"
  if [[ -w "/usr/local/bin" ]]; then
    echo "$WRAPPER_CONTENT" > "$WRAPPER"
    chmod +x "$WRAPPER"
    success "Global wrapper installed: $WRAPPER"
  else
    echo "$WRAPPER_CONTENT" | sudo tee "$WRAPPER" > /dev/null
    sudo chmod +x "$WRAPPER"
    success "Global wrapper installed: $WRAPPER (via sudo)"
  fi
fi

# ─── Write default config ────────────────────────────────────
DEFAULT_CONFIG="$CONFIG_DIR/config.yaml"
if [[ ! -f "$DEFAULT_CONFIG" ]]; then
  info "Writing default configuration..."
  cat > "$DEFAULT_CONFIG" <<YAML
server:
  host: 127.0.0.1
  port: 8765
models: {}
endpoints: {}
chat:
  system_prompt: "You are Axora, a helpful and concise AI assistant."
  max_history: 50
paths:
  log_file: $LOG_DIR/axora.log
  pid_file: /tmp/axora.pid
logging:
  level: INFO
  max_bytes: 5242880
  backup_count: 3
YAML
  chmod 600 "$DEFAULT_CONFIG"
  success "Default config written to $DEFAULT_CONFIG"
else
  warn "Config already exists at $DEFAULT_CONFIG — skipping"
fi

# ─── Verify installation ─────────────────────────────────────
info "Verifying installation..."
if "$AXORA_BIN" --version &>/dev/null; then
  VER=$("$AXORA_BIN" --version 2>&1)
  success "axora binary verified: $VER"
else
  error "Installation verification failed. Check $LOG_DIR/install.log"
fi

# ─── Done ────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  Axora v${AXORA_VERSION} installed successfully!${RESET}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${CYAN}Next steps:${RESET}"
echo -e "  ${BOLD}1.${RESET} Reload your shell:  ${CYAN}source $SHELL_RC${RESET}"
echo -e "  ${BOLD}2.${RESET} Run setup wizard:   ${CYAN}axora init${RESET}"
echo -e "  ${BOLD}3.${RESET} Start the agent:    ${CYAN}axora agent start${RESET}"
echo -e "  ${BOLD}4.${RESET} Chat with AI:       ${CYAN}axora chat${RESET}"
echo -e "  ${BOLD}5.${RESET} Check status:       ${CYAN}axora status${RESET}"
echo ""
echo -e "  ${BOLD}Docs:${RESET}  axora --help"
echo -e "  ${BOLD}Logs:${RESET}  $LOG_DIR/axora.log"
echo ""
