#!/usr/bin/env sh
set -eu

BRANCH="${AEGIS_BRANCH:-main}"
INSTALL_DIR="${AEGIS_INSTALL_DIR:-$HOME/.aegis-agent}"
BIN_DIR="${AEGIS_BIN_DIR:-$HOME/.local/bin}"
COMMAND_NAME="${AEGIS_COMMAND_NAME:-aegis}"
REPO_URL="${AEGIS_REPO_URL:-https://github.com/MatthewLopez1990/AegisAgent.git}"
PYTHON="${AEGIS_PYTHON:-python3}"

need_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 1
  fi
}

require_python_version() {
  "$PYTHON" - <<'PY'
import sys

minimum = (3, 12)
if sys.version_info < minimum:
    version = ".".join(str(part) for part in sys.version_info[:3])
    sys.stderr.write("python3 3.12 or newer is required; found {}\n".format(version))
    raise SystemExit(1)
PY
}

validate_branch() {
  case "$BRANCH" in
    ""|-*|.|..|HEAD|*..*|*//*|*/|*.|*.lock|*@{*|*\\*|*~*|*^*|*:*|*[\?\*\[]*|*[\ \	]*)
      echo "invalid AEGIS_BRANCH: $BRANCH" >&2
      exit 1
      ;;
  esac
  if ! git check-ref-format --branch "$BRANCH" >/dev/null 2>&1; then
    echo "invalid AEGIS_BRANCH: $BRANCH" >&2
    exit 1
  fi
}

canonical_repo_url() {
  case "$1" in
    git@github.com:*)
      printf 'https://github.com/%s\n' "${1#git@github.com:}"
      ;;
    ssh://git@github.com/*)
      printf 'https://github.com/%s\n' "${1#ssh://git@github.com/}"
      ;;
    */)
      printf '%s\n' "${1%/}"
      ;;
    *)
      printf '%s\n' "$1"
      ;;
  esac
}

if [ ! -d "$INSTALL_DIR/.git" ]; then
  echo "AegisAgent checkout not found at $INSTALL_DIR" >&2
  echo "Install first with scripts/install.sh or the README one-line installer." >&2
  exit 1
fi

need_command git
need_command "$PYTHON"
require_python_version
validate_branch

current_url="$(git -C "$INSTALL_DIR" remote get-url origin 2>/dev/null || true)"
current_canonical="$(canonical_repo_url "$current_url")"
expected_canonical="$(canonical_repo_url "$REPO_URL")"
if [ "$current_canonical" != "$expected_canonical" ]; then
  echo "refusing to update $INSTALL_DIR because origin is not $REPO_URL" >&2
  echo "current origin: ${current_url:-missing}" >&2
  exit 1
fi

if [ -n "$(git -C "$INSTALL_DIR" status --porcelain)" ]; then
  echo "refusing to update dirty checkout at $INSTALL_DIR" >&2
  exit 1
fi

git -C "$INSTALL_DIR" fetch origin "$BRANCH"
git -C "$INSTALL_DIR" checkout "$BRANCH"
git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"

cd "$INSTALL_DIR"
PYTHONPATH=src "$PYTHON" -m aegisagent install shim --approved --bin-dir "$BIN_DIR" --name "$COMMAND_NAME"

echo ""
echo "AegisAgent updated."
echo "Run: $COMMAND_NAME"
echo "Verify: $COMMAND_NAME health && $COMMAND_NAME audit verify"
echo "Update again: $COMMAND_NAME update --approved"
