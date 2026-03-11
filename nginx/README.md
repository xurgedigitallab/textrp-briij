# Nginx configs for Synapse (briij)

Drop-in server blocks for proxying Matrix traffic to Synapse on port 8008.

## test-server.textrp.io

- **File:** `test-server.textrp.io.conf`
- **Backend:** `http://127.0.0.1:8008`
- **Ports:** 80 (redirect to HTTPS + ACME for certbot), 443 (client), 8448 (federation)

### Setup

1. Ensure SSL certificates exist (e.g. from a previous certbot run). If not, use the HTTP-only config first, run `sudo certbot --nginx -d test-server.textrp.io`, then switch to this config.

2. Install the config:
   ```sh
   sudo cp nginx/test-server.textrp.io.conf /etc/nginx/sites-available/
   sudo ln -s /etc/nginx/sites-available/test-server.textrp.io.conf /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```

3. In `homeserver.yaml`, set `x_forwarded: true` for the listener on port 8008 (see [reverse_proxy.md](../docs/reverse_proxy.md)).

### DNS

Point `test-server.textrp.io` (A/AAAA) to this host. Port 80 is used for redirects and certbot renewal; 443 and 8448 for Matrix.
