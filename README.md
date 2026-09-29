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
- **Auto-update yt-dlp** — daily update at 1:00 AM

## Requirements

- Raspberry Pi (or any Linux machine)
- Python 3.7+
- FFmpeg
- pygame (for audio output)

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
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 wsgi:application
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
├── app.py                  # Main Flask backend (~2300 lines)
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
- **yt-dlp** — YouTube downloads
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
| Download errors | `pip install --upgrade yt-dlp` |
| Forgot password | `python3 migrate_user.py` (generates a new password) |
| Service not running | `sudo journalctl -u music-scheduler -f` |
| Database issues | Check files in `instance/` directory |

## License

MIT License
