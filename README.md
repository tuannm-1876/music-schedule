# Raspberry Pi Music Scheduler

A web-based music scheduler for Raspberry Pi that plays music at scheduled times. Features YouTube/YouTube Music playlist downloads, drag-and-drop playlist management, and real-time progress tracking.

## Key Features

- **YouTube Playlist Support**: Download individual tracks or entire playlists
- **Real-time Download Progress**: Live progress tracking with persistent state
- **Drag-and-drop Playlist**: Intuitive song reordering
- **Scheduled Playback**: Custom times with weekday selection
- **Secure Login**: Random password generation and user authentication
- **System Monitoring**: Disk usage and download status
- **Local File Upload**: Support for .mp3, .wav, .ogg files

## Quick Setup

**Requirements**: Raspberry Pi, Python 3.7+, FFmpeg, Internet connection

```bash
# Install dependencies
sudo apt-get update && sudo apt-get install python3-pip python3-pygame ffmpeg

# Clone and setup
git clone [repository-url] && cd schedule-music
sudo pip3 install -r requirements.txt

# Setup database (save the generated admin password!)
python3 migrate_song_position.py
python3 migrate_user.py
```

## Usage

```bash
# Start application
python3 app.py  # Development
# OR
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 wsgi:application  # Production
```

1. **Access**: `http://[raspberry-pi-ip]:5000`
2. **Login**: Username `admin` + generated password
3. **Add Music**:
   - YouTube URLs (single/playlist) → Watch real-time progress
   - Upload local files (.mp3, .wav, .ogg)
4. **Manage**: Drag-and-drop to reorder, play/delete songs
5. **Schedule**: Set times + weekdays for automatic playback
6. **Control**: Play/pause, volume, seek, monitor disk usage

## Run as Service

```bash
sudo cp music-scheduler.service /etc/systemd/system/
sudo systemctl enable music-scheduler
sudo systemctl start music-scheduler
```

## Troubleshooting

**Audio**: Check speakers, volume (`alsamixer`), 3.5mm output (`sudo raspi-config`)
**Network**: Verify internet connection, check firewall settings
**Login**: Reset password with `python3 migrate_user.py`
**Downloads**: Update yt-dlp (`sudo pip3 install --upgrade yt-dlp`), check progress bar
**UI Issues**: Enable JavaScript, clear browser cache, check console for errors

## Recent Updates

- **YouTube Playlist Downloads**: Full playlist support with real-time progress
- **Secure Authentication**: Random password generation, login system
- **Enhanced UI**: Drag-and-drop ordering, collapsible sections, progress tracking
- **System Improvements**: WebSocket reliability, database migrations, error handling

## License

MIT License
