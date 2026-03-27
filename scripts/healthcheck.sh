#!/bin/bash
# Health check: verify API, DB, and nginx are responding
STATUS=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8100/api/v1/health)

if [ "$STATUS" = "200" ]; then
    echo "$(date): OK (HTTP $STATUS)"
else
    echo "$(date): ALERT — API returned HTTP $STATUS"
    # Restart if down
    systemctl restart lorcana-api
    echo "$(date): Restarted lorcana-api"
fi
