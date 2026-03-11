#!/usr/bin/env bash
# Run on the server to see why /docs/ might not hit our server block.
# Usage: ./nginx/diagnose-docs-404.sh

set -e
echo "=== 1. Include order in nginx.conf ==="
grep -E "include|server_name|listen" /etc/nginx/nginx.conf | head -30

echo ""
echo "=== 2. conf.d and sites-enabled ==="
ls -la /etc/nginx/conf.d/ 2>/dev/null || true
ls -la /etc/nginx/sites-enabled/ 2>/dev/null || true

echo ""
echo "=== 3. Request to localhost with Host header (bypasses any front proxy) ==="
curl -sI "https://127.0.0.1/docs/" -k -H "Host: test-server.textrp.io" 2>/dev/null || true

echo ""
echo "=== 4. All 443 server blocks (from full config) ==="
sudo nginx -T 2>/dev/null | grep -E "listen.*443|server_name" | head -30
