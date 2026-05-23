#!/usr/bin/env sh
set -eu

REPO_URL="${AEGIS_REPO_URL:-https://github.com/MatthewLopez1990/AegisAgent.git}"
BRANCH="${AEGIS_BRANCH:-main}"
INSTALL_DIR="${AEGIS_INSTALL_DIR:-$HOME/.aegis-agent}"
BIN_DIR="${AEGIS_BIN_DIR:-$HOME/.local/bin}"
COMMAND_NAME="${AEGIS_COMMAND_NAME:-aegis}"

need_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 1
  fi
}

need_command git
need_command python3

mkdir -p "$BIN_DIR"

if [ -d "$INSTALL_DIR/.git" ]; then
  git -C "$INSTALL_DIR" fetch origin "$BRANCH"
  git -C "$INSTALL_DIR" checkout "$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
else
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
PYTHONPATH=src python3 -m aegisagent install shim --approved --bin-dir "$BIN_DIR" --name "$COMMAND_NAME"

echo ""
echo "AegisAgent installed."
echo "Run: $COMMAND_NAME"
echo "Update: $COMMAND_NAME update --approved"
echo "If needed, add this to your shell profile:"
echo "  export PATH=\"$BIN_DIR:\$PATH\""
