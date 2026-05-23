# Checkpoint 82 - Live GitHub Install and Update Verification

## Scope
- Exercised the published GitHub lifecycle path from a clean terminal install/update flow.
- Verified the one-line installer pulls `MatthewLopez1990/AegisAgent` on `main`, writes the `aegis` shim, and prints the terminal run/update commands.
- Fixed the approved update card so it reports the active workspace, external git action, and workspace mutation state accurately.
- Added CLI lifecycle preflight guards for wrong remotes and dirty checkouts before an approved update can pull.
- Allowed shell install/update scripts to treat HTTPS and SSH GitHub origins for `MatthewLopez1990/AegisAgent` as the same canonical repo.
- Rechecked that install/update remains terminal-first: no browser auto-launch and no gateway start.

## Safety
- Used isolated `AEGIS_INSTALL_DIR` and `AEGIS_BIN_DIR` paths for live smoke runs.
- Kept GitHub clone/fetch/pull as the only external action, with update execution behind explicit approval.

## Verification
- Ran the raw GitHub installer from `https://raw.githubusercontent.com/MatthewLopez1990/AegisAgent/main/scripts/install.sh`.
- Confirmed the installed shim resolves to the cloned checkout and exposes terminal activation, health, and update commands.
- Ran installed-runtime smoke: `aegis activation`, `aegis health`, `aegis update --approved`, and `aegis activation` after update.
- Re-ran focused CLI/TUI lifecycle tests that cover update preview, approved pull, clean formatted TUI output, audit receipts, and browser-off safety.
- Re-ran shell syntax checks for `scripts/install.sh` and `scripts/update.sh`.
