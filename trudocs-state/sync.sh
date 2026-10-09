#!/usr/bin/env bash
# Refresh the distributable copies inside this skill from the live Karnataka code.
# Run it from anywhere before you hand the skill folder to another state's team:
#
#     .claude/skills/trudocs-state/sync.sh
#
# Copies:
#   frontend-v2/                        -> frontend-shell/    (minus node_modules, dist)
#   Swarnal/BBMPReceipt/scraper.py      -> backend-kit/examples/bbmp_receipt/scraper.py
# The kit modules (backend-kit/kit/) and examples/bbmp_receipt/routes.py are authored here,
# not copied — they are the generalised versions.
set -euo pipefail

SKILL="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SKILL/../../.." && pwd)"

[ -d "$ROOT/frontend-v2/src" ] || { echo "expected $ROOT/frontend-v2/src — is this skill inside the Karnataka repo?"; exit 1; }

rsync -a --delete \
  --exclude node_modules --exclude dist --exclude .DS_Store \
  "$ROOT/frontend-v2/" "$SKILL/frontend-shell/"

# New-state layout is backend/tools/bbmp_receipt/, not Swarnal/BBMPReceipt/ — fix the docstring paths.
sed -e 's#python -m Swarnal\.BBMPReceipt\.scraper#python -m backend.tools.bbmp_receipt.scraper#g' \
    -e 's#from BBMPReceipt\.scraper import#from backend.tools.bbmp_receipt.scraper import#g' \
    -e 's#Swarnal/BBMPReceipt/scraper\.py#backend/tools/bbmp_receipt/scraper.py#g' \
    -e 's#backend/rtc_routes\.py#backend/tools/bbmp_receipt/routes.py#g' \
    "$ROOT/Swarnal/BBMPReceipt/scraper.py" > "$SKILL/backend-kit/examples/bbmp_receipt/scraper.py"

echo "synced frontend-shell/ ($(find "$SKILL/frontend-shell" -type f | wc -l | tr -d ' ') files) and examples/bbmp_receipt/scraper.py"
