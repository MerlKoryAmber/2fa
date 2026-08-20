#!/bin/sh
set -e

if [ ! -f /etc/nginx/ssl/cert.pem ] || [ ! -f /etc/nginx/ssl/key.pem ]; then
  mkdir -p /etc/nginx/ssl
  openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/key.pem \
    -out /etc/nginx/ssl/cert.pem \
    -subj "/CN=mk2fa.local/O=MK2FA/C=RU"
fi

if [ -f /etc/nginx/ssl/root-ca.crt ]; then
  cp /etc/nginx/ssl/root-ca.crt /usr/local/share/ca-certificates/mk2fa-root.crt
  update-ca-certificates 2>/dev/null || true
fi

NS=$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf)
if [ -z "$NS" ]; then
  NS="127.0.0.11"
fi
sed "s/@RESOLVER@/$NS/g" /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

(
  while true; do
    sleep 2
    if [ -f /etc/nginx/ssl/reload.request ]; then
      nginx -s reload 2>/dev/null || true
      rm -f /etc/nginx/ssl/reload.request
      if [ -f /etc/nginx/ssl/root-ca.crt ]; then
        cp /etc/nginx/ssl/root-ca.crt /usr/local/share/ca-certificates/mk2fa-root.crt
        update-ca-certificates 2>/dev/null || true
      fi
    fi
  done
) &

exec nginx -g 'daemon off;'
