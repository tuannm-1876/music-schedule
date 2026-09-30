# Music Scheduler

Plays music and announcements on a schedule from a Raspberry Pi: download from YouTube or upload files,
group them into playlists, set times per weekday, skip holidays, and control everything from a browser
or the Android app. Built to run smoothly on a **Raspberry Pi 3B+** (1GB RAM).

## Features

- **YouTube downloads** — single videos or whole playlists, live progress, cancel at any time.
  Mix links (`watch?v=…&list=RD…`) download just that one video.
- **File uploads** — MP3, WAV, OGG, FLAC, AAC, M4A (up to 150MB)
- **Playlists** — group songs (e.g. music vs. announcements), drag-and-drop ordering,
  optional *delete after play*
- **Schedules** — time + weekdays, per-schedule volume, pick a playlist, play one song or the whole
  playlist in order (*play all*), one-time schedules that disable themselves
- **Holidays** — scheduled playback is skipped on listed dates
- **Playback controls** — play/pause, stop, seek, volume, shuffle, fade in/out, synced live to every client
- **Stays signed in** — 30-day sliding session plus a 365-day refresh token per device; each phone/PC
  stays logged in independently and logout only signs out that device
- **Android app** — Capacitor WebView over Tailscale
- **Self-maintaining** — yt-dlp updates itself nightly at 03:00 (skipped while playing or downloading)

## Requirements

- Raspberry Pi 3B+ or newer, or any Linux machine. **Raspberry Pi OS 64-bit (Bookworm) recommended**
- Python **3.10+** (3.11 recommended) — current yt-dlp no longer supports older versions,
  so Raspberry Pi OS Bullseye (Python 3.9) is too old
- FFmpeg
- A JavaScript runtime for YouTube (below)

### JavaScript runtime (required for YouTube)

Since late 2025 yt-dlp solves YouTube's JS challenges with an external runtime plus the `yt-dlp-ejs`
package (installed via `yt-dlp[default]` in `requirements.txt`).

| `uname -m` | Runtime | Setup |
|---|---|---|
| `aarch64` (64-bit OS) | Deno ≥ 2.3 (yt-dlp default) | `curl -fsSL https://deno.land/install.sh \| sh` |
| `armv7l` (32-bit OS) | Node.js ≥ 22 — Deno has no armv7 build | install Node 22, set `YTDLP_JS_RUNTIME=node` in `.env` |

## Installation

```bash
sudo apt-get update
sudo apt-get install -y python3-venv ffmpeg git

git clone https://github.com/tuannm-1876/music-schedule.git
cd music-schedule

python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env          # all settings are optional, see Configuration

# JS runtime for YouTube (64-bit OS; see the table above for 32-bit)
curl -fsSL https://deno.land/install.sh | sh
```

Check that YouTube works — this must list audio formats without a
"No supported JavaScript runtime" warning:

```bash
PATH=$HOME/.deno/bin:$PATH venv/bin/yt-dlp -F "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

A fresh install needs **no migration scripts**: tables are created on first start, and an `admin`
user is created with a random password. The password is not printed to the logs:

```bash
cat instance/initial-admin-password.txt   # save it, then delete the file
```

Recommended on a 1GB board: `sudo apt-get install -y zram-tools` (compressed swap).

## Running

### As a systemd service (production)

`music-scheduler.service` assumes user `pi` and `/home/pi/schedule-music` — edit `User`,
`WorkingDirectory`, `PATH` and `ExecStart` if yours differ.

```bash
sudo cp music-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now music-scheduler
sudo journalctl -u music-scheduler -f      # logs
```

The service puts `~/.deno/bin` on `PATH` (systemd does not read `.bashrc`), runs the app at
`Nice=-5` so audio wins over downloads, and caps memory with `MemoryHigh=600M`.

### Manually

```bash
# production: exactly one worker, pygame audio lives in a single process
venv/bin/gunicorn --worker-class eventlet -w 1 --timeout 120 --bind 0.0.0.0:5000 wsgi:application

# development
venv/bin/python app.py
```

Open `http://<raspberry-pi-ip>:5000`.

## Configuration

All settings go in `.env` (template: `.env.example`). Everything is optional.

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | generated | Signs sessions/CSRF. Generated on first start and saved to `.env`. Changing it logs sessions out (refresh tokens still work) |
| `YTDLP_JS_RUNTIME` | *(deno)* | `deno`, `node` or `quickjs` |
| `YTDLP_JS_RUNTIME_PATH` | | Absolute path to the runtime if it is not on `PATH` |
| `YTDLP_COOKIES_FILE` | | Netscape cookies file, only when YouTube says "confirm you're not a bot". Use a secondary account |
| `YTDLP_AUDIO_QUALITY` | `128K` | MP3 bitrate of downloads |
| `YTDLP_MAX_PLAYLIST_ITEMS` | `200` | Safety cap per playlist download |
| `YTDLP_STALL_TIMEOUT` | `900` | Seconds without yt-dlp output before a download is killed |
| `DATABASE_URL` | `sqlite:///music.db` | SQLAlchemy URL (relative SQLite paths live in `instance/`) |

`.env` holds secrets and is gitignored; keep it private with `chmod 600 .env`.

## Upgrading an existing install

```bash
cd ~/schedule-music
sudo systemctl stop music-scheduler
cp instance/music.db instance/music.db.bak          # backup first
git pull
venv/bin/pip install -r requirements.txt
cp -n .env.example .env

# bring an old database up to date — every script checks before changing, safe to re-run
for m in song_position category delete_after_play one_time schedule_volume \
         remember_token playlist_holiday play_all; do
  venv/bin/python migrate_$m.py
done

sudo cp music-scheduler.service /etc/systemd/system/ && sudo systemctl daemon-reload
sudo systemctl start music-scheduler
```

Old `remember_token` logins are converted to the new refresh tokens automatically, so nobody has
to sign in again. SQLite now runs in WAL mode: back up `music.db` together with `music.db-wal`
(or stop the service first).

## How it works

- **Backend** — a single Flask-SocketIO process on eventlet. pygame plays audio in-process; one
  greenlet broadcasts playback state every second (nothing is sent while idle); APScheduler fires
  the schedules.
- **Downloads** — `POST /add-music` returns `202` at once and progress arrives over Socket.IO
  (`download_progress`, `song_added`). yt-dlp runs as a child process (`youtube_downloader.py`) at
  `nice 15`, so it never blocks the event loop. Cancelling kills the whole process group and
  removes partial files from `music/.incoming/`, and a new yt-dlp version is used on the next
  download without a restart. Only one download runs at a time (`409` otherwise), and only
  YouTube URLs are accepted.
- **Login** — the session cookie lasts 30 days and is renewed on every request. Each device also
  gets a refresh token (table `auth_token`, SHA-256 only) valid for 365 days and renewed when
  used, so the session is restored silently even after it expires.
- **Files** — new downloads are named `<title>_<videoId>.mp3` (ASCII-safe).

## Project Structure

```
├── app.py                    # Flask app: models, API, Socket.IO, player, scheduler
├── youtube_downloader.py     # yt-dlp wrapper (child process, progress parsing, cancel, update)
├── secret_key_loader.py      # SECRET_KEY from .env, generated on first start
├── wsgi.py                   # Gunicorn entry point
├── migrate_*.py              # upgrade scripts for databases created by older versions
├── music-scheduler.service   # systemd unit
├── requirements.txt          # runtime deps · requirements-dev.txt: pytest
├── .env.example              # configuration template
├── tests/                    # pytest suite
├── music/                    # audio files (gitignored)
├── instance/                 # SQLite DB, initial admin password (gitignored)
├── static/react/             # built frontend (npm run build)
├── templates/                # legacy server-rendered login page
└── frontend/src/
    ├── components/
    │   ├── dashboard/        # AddMusic, DownloadProgress, DiskUsage, NextSchedule, YtdlpInfo
    │   ├── player/           # player bar
    │   ├── playlist/         # song list with drag-and-drop
    │   ├── playlist-manager/ # create/delete playlists
    │   ├── schedule/         # schedules
    │   ├── holiday/          # holidays
    │   └── ui/               # Button, Card, Input, Progress, Slider, Spinner, Switch
    ├── contexts/             # Socket, Theme, Toast providers
    ├── lib/api.ts            # axios client
    ├── pages/                # Dashboard, LoginPage
    └── types/                # shared TypeScript types
```

## Development

```bash
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m pytest          # needs ffmpeg; downloads are tested against a local HTTP server

cd frontend
npm install
npm run dev                        # Vite dev server
npm run build                      # outputs to ../static/react
```

## Tech Stack

- **Backend** — Flask 2.3, Flask-SocketIO + eventlet, Flask-SQLAlchemy + SQLite (WAL), APScheduler,
  pygame, yt-dlp, mutagen, Flask-WTF
- **Frontend** — React 19, TypeScript, Vite 7, Tailwind CSS 4, Socket.IO client, Framer Motion,
  dnd-kit, Axios, Lucide
- **Mobile** — Capacitor 8, Tailscale for remote access

## Android App

The app is a WebView pointed at the Pi over Tailscale (`http://<tailscale-ip>:5000`).

```bash
cd frontend
npm run build:cap
npx cap sync android
cd android && JAVA_HOME=/path/to/java-21 ./gradlew assembleDebug
# APK: android/app/build/outputs/apk/debug/app-debug.apk
```

Requires Node.js, Java 21 and Android SDK 34.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Thiếu JS runtime" / no audio formats | Install Deno or Node (see *JavaScript runtime*) and make sure it is on the service `PATH` |
| "YouTube chặn vì nghi là bot" | Export a cookies file from a secondary account, set `YTDLP_COOKIES_FILE` |
| Downloads broke after a YouTube change | Press *Cập nhật* on the yt-dlp card, or `venv/bin/pip install -U "yt-dlp[default]"` |
| yt-dlp never gets newer | Python < 3.10 — move to Raspberry Pi OS Bookworm |
| "Đang có bài đang tải" forever | A download is running; cancel it in the UI. A stalled one is killed after `YTDLP_STALL_TIMEOUT` |
| Audio stutters | `journalctl -u music-scheduler \| grep -i underrun`; enable zram, check the service `Nice=-5` |
| No audio at all | `alsamixer`; choose the 3.5mm output in `sudo raspi-config` |
| Lost the admin password | `venv/bin/python migrate_user.py` — asks to overwrite, prints the new password in your terminal |
| Where is the first password? | `cat instance/initial-admin-password.txt` — it is never written to the logs |
| Service won't start | `sudo journalctl -u music-scheduler -n 100` |

## License

MIT License
