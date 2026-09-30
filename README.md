# Music Scheduler

A web application for scheduling and playing music automatically on a Raspberry Pi. Supports downloading from YouTube, drag-and-drop playlist management, cron-like scheduling, and remote control via an Android app.

## Features

- **YouTube downloads** — single videos or entire playlists with real-time progress tracking
- **File uploads** — MP3, WAV, OGG, FLAC, AAC, M4A (up to 150MB)
- **Drag-and-drop playlist** — reorder songs, categorize as music or announcement
- **Scheduled playback** — set time + weekdays, supports one-time schedules
- **Playback controls** — play/pause, stop, seek, volume, shuffle, fade in/out
- **Android app** — remote control via Tailscale VPN (Capacitor WebView)
- **Persistent login** — remember token keeps sessions alive for 1 year
- **Auto-update yt-dlp** — nightly update at 3:00 AM (skipped while playing or downloading)

## Requirements

- Raspberry Pi 3B+ or newer (or any Linux machine). **Raspberry Pi OS 64-bit (Bookworm) recommended**
- Python 3.10+ (3.11 recommended) — current yt-dlp no longer supports older versions
- FFmpeg
- pygame (for audio output)
- A JavaScript runtime for YouTube downloads (see below)

### JavaScript runtime (required for YouTube)

Since late 2025 yt-dlp must run YouTube's JS challenges through an external runtime,
together with the `yt-dlp-ejs` package (installed by `yt-dlp[default]` in `requirements.txt`).

| `uname -m` | Runtime | Setup |
|---|---|---|
| `aarch64` (64-bit OS) | Deno ≥ 2.3 (default) | `curl -fsSL https://deno.land/install.sh \| sh` |
| `armv7l` (32-bit OS) | Node.js ≥ 22 (Deno has no armv7 build) | install Node 22, then set `YTDLP_JS_RUNTIME=node` in `.env` |

Check it works: `venv/bin/yt-dlp -F "https://www.youtube.com/watch?v=dQw4w9WgXcQ"` must list audio
formats without a "No supported JavaScript runtime" warning. Make sure the runtime is on the
`PATH` of the systemd service (see `music-scheduler.service`).

Optional settings live in `.env` — copy `.env.example`.

## Installation

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install python3-pip python3-pygame ffmpeg

# Clone the repo
git clone https://github.com/tuannm-1876/music-schedule.git
cd music-schedule

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt
cp .env.example .env   # optional settings

# Run migrations
python3 migrate_user.py              # Create admin user (save the password!)
python3 migrate_song_position.py     # Add position field to Song
python3 migrate_category.py          # Add category field
python3 migrate_delete_after_play.py # Add delete_after_play field
python3 migrate_one_time.py          # Add one_time field to Schedule
python3 migrate_schedule_volume.py   # Add volume field to Schedule
python3 migrate_remember_token.py    # Add remember_token field to User
```

## Usage

### Development

```bash
python3 app.py
```

### Production (recommended)

```bash
gunicorn --worker-class eventlet -w 1 --timeout 120 --bind 0.0.0.0:5000 wsgi:application
```

> **Note:** `-w 1` (single worker) is required because pygame audio can only run in one process.

### Run as systemd service

```bash
# Quick setup
./install_service.sh

# Or manually
sudo cp music-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable music-scheduler
sudo systemctl start music-scheduler
```

Access at: `http://<raspberry-pi-ip>:5000`

## Project Structure

```
├── app.py                  # Main Flask backend
├── youtube_downloader.py   # yt-dlp wrapper (runs yt-dlp as a child process)
├── secret_key_loader.py    # SECRET_KEY from .env, generated on first start if missing
├── tests/                  # pytest suite (pip install -r requirements-dev.txt)
├── wsgi.py                 # Gunicorn entry point
├── requirements.txt        # Python dependencies
├── install_service.sh      # Systemd service installer
├── music-scheduler.service # Systemd service file
├── migrate_*.py            # Database migration scripts
├── music/                  # Music files storage
├── instance/               # SQLite database
├── static/                 # Static files (CSS, JS, React build)
│   └── react/              # React frontend build output
├── templates/              # Jinja2 templates (legacy login)
└── frontend/               # React frontend source
    ├── src/
    │   ├── App.tsx         # Root component
    │   ├── components/     # UI components
    │   │   ├── dashboard/  # AddMusic, DiskUsage, DownloadProgress...
    │   │   ├── player/     # Player bar (fixed bottom)
    │   │   ├── playlist/   # Playlist with drag-and-drop
    │   │   ├── schedule/   # Schedule management
    │   │   └── ui/         # Button, Card, Input, Spinner...
    │   ├── contexts/       # Socket, Theme, Toast providers
    │   ├── lib/            # API client (axios), utilities
    │   ├── pages/          # Dashboard, LoginPage
    │   └── types/          # TypeScript type definitions
    └── android/            # Capacitor Android project (gitignored)
```

## Tech Stack

### Backend
- **Flask** + Flask-SocketIO (eventlet) — HTTP API + WebSocket real-time
- **SQLAlchemy** + SQLite — database
- **APScheduler** — cron-like scheduling
- **pygame** — audio playback
- **yt-dlp** — YouTube downloads, run as a low-priority child process so playback never stutters
- **Flask-WTF** — CSRF protection

### Frontend
- **React 19** + TypeScript + Vite
- **Tailwind CSS v4** — styling
- **Socket.IO Client** — real-time updates
- **Framer Motion** — animations
- **dnd-kit** — drag-and-drop
- **Axios** — HTTP client
- **Lucide React** — icons

### Mobile
- **Capacitor v8** — wraps React app as Android APK
- **Tailscale** — VPN for remote access to Pi

## Android App

The Android app connects directly to the Pi via Tailscale (WebView → `http://<tailscale-ip>:5000`).

```bash
cd frontend

# Build frontend
npm run build

# Sync and build APK
npx cap sync android
cd android
JAVA_HOME=/path/to/java-21 ./gradlew assembleDebug

# APK output: android/app/build/outputs/apk/debug/app-debug.apk
```

**Build requirements:** Node.js, Java 21, Android SDK 34.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No audio output | Check `alsamixer`, set 3.5mm output (`sudo raspi-config`) |
| "Thiếu JS runtime" / no audio formats | Install Deno or Node (see *JavaScript runtime*), check the service `PATH` |
| "YouTube chặn vì nghi là bot" | Export a cookies file from a secondary account, set `YTDLP_COOKIES_FILE` |
| Download errors after YouTube changes | Press *Cập nhật* in the yt-dlp card, or `venv/bin/pip install -U "yt-dlp[default]"` |
| Stuck on an old yt-dlp version | Python < 3.10 — upgrade to Raspberry Pi OS Bookworm |
| Audio stutters | `journalctl -u music-scheduler \| grep -i underrun`; enable zram on 1GB boards |
| Forgot password | `python3 migrate_user.py` (generates a new password) |
| Service not running | `sudo journalctl -u music-scheduler -f` |
| Database issues | Check files in `instance/` directory |

## License

MIT License
