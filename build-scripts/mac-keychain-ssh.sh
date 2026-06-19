#!/usr/bin/env bash
# Unlocks the login keychain for codesign access over SSH.
# Usage: bash build-scripts/mac-keychain-ssh.sh
# Reads KEYCHAIN_PASSWORD from .env if set, otherwise prompts.
set -euo pipefail

KEYCHAIN="${HOME}/Library/Keychains/login.keychain-db"

# Load KEYCHAIN_PASSWORD from .env if present and not already in env.
if [ -z "${KEYCHAIN_PASSWORD:-}" ] && [ -f "$(dirname "$0")/../.env" ]; then
  KEYCHAIN_PASSWORD=$(grep -E '^KEYCHAIN_PASSWORD=' "$(dirname "$0")/../.env" | cut -d= -f2- | tr -d '"' | tr -d "'")
fi

if [ -z "${KEYCHAIN_PASSWORD:-}" ]; then
  echo -n "Keychain password: "
  read -rs KEYCHAIN_PASSWORD
  echo
fi

security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
# Keep it unlocked for the duration of the session (no auto-lock timeout).
security set-keychain-settings "$KEYCHAIN"
echo "Keychain unlocked: $KEYCHAIN"
