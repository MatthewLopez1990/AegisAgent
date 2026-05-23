#!/usr/bin/env sh
set -eu

BRANCH="${AEGIS_BRANCH:-main}"
INSTALL_DIR="${AEGIS_INSTALL_DIR:-$HOME/.aegis-agent}"
BIN_DIR="${AEGIS_BIN_DIR:-$HOME/.local/bin}"
COMMAND_NAME="${AEGIS_COMMAND_NAME:-aegis}"

if [ ! -d "$INSTALL_DIR/.git" ]; then
  echo "AegisAgent checkout not found at $INSTALL_DIR" >&2
  echo "Install first with scripts/install.sh or the README one-line installer." >&2
  exit 1
fi

git -C "$INSTALL_DIR" fetch origin "$BRANCH"
git -C "$INSTALL_DIR" checkout "$BRANCH"
git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"

cd "$INSTALL_DIR"
PYTHONPATH=src python3 -m aegisagent install shim --approved --bin-dir "$BIN_DIR" --name "$COMMAND_NAME"

echo ""
echo "AegisAgent updated."
echo "Run: $COMMAND_NAME"
echo "Update again: $COMMAND_NAME update --approved"
