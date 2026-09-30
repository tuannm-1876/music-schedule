# Project Changelog

## [Unreleased] — 2026-09-30 · branch `fix/youtube-download-rpi`

### Fixed (high severity)
- YouTube downloads failing: yt-dlp now installs as `yt-dlp[default]` (brings `yt-dlp-ejs`) and can use a JS runtime (Deno by default, `YTDLP_JS_RUNTIME=node` on 32-bit Pi OS).
- Downloads no longer block the eventlet hub: yt-dlp runs as a low-priority child process driven by a greenlet; `POST /add-music` returns `202` at once and `409` while another job or a yt-dlp update is running.
- `watch?v=…&list=RD…` mix links download a single video instead of the whole radio mix.
- Cancel works mid-track (process-group kill, SIGKILL escalation) and removes partial files; a 15-minute stall watchdog prevents a hung job from locking downloads.
- yt-dlp updates take effect without restarting the service.
- Frontend: `song_added` no longer blanks the playlist, the download banner no longer sticks on `cancelled`, and API error messages are shown.

### Security
- `/add-music` only accepts YouTube hosts (blocks SSRF through yt-dlp's generic extractor).

### Performance (Raspberry Pi 3B+)
- Playback broadcast: one 1s greenlet loop instead of a 0.5s APScheduler job, song title cached, no emits while idle and unchanged.
- One extraction per track (previously two); mp3 128K; yt-dlp/ffmpeg run at `nice -n 15`.
- SQLite WAL + `synchronous=NORMAL`; download state logs lowered to DEBUG.
- Nightly yt-dlp update moved to 03:00 and skipped while playing or downloading.

### Changed
- New downloads are named `<title>_<videoId>.mp3` (ASCII-safe); existing files are untouched.
- Requires Python ≥ 3.10.
