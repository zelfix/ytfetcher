#!/bin/sh
set -euo pipefail

SERVER_NAME=${SERVER_NAME:-_}
ENABLE_TLS=${ENABLE_TLS:-false}
TLS_CERT_PATH=${TLS_CERT_PATH:-/etc/letsencrypt/live/${SERVER_NAME}/fullchain.pem}
TLS_KEY_PATH=${TLS_KEY_PATH:-/etc/letsencrypt/live/${SERVER_NAME}/privkey.pem}
DOWNLOAD_ROOT=${DOWNLOAD_ROOT:-/srv/ytfetcher/downloads}

if [ "$ENABLE_TLS" = "true" ] && { [ ! -f "$TLS_CERT_PATH" ] || [ ! -f "$TLS_KEY_PATH" ]; }; then
  echo "[entrypoint] TLS requested but certificate or key not found; continuing with HTTP" >&2
  ENABLE_TLS=false
fi

mkdir -p /var/www/certbot/.well-known/acme-challenge
mkdir -p "$DOWNLOAD_ROOT"

cat > /etc/nginx/nginx.conf <<'EOF_CONF'
events {}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    tcp_nopush    on;
    keepalive_timeout 65;
EOF_CONF

if [ "$ENABLE_TLS" = "true" ]; then
cat >> /etc/nginx/nginx.conf <<EOF_CONF

    server {
        listen 80;
        server_name $SERVER_NAME;

        location /.well-known/acme-challenge/ {
            alias /var/www/certbot/.well-known/acme-challenge/;
        }

        location /downloads/ {
            return 301 https://\$host\$request_uri;
        }

        location / {
            return 301 https://\$host\$request_uri;
        }
    }

    server {
        listen 443 ssl;
        server_name $SERVER_NAME;

        ssl_certificate $TLS_CERT_PATH;
        ssl_certificate_key $TLS_KEY_PATH;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        location /.well-known/acme-challenge/ {
            alias /var/www/certbot/.well-known/acme-challenge/;
        }

        location /downloads/ {
            alias $DOWNLOAD_ROOT/;
            autoindex off;
            add_header Content-Disposition "attachment";
            add_header Cache-Control "public, max-age=604800";
        }

        location / {
            return 204;
        }
    }
EOF_CONF
else
cat >> /etc/nginx/nginx.conf <<EOF_CONF

    server {
        listen 80;
        server_name $SERVER_NAME;

        location /.well-known/acme-challenge/ {
            alias /var/www/certbot/.well-known/acme-challenge/;
        }

        location /downloads/ {
            alias $DOWNLOAD_ROOT/;
            autoindex off;
            add_header Content-Disposition "attachment";
            add_header Cache-Control "public, max-age=604800";
        }

        location / {
            return 204;
        }
    }
EOF_CONF
fi

cat >> /etc/nginx/nginx.conf <<'EOF_CONF'
}
EOF_CONF

exec supervisord -c /etc/supervisor/conf.d/supervisord.conf
