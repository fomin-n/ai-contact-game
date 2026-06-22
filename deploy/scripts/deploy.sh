#!/usr/bin/env bash
# Deploy ai-contact-game Telegram bot to the production VPS.
# Usage: ./deploy/scripts/deploy.sh
# Requires: SSH key at ~/.ssh/vps_glados_ed25519, server at 65.109.139.84

set -euo pipefail

SERVER="${SERVER:-glados@65.109.139.84}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/vps_glados_ed25519}"
APP_DIR="${APP_DIR:-/opt/ai-contact-game}"
SERVICE_NAME="ai-contact-game"
REPO_URL="${REPO_URL:-$(git remote get-url origin 2>/dev/null || echo '')}"

if [[ -z "$REPO_URL" ]]; then
    echo "ERROR: Cannot determine repo URL. Set REPO_URL or ensure git remote origin is configured." >&2
    exit 2
fi

ssh -i "$SSH_KEY" "$SERVER" \
    "REPO_URL='$REPO_URL' APP_DIR='$APP_DIR' SERVICE_NAME='$SERVICE_NAME' bash -s" <<'REMOTE'
set -euo pipefail

echo "=== Deploying $SERVICE_NAME to $APP_DIR ==="

# Clone or update the repository
if [[ -d "$APP_DIR/.git" ]]; then
    echo "Pulling latest changes..."
    git -C "$APP_DIR" fetch --all --prune
    git -C "$APP_DIR" pull --ff-only
else
    echo "Cloning $REPO_URL -> $APP_DIR ..."
    git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

# Record deployed revision
git rev-parse HEAD > "$APP_DIR/.deploy-revision"
echo "Deployed revision: $(cat .deploy-revision)"

# Create virtualenv if needed
if [[ ! -d .venv ]]; then
    echo "Creating virtualenv..."
    python3 -m venv .venv
fi

# Install dependencies
echo "Installing Python dependencies..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

# Check .env exists
if [[ ! -f "$APP_DIR/.env" ]]; then
    echo ""
    echo "ERROR: $APP_DIR/.env not found."
    echo "Create it from .env.example and fill in:"
    echo "  AI_CONTACT_TELEGRAM_BOT_TOKEN"
    echo "  MISTRAL_API_KEY"
    echo "  ENABLE_PHOENIX_TRACING=true  (optional)"
    echo "  PHOENIX_COLLECTOR_ENDPOINT   (optional)"
    exit 5
fi

# Install systemd service
echo "Installing systemd service..."
sudo cp "$APP_DIR/deploy/systemd/$SERVICE_NAME.service" "/etc/systemd/system/$SERVICE_NAME.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

# Restart service
echo "Restarting service..."
sudo systemctl restart "$SERVICE_NAME"

# Wait a moment and check status
sleep 3
echo ""
echo "=== Service status ==="
sudo systemctl status "$SERVICE_NAME" --no-pager -l

echo ""
echo "=== Recent logs ==="
sudo journalctl -u "$SERVICE_NAME" -n 20 --no-pager

echo ""
echo "=== Deployment complete ==="
REMOTE

echo "Deploy script finished."
echo ""
echo "Management commands on the server:"
echo "  sudo systemctl status ai-contact-game"
echo "  sudo journalctl -u ai-contact-game -f"
echo "  sudo systemctl restart ai-contact-game"
echo "  sudo systemctl stop ai-contact-game"
echo "  cd /opt/ai-contact-game && git pull && sudo systemctl restart ai-contact-game"
