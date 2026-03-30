#!/usr/bin/env bash
set -euo pipefail

# Usage:
# DOMAIN=corp.mms.com ./scripts/setup_named_tunnel.sh

TUNNEL_NAME="${TUNNEL_NAME:-material-management}"
SUBDOMAIN="${SUBDOMAIN:-wzgl}"
DOMAIN="${DOMAIN:-}"

if [[ -z "${DOMAIN}" ]]; then
  echo "ERROR: DOMAIN is required. Example: DOMAIN=corp.mms.com ./scripts/setup_named_tunnel.sh"
  exit 1
fi

HOSTNAME="${SUBDOMAIN}.${DOMAIN}"

echo "[1/5] Login to Cloudflare (browser auth may open)..."
cloudflared tunnel login

echo "[2/5] Create tunnel if not exists: ${TUNNEL_NAME}"
if ! cloudflared tunnel list | rg -q "${TUNNEL_NAME}"; then
  cloudflared tunnel create "${TUNNEL_NAME}"
else
  echo "Tunnel already exists, skip create."
fi

echo "[3/5] Route DNS: ${HOSTNAME}"
cloudflared tunnel route dns "${TUNNEL_NAME}" "${HOSTNAME}"

echo "[4/5] Ensure ~/.cloudflared/config.yml exists"
mkdir -p "${HOME}/.cloudflared"
TUNNEL_ID="$(cloudflared tunnel list | rg "${TUNNEL_NAME}" --no-line-number | awk '{print $1}' | head -n 1)"
if [[ -z "${TUNNEL_ID}" ]]; then
  echo "ERROR: Cannot resolve tunnel id for ${TUNNEL_NAME}"
  exit 1
fi
cat > "${HOME}/.cloudflared/config.yml" <<EOF
tunnel: ${TUNNEL_NAME}
credentials-file: ${HOME}/.cloudflared/${TUNNEL_ID}.json
ingress:
  - hostname: ${HOSTNAME}
    service: http://localhost:8501
  - service: http_status:404
EOF

echo "[5/5] Done. Start tunnel:"
echo "cloudflared tunnel run ${TUNNEL_NAME}"
echo "Then set in .env:"
echo "APP_HOME_URL=https://${HOSTNAME}/"
echo "FEISHU_REDIRECT_URI=https://${HOSTNAME}/"
