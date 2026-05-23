# Checkpoint 76 - Terminal Install and Update

## Scope
- Added terminal lifecycle commands for macOS/Linux operators.
- `aegisagent install` previews the shim target, PATH hint, run command, and update command without writing files.
- `aegisagent install shim --approved` writes an executable `aegis` shell shim to `~/.local/bin` by default.
- `aegisagent update --approved` pulls the configured GitHub branch with `git pull --ff-only origin main`.
- TUI commands `/install`, `/install shim | approve`, `/update`, and `/update | approve` expose the same lifecycle controls.

## Safety
- Preview paths are metadata-only and report `browser_auto_launch=false`.
- Install writes only after explicit approval and records a lifecycle audit receipt.
- Update runs only after explicit approval and delegates to the existing approval-gated typed git remote pull path.
- Update uses fast-forward-only pulls to avoid merge commits or destructive local rewrites.

## Verification
- Added CLI coverage for install status, approval-gated shim creation, and update preview.
- Added TUI slash palette and dispatch coverage for install/update lifecycle commands.
- Added lifecycle update coverage through a temporary local Git remote.
