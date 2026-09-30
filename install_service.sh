#!/usr/bin/env bash
# Install Music Scheduler as a systemd service for the current user and directory.
# Usage: ./install_service.sh   (run from the project directory, as your normal user)
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_USER="$(id -un)"
APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6)"
SERVICE=music-scheduler

if [ "$APP_USER" = "root" ]; then
    echo "Run this as the user that should own the service, not root (sudo is used where needed)." >&2
    exit 1
fi

echo "==> Python virtual environment"
if [ ! -x "$APP_DIR/venv/bin/python" ]; then
    python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/python" -c 'import sys; sys.exit(sys.version_info < (3, 10))' || {
    echo "Python 3.10+ is required (yt-dlp dropped older versions). Upgrade to Raspberry Pi OS Bookworm." >&2
    exit 1
}
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo "    created .env from .env.example"
fi

if ! command -v deno >/dev/null 2>&1 && [ ! -x "$APP_HOME/.deno/bin/deno" ] && ! command -v node >/dev/null 2>&1; then
    echo "WARNING: no JavaScript runtime found - YouTube downloads will fail." >&2
    echo "         64-bit OS: curl -fsSL https://deno.land/install.sh | sh" >&2
    echo "         32-bit OS: install Node.js 22 and set YTDLP_JS_RUNTIME=node in .env" >&2
fi

echo "==> systemd unit for user '$APP_USER' in $APP_DIR"
sed -e "s|^User=.*|User=$APP_USER|" \
    -e "s|/home/pi/schedule-music|$APP_DIR|g" \
    -e "s|/home/pi|$APP_HOME|g" \
    "$APP_DIR/music-scheduler.service" | sudo tee "/etc/systemd/system/$SERVICE.service" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl restart "$SERVICE"
sleep 3
sudo systemctl --no-pager --lines=5 status "$SERVICE" || true

if [ -f "$APP_DIR/instance/initial-admin-password.txt" ]; then
    echo
    echo "Admin password: cat $APP_DIR/instance/initial-admin-password.txt  (delete it after saving)"
fi
echo "Logs: sudo journalctl -u $SERVICE -f"
echo "Open: http://$(hostname -I 2>/dev/null | awk '{print $1}'):5000"
