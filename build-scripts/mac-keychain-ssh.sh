#!/usr/bin/env bash
# Unlocks the login keychain AND grants codesign access to the signing key,
# which is required when running codesign over SSH (fixes errSecInternalComponent).
# Usage: bash build-scripts/mac-keychain-ssh.sh
# Reads KEYCHAIN_PASSWORD from .env if not already in the environment.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
KEYCHAIN="${KEYCHAIN_PATH:-${HOME}/Library/Keychains/login.keychain-db}"

if [ -z "${KEYCHAIN_PASSWORD:-}" ] && [ -f "$ENV_FILE" ]; then
  line="$(grep -E '^KEYCHAIN_PASSWORD=' "$ENV_FILE" || true)"
  if [ -n "$line" ]; then
    KEYCHAIN_PASSWORD="${line#KEYCHAIN_PASSWORD=}"
    KEYCHAIN_PASSWORD="${KEYCHAIN_PASSWORD%\"}"; KEYCHAIN_PASSWORD="${KEYCHAIN_PASSWORD#\"}"
    KEYCHAIN_PASSWORD="${KEYCHAIN_PASSWORD%\'}"; KEYCHAIN_PASSWORD="${KEYCHAIN_PASSWORD#\'}"
  fi
fi

if [ -z "${KEYCHAIN_PASSWORD:-}" ]; then
  if [ -t 0 ]; then
    printf 'Keychain password: '
    read -rs KEYCHAIN_PASSWORD
    printf '\n'
  else
    echo "ERROR: KEYCHAIN_PASSWORD not set (add it to .env) and no TTY to prompt." >&2
    exit 1
  fi
fi

if [ ! -f "$KEYCHAIN" ]; then
  echo "ERROR: keychain not found: $KEYCHAIN" >&2
  exit 1
fi

echo "Unlocking $KEYCHAIN ..."
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"

# Stop the keychain auto-relocking mid-build.
security set-keychain-settings "$KEYCHAIN"

# Grant codesign/security tools non-interactive access to the private key.
# This is what actually fixes errSecInternalComponent over SSH.
echo "Granting codesign access to signing key ..."
security set-key-partition-list \
  -S apple-tool:,apple:,codesign: \
  -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN" >/dev/null

echo "Keychain ready for signing: $KEYCHAIN"
