#!/usr/bin/env bash
# Install test-server config. Uses conf.d only (loaded before sites-enabled) so this block wins.
# Run from repo root: ./nginx/install-docs-conf.d.sh

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF_SOURCE="$REPO_ROOT/nginx/test-server.textrp.io.conf"
CONF_DEST="/etc/nginx/conf.d/00-test-server.textrp.io.conf"
SITES_AVAILABLE="/etc/nginx/sites-available/test-server.textrp.io.conf"
SITES_ENABLED="/etc/nginx/sites-enabled/test-server.textrp.io.conf"

echo "Other conf.d files (may have conflicting server blocks):"
ls /etc/nginx/conf.d/*.conf 2>/dev/null || true

echo "Copying config to conf.d (loads first)..."
sudo cp "$CONF_SOURCE" "$CONF_DEST"

echo "Removing from sites-enabled to avoid duplicate..."
sudo rm -f "$SITES_ENABLED"

echo "Keeping a copy in sites-available for reference..."
sudo cp "$CONF_SOURCE" "$SITES_AVAILABLE"

echo "Testing and reloading nginx..."
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "Test from this host (localhost) - should show X-Test-Server-Block and 302 or 200:"
curl -sI "https://127.0.0.1/docs/" -k -H "Host: test-server.textrp.io" 2>/dev/null | head -15

echo ""
echo "If localhost works but test-server.textrp.io does not, a proxy/LB in front is returning 404."
echo "Test hostname: curl -sI https://test-server.textrp.io/docs/"
