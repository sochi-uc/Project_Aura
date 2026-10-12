#!/bin/bash
# ==============================================================================
# scripts/health.sh — Project Aura System Health & Statistics Inspector
#
# Design Rationale:
# - Non-Privileged Telemetry: Older diagnostic scripts frequently relied on
#   interactive `sudo -u postgres psql` commands which risked password leakage
#   or required root privileges. This script runs a lightweight, unprivileged
#   asyncpg probe directly using the credentials declared in `.env`.
# - Dual-Scope Systemd Inspection: Checks both system-level and user-level systemd
#   units so services are accurately diagnosed regardless of deployment scope.
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Detect virtual environment Python interpreter if present
PYTHON_BIN="python3"
if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
fi

echo -e "\n🩺 \033[1;36mProject Aura Health Check\033[0m\n"

# ── 1. Check Systemd Units ──────────────────────────────────────────────────
# Iterates core daemons and timers across system and user scopes
echo -e "⚙️  \033[1;33mSystemd Services & Timers:\033[0m"
for srv in project-aura aura-bot aura-listener aura-worker.timer aura-digest.timer; do
    if systemctl is-active --quiet "$srv" 2>/dev/null || systemctl --user is-active --quiet "$srv" 2>/dev/null; then
        echo -e "   ✅ $srv: \033[32mActive\033[0m"
    else
        echo -e "   ⚪ $srv: \033[37mInactive/Not Configured\033[0m"
    fi
done

# ── 2. Database Probe (asyncpg) ─────────────────────────────────────────────
# Probes PostgreSQL without requiring sudo or interactive psql CLI tools
echo -e "\n📊 \033[1;33mDatabase Statistics:\033[0m"
STATS=$("$PYTHON_BIN" -c "
import asyncio, asyncpg, os
from dotenv import load_dotenv

# Load local environment configuration
load_dotenv('$SCRIPT_DIR/.env')

async def probe():
    url = os.environ.get('DATABASE_URL')
    if not url:
        return
    try:
        # Establish connection with a 5-second timeout to avoid hanging on network partitions
        conn = await asyncpg.connect(url, timeout=5)
        chats = await conn.fetchval('SELECT COUNT(*) FROM chats;')
        msgs = await conn.fetchval('SELECT COUNT(*) FROM raw_messages;')
        pending = await conn.fetchval('SELECT COUNT(*) FROM raw_messages WHERE processed_at IS NULL;')
        relevant = await conn.fetchval('SELECT COUNT(*) FROM message_relevance;')
        print(f'{chats}|{msgs}|{pending}|{relevant}')
        await conn.close()
    except Exception as e:
        print(f'ERR:{e}')

asyncio.run(probe())
" 2>/dev/null || true)

if [[ "$STATS" == ERR:* ]]; then
    echo -e "   ⚠️  Database Connection Error: ${STATS#ERR:}"
elif [ -n "$STATS" ]; then
    IFS='|' read -r total_chats total_msgs pending relevant <<< "$STATS"
    echo -e "   💬 Monitored Chats: \033[1;32m$total_chats\033[0m"
    echo -e "   📥 Total Messages: \033[1;32m$total_msgs\033[0m"
    echo -e "   ⏳ Worker Queue: \033[1;33m$pending\033[0m messages pending"
    echo -e "   🎯 Relevant Matches: \033[1;32m$relevant\033[0m"
else
    echo -e "   ℹ️  Database not reachable or DATABASE_URL not set in .env."
fi
echo ""
