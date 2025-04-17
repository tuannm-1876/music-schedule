# Raspberry Pi Music Scheduler

A web-based music scheduler application designed to play music at specific times (11:45 AM and 12:45 PM) through the Raspberry Pi's 3.5mm audio output. It includes features for downloading music from YouTube and managing a playlist through a web interface.

The application automatically updates yt-dlp daily at 1 AM to ensure continuous compatibility with YouTube's latest changes.

## Features

- Scheduled music playback at 11:45 AM and 12:45 PM
- Web interface for playlist management
- YouTube music download support with automatic daily updates at 1 AM
- Real-time music playback control
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

## Configuration

1. The application will create necessary directories on first run:

   - `music/` - Stores downloaded music files
   - `config/` - Stores playlist configuration

2. The web interface runs on port 5000 by default

## Usage

1. Start the application:

```bash
python3 app.py
```

2. Access the web interface:

   - Open a web browser and navigate to `http://[raspberry-pi-ip]:5000`
   - If accessing locally on the Raspberry Pi, use `http://localhost:5000`

3. Add music to playlist:

   - Paste a YouTube URL into the input field
   - Click "Add Music" to download and add to playlist

4. Control playback:
   - Use the Play button next to each track to test playback
   - Use the Stop button to stop current playback

## Running as a Service

To ensure the scheduler runs on system startup:

1. Create a systemd service file:

```bash
sudo nano /etc/systemd/system/music-scheduler.service
```

2. Add the following content (adjust paths as needed):

```ini
[Unit]
Description=Music Scheduler Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/app.py
WorkingDirectory=/path/to/project
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:

```bash
sudo systemctl enable music-scheduler
sudo systemctl start music-scheduler
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

## Contributing

Feel free to submit issues and enhancement requests!

## License

MIT License
