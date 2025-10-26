#!/usr/bin/env bash
set -euo pipefail
BLUEPRINT="docs/tradingbot_technical_blueprint.md"
EXPECTED_HASH_FILE="docs/.blueprint.sha256"
sha256sum "$BLUEPRINT" | awk '{print $1}' > /tmp/blue.sha
if [[ ! -f "$EXPECTED_HASH_FILE" ]]; then
  echo "No pinned hash found; creating it now."
  cp /tmp/blue.sha "$EXPECTED_HASH_FILE"
  exit 0
fi
diff -q /tmp/blue.sha "$EXPECTED_HASH_FILE" >/dev/null || {
  echo "Blueprint changed without bumping governance!"
  echo "→ Update docs/.blueprint.sha256 en CHANGELOG.md"
  exit 1
}
