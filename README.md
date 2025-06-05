# Raspberry Pi Music Scheduler

A web-based music scheduler application designed to play music at user-defined schedules through the Raspberry Pi's 3.5mm audio output. It includes features for downloading music from YouTube, managing a playlist with drag-and-drop reordering, and monitoring disk space usage.

The application automatically updates yt-dlp daily at 1 AM to ensure continuous compatibility with YouTube's latest changes.

## Features

- Custom scheduled music playback with weekday selection
- Web interface for playlist management
- Drag-and-drop playlist reordering
- YouTube music download support with automatic daily updates at 1 AM
- Local music file upload support
- Real-time music playback control with volume adjustment
- Real-time disk space usage monitoring
- Song priority management
- 3.5mm audio output support

## Requirements

- Raspberry Pi (any model with 3.5mm audio output)
- Python 3.7+
- FFmpeg (for audio processing)
- Internet connection
- Speakers connected to the 3.5mm audio jack

## Installation

1. Install system dependencies and Python packages:

```bash
sudo apt-get update
sudo apt-get install python3-pip python3-pygame ffmpeg
```

2. Clone this repository:

```bash
git clone [repository-url]
cd schedule-music
```

3. Install additional Python packages:

```bash
sudo pip3 install -r requirements.txt
```

4. Run database migrations to setup the song position field:

```bash
python3 migrate_song_position.py
```

## Configuration

1. The application will create necessary directories on first run:

   - `music/` - Stores downloaded music files
   - `config/` - Stores playlist configuration

2. The web interface runs on port 5000 by default
   
3. Songs can be reordered by drag-and-drop in the playlist

## Usage

1. Start the application (development mode):

```bash
python3 app.py
```

For production use with Gunicorn:

```bash
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 wsgi:application
```

2. Access the web interface:

   - Open a web browser and navigate to `http://[raspberry-pi-ip]:5000`
   - If accessing locally on the Raspberry Pi, use `http://localhost:5000`

3. Add music to playlist:

   - Paste a YouTube URL into the input field and click "Add from YouTube" to download and add to playlist
   - Or upload local audio files (.mp3, .wav, .ogg) using the "Upload File" section

4. Manage your playlist:
   - Drag and drop songs to reorder them
   - Set priority values for each song (higher values play more frequently)
   - Use the Play button next to each track to test playback
   - Use the Delete button to remove songs from the playlist

5. Control playback:
   - Use the Play/Pause button to control current playback
   - Use the Stop button to stop current playback
   - Adjust volume using the volume slider
   - Click on the progress bar to seek within the current track

6. Schedule playback:
   - Add new schedules with specific times
   - Select which weekdays each schedule should be active
   - Enable/disable schedules as needed
   - Delete schedules that are no longer needed

7. Monitor disk usage:
   - Check available disk space in the Disk Usage section
   - Keep an eye on disk usage to avoid running out of space when uploading new songs

## Running as a Service

To ensure the scheduler runs on system startup with Gunicorn:

1. Install Gunicorn and dependencies:

```bash
pip3 install -r requirements.txt
```

2. Copy the provided service file to systemd:

```bash
sudo cp music-scheduler.service /etc/systemd/system/
```

3. Edit the service file if necessary to match your paths:

```bash
sudo nano /etc/systemd/system/music-scheduler.service
```

4. Enable and start the service:

```bash
sudo systemctl enable music-scheduler
sudo systemctl start music-scheduler
```

5. Check the service status:

```bash
sudo systemctl status music-scheduler
```

## Troubleshooting

1. Audio Issues:

   - Ensure speakers are properly connected
   - Check volume levels using `alsamixer`
   - Verify audio output is set to 3.5mm: `sudo raspi-config`

2. Network Issues:

   - Verify Raspberry Pi has internet connection
   - Check firewall settings if web interface is inaccessible

3. Permission Issues:

   - Ensure proper write permissions for music and config directories
   - Run with sudo if necessary for audio access

4. Download Issues:
   - If YouTube downloads stop working, the automatic daily update of yt-dlp should fix it
   - To manually update yt-dlp: `sudo pip3 install --upgrade yt-dlp`

5. CSRF Token Issues:
   - If you see "CSRF token missing" errors, try clearing your browser cache or restarting the application

6. Drag-and-Drop Issues:
   - Make sure JavaScript is enabled in your browser
   - If reordering doesn't persist after refresh, check browser console for API errors

7. Disk Space Issues:
   - If the disk space indicator shows high usage, delete unused songs
   - Consider moving the music directory to an external drive for more space

## Contributing

Feel free to submit issues and enhancement requests!

## Recent Improvements

- **Drag and Drop Playlist Reordering**: Easily reorganize your playlist with intuitive drag-and-drop functionality
- **Song Position Tracking**: Songs now maintain their order in the playlist across application restarts
- **Disk Space Monitoring**: Real-time disk usage indicator to help manage storage space
- **Enhanced Weekday Selector**: Improved UI for schedule weekday selection
- **Better CSRF Handling**: Fixed CSRF token issues for better security and reliability
- **Production Deployment**: Support for Gunicorn with eventlet worker for proper production deployment

## License

MIT License
