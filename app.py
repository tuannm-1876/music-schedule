# Apply eventlet monkey patching at the very start
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, jsonify, request, redirect, url_for, send_file, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import yt_dlp
import pygame
import os
import json
import subprocess
import sys
import logging
import shutil
import re
from werkzeug.utils import secure_filename
import mutagen
from mutagen.mp3 import MP3
import glob
from contextlib import contextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set APScheduler logging to WARNING level to reduce noise
logging.getLogger('apscheduler').setLevel(logging.WARNING)

# Constants
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg'}
DEFAULT_VOLUME = 0.5
BROADCAST_INTERVAL = 0.5
UPDATE_YTDLP_HOUR = 1
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB

# Global download state
download_state = {
    'active': False,
    'status': '',
    'message': '',
    'current': 0,
    'total': 0,
    'current_song': '',
    'playlist_title': '',
    'cancelled': False
}

app = Flask(__name__)
csrf = CSRFProtect(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///music.db'
app.config['UPLOAD_FOLDER'] = 'music'
app.config['SECRET_KEY'] = 'super-secret-key-for-music-scheduler-app'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours session lifetime
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE
app.config['CORS_HEADERS'] = 'Content-Type'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*', message_queue=None)
CORS(app)
db = SQLAlchemy(app)

# Get absolute path for the project directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
MUSIC_DIR = os.path.join(BASE_DIR, app.config['UPLOAD_FOLDER'])

# Function to get disk usage information
def get_disk_usage():
    """Get disk usage information for the music folder"""
    try:
        # Get disk usage for the partition where the music folder is located
        total, used, free = shutil.disk_usage(MUSIC_DIR)
        
        # Convert to readable format
        total_gb = total / (1024 ** 3)  # Convert to GB
        used_gb = used / (1024 ** 3)
        free_gb = free / (1024 ** 3)
        
        # Calculate percentage used
        percentage_used = (used / total) * 100
        
        return {
            'total_gb': round(total_gb, 2),
            'used_gb': round(used_gb, 2),
            'free_gb': round(free_gb, 2),
            'percentage_used': round(percentage_used, 1)
        }
    except Exception as e:
        logger.error(f"Error getting disk usage: {e}")
        return {
            'total_gb': 0,
            'used_gb': 0,
            'free_gb': 0,
            'percentage_used': 0
        }

# Initialize pygame mixer for audio playback with larger buffer to prevent ALSA underrun
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
pygame.mixer.music.set_volume(DEFAULT_VOLUME)

# Initialize scheduler
scheduler = None
# Download state management functions
def set_download_state(status, message='', current=0, total=0, current_song='', playlist_title='', cancelled=False):
    """Update global download state"""
    global download_state
    download_state.update({
        'active': status != 'completed' and status != 'error' and status != 'cancelled',
        'status': status,
        'message': message,
        'current': current,
        'total': total,
        'current_song': current_song,
        'playlist_title': playlist_title,
        'cancelled': cancelled
    })
    logger.info(f"Download state updated: {download_state}")

def get_download_state():
    """Get current download state"""
    return download_state.copy()

def clear_download_state():
    """Clear download state"""
    global download_state
    download_state = {
        'active': False,
        'status': '',
        'message': '',
        'current': 0,
        'total': 0,
        'current_song': '',
        'playlist_title': '',
        'cancelled': False
    }

def cancel_download():
    """Cancel current download"""
    global download_state
    if download_state['active']:
        download_state['cancelled'] = True
        set_download_state('cancelled', 'Download has been cancelled', download_state['current'], download_state['total'], cancelled=True)
        logger.info("Download cancelled by user")
        socketio.emit('download_progress', {
            'status': 'cancelled',
            'message': 'Download has been cancelled',
            'current': download_state['current'],
            'total': download_state['total']
        })
        return True
    return False

def init_scheduler():
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler()
        scheduler.start()
        scheduler.add_job(safe_broadcast, 'interval', seconds=BROADCAST_INTERVAL, id='broadcast_playback')
        scheduler.add_job(update_ytdlp, 'cron', hour=UPDATE_YTDLP_HOUR, id='update_ytdlp')

def init_admin_user():
    """Initialize the admin user if not exists"""
    try:
        with session_scope() as db_session:
            admin = db_session.query(User).filter_by(username='admin').first()
            if not admin:
                logger.info("Creating admin user")
                
                # Import random password generation
                import secrets
                import string
                
                def generate_random_password(length=16):
                    lowercase = string.ascii_lowercase
                    uppercase = string.ascii_uppercase
                    digits = string.digits
                    special = "!@#$%^&*"
                    
                    password = [
                        secrets.choice(lowercase),
                        secrets.choice(uppercase),
                        secrets.choice(digits),
                        secrets.choice(special)
                    ]
                    
                    all_chars = lowercase + uppercase + digits + special
                    for _ in range(length - 4):
                        password.append(secrets.choice(all_chars))
                    
                    secrets.SystemRandom().shuffle(password)
                    return ''.join(password)
                
                random_password = generate_random_password()
                
                admin = User(username='admin')
                admin.set_password(random_password)
                db_session.add(admin)
                db_session.commit()
                
                # Display password prominently
                print("\n" + "="*60)
                print("🔐 ADMIN PASSWORD GENERATED")
                print("="*60)
                print(f"Username: admin")
                print(f"Password: {random_password}")
                print("="*60)
                print("⚠️  SAVE THIS PASSWORD NOW! It will not be shown again.")
                print("="*60 + "\n")
                
                logger.info("Admin user created successfully")
                logger.info(f"Admin password: {random_password}")
            else:
                logger.info("Admin user already exists")
    except Exception as e:
        logger.error(f"Error initializing admin user: {e}")

# Ensure directories exist
os.makedirs(MUSIC_DIR, exist_ok=True)

# Global variables for playback state
current_song_id = None
current_song_duration = 0
is_playing = False
volume = DEFAULT_VOLUME
current_position = 0
seek_offset = 0  # Track the offset when seeking
shuffle_mode = False  # Shuffle mode for random playback
fade_enabled = True  # Enable fade in/out effect
fade_duration = 2.0  # Fade duration in seconds

@contextmanager
def session_scope():
    """Provides a transactional scope around a series of operations."""
    session = db.session
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def broadcast_playback_state():
    """Broadcast current playback state to all clients"""
    try:
        global current_position, current_song_id, current_song_duration, is_playing, seek_offset
        
        music_busy = pygame.mixer.music.get_busy()
        
        if music_busy and current_song_id:
            pos = pygame.mixer.music.get_pos()
            if pos >= 0:
                # Add seek_offset to get actual position in the song
                current_position = (pos / 1000) + seek_offset
        elif not music_busy and is_playing and current_song_id:
            # Song has finished playing
            logger.info(f"Song finished playing: {current_song_id}")
            current_position = 0
            current_song_id = None
            current_song_duration = 0
            is_playing = False
            
            # Emit song finished event
            socketio.emit('song_finished', {
                'message': 'Song playback completed'
            })

        # Get current song title
        current_title = None
        if current_song_id:
            try:
                with app.app_context():
                    with session_scope() as session:
                        song = session.get(Song, current_song_id)
                        if song:
                            current_title = song.title
            except Exception as e:
                logger.error(f"Error getting song title: {e}")
        
        socketio.emit('playback_update', {
            'position': current_position,
            'duration': current_song_duration,
            'is_playing': music_busy,
            'volume': int(volume * 100),
            'current_song_id': current_song_id,
            'current_song_title': current_title
        })
    except Exception as e:
        logger.error(f"Error in broadcast_playback_state: {e}")

def safe_broadcast():
    socketio.start_background_task(broadcast_playback_state)


def fade_in():
    """Gradually increase volume from 0 to target volume"""
    global volume
    try:
        steps = int(fade_duration * 20)  # 20 steps per second
        step_volume = volume / steps
        current_vol = 0
        for _ in range(steps):
            current_vol = min(current_vol + step_volume, volume)
            pygame.mixer.music.set_volume(current_vol)
            eventlet.sleep(0.05)  # 50ms per step
        pygame.mixer.music.set_volume(volume)
        logger.info(f"Fade in complete, volume: {volume}")
    except Exception as e:
        logger.error(f"Error in fade_in: {e}")
        pygame.mixer.music.set_volume(volume)


def fade_out():
    """Gradually decrease volume to 0 then stop"""
    global volume
    try:
        current_vol = pygame.mixer.music.get_volume()
        steps = int(fade_duration * 20)  # 20 steps per second
        step_volume = current_vol / steps if steps > 0 else current_vol
        for _ in range(steps):
            current_vol = max(current_vol - step_volume, 0)
            pygame.mixer.music.set_volume(current_vol)
            eventlet.sleep(0.05)  # 50ms per step
        pygame.mixer.music.stop()
        pygame.mixer.music.set_volume(volume)  # Reset volume for next song
        logger.info("Fade out complete")
    except Exception as e:
        logger.error(f"Error in fade_out: {e}")
        pygame.mixer.music.stop()


# Models
class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(5), nullable=False)  # Format: "HH:MM"
    enabled = db.Column(db.Boolean, default=True)
    one_time = db.Column(db.Boolean, default=False)  # If True, disable after playing once
    monday = db.Column(db.Boolean, default=True)
    tuesday = db.Column(db.Boolean, default=True)
    wednesday = db.Column(db.Boolean, default=True)
    thursday = db.Column(db.Boolean, default=True)
    friday = db.Column(db.Boolean, default=True)
    saturday = db.Column(db.Boolean, default=True)
    sunday = db.Column(db.Boolean, default=True)

    @property
    def weekdays(self):
        return {
            'monday': self.monday,
            'tuesday': self.tuesday,
            'wednesday': self.wednesday,
            'thursday': self.thursday,
            'friday': self.friday,
            'saturday': self.saturday,
            'sunday': self.sunday
        }

class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(200), nullable=False, unique=True)
    priority = db.Column(db.Integer, default=0)
    position = db.Column(db.Integer, default=0)  # New field for song ordering
    source = db.Column(db.String(50))
    duration = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_played_at = db.Column(db.DateTime, nullable=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Create a function to check if a user is logged in
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def find_actual_file(filename):
    """Find the actual file regardless of special character differences"""
    try:
        base_name = os.path.basename(filename)
        dir_name = os.path.dirname(filename)
        search_path = os.path.join(BASE_DIR, dir_name, '*')
        
        for file in glob.glob(search_path):
            if os.path.basename(file).replace('｜', '|') == base_name:
                return os.path.relpath(file, BASE_DIR)
        return filename
    except Exception as e:
        logger.error(f"Error finding file {filename}: {e}")
        return filename

def get_audio_duration(filename):
    try:
        audio = MP3(filename)
        return int(audio.info.length)
    except Exception as e:
        logger.error(f"Error getting audio duration for {filename}: {e}")
        return 0

def update_ytdlp():
    """Update yt-dlp with multiple methods compatible with Raspberry Pi"""
    try:
        venv_python = os.path.join(BASE_DIR, "venv", "bin", "python")
        venv_pip = os.path.join(BASE_DIR, "venv", "bin", "pip")

        if os.path.exists(venv_python) and os.path.exists(venv_pip):
            logger.info("Attempting to update yt-dlp using virtual environment")
            subprocess.check_call([venv_pip, "install", "--upgrade", "yt-dlp"])
            logger.info("yt-dlp updated successfully using virtual environment")
            return

        # On modern Debian/Raspberry Pi OS, pip commands can fail with an
        # 'externally-managed-environment' error. The following methods attempt to work around this.

        # Method 1: Use pip with --break-system-packages. This is the direct override for the error.
        try:
            logger.info("Attempting to update yt-dlp with --break-system-packages")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", "--upgrade", "yt-dlp"])
            logger.info("yt-dlp updated successfully with --break-system-packages")
            return
        except subprocess.CalledProcessError:
            logger.warning("Update with --break-system-packages failed. Trying next method.")
            pass

        # Method 2: Try installing for the current user. This might also be blocked.
        try:
            logger.info("Attempting to update yt-dlp for user")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "--upgrade", "yt-dlp"])
            logger.info("yt-dlp updated successfully for user")
            return
        except subprocess.CalledProcessError:
            logger.warning("Update with --user failed. Trying next method.")
            pass

        # Method 3: Use the system package manager (apt).
        # Note: This requires the user running the app to have passwordless sudo access.
        try:
            logger.info("Attempting to update yt-dlp using apt-get")
            subprocess.check_call(["sudo", "apt-get", "update"])
            subprocess.check_call(["sudo", "apt-get", "install", "-y", "yt-dlp"])
            logger.info("yt-dlp updated successfully using apt-get")
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Update with apt-get failed. This may be due to permissions or apt-get not being found.")
            pass

        logger.error("All update methods for yt-dlp have failed. Please update it manually.")

    except Exception as e:
        logger.error(f"An unexpected error occurred during yt-dlp update: {e}")

def get_ytdlp_version():
    """Get current yt-dlp version"""
    try:
        result = subprocess.run([sys.executable, "-m", "yt_dlp", "--version"],
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return "Unknown"
    except Exception as e:
        logger.error(f"Error getting yt-dlp version: {e}")
        return "Unknown"

def get_next_scheduled_song():
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    weekday = now.strftime("%A").lower()

    try:
        with session_scope() as session:
            schedules = session.query(Schedule).filter(
                Schedule.time > current_time,
                Schedule.enabled == True
            ).order_by(Schedule.time).all()
            
            if not schedules:
                schedules = session.query(Schedule).filter(
                    Schedule.enabled == True
                ).order_by(Schedule.time).all()
            
            valid_schedules = [s for s in schedules if getattr(s, weekday)]
            
            if valid_schedules:
                next_schedule = valid_schedules[0]
                next_song_to_play = session.query(Song).order_by(
                    Song.position.asc(),
                    Song.last_played_at.is_(None).desc(),
                    Song.priority.desc(),
                    Song.last_played_at.asc()
                ).first()

                weekdays = [day for day, enabled in next_schedule.weekdays.items() if enabled]
                return {
                    'time': next_schedule.time,
                    'weekdays': weekdays,
                    'song': next_song_to_play.title if next_song_to_play else None
                }
    except Exception as e:
        logger.error(f"Error getting next scheduled song: {e}")
    return None

def broadcast_next_schedule():
    """Broadcast next schedule info to all clients"""
    try:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        weekday = now.strftime("%A").lower()
        
        with session_scope() as session:
            # Get schedules after current time
            schedules = session.query(Schedule).filter(
                Schedule.time > current_time,
                Schedule.enabled == True
            ).order_by(Schedule.time).all()
            
            # If no schedules after current time, get all enabled schedules (for next day)
            if not schedules:
                schedules = session.query(Schedule).filter(
                    Schedule.enabled == True
                ).order_by(Schedule.time).all()
            
            # Filter by current weekday
            valid_schedules = [s for s in schedules if getattr(s, weekday)]
            
            next_schedule_info = None
            if valid_schedules:
                next_schedule = valid_schedules[0]
                next_song = session.query(Song).order_by(
                    Song.position.asc(),
                    Song.last_played_at.is_(None).desc(),
                    Song.priority.desc(),
                    Song.last_played_at.asc()
                ).first()
                
                next_schedule_info = {
                    'time': next_schedule.time,
                    'song_title': next_song.title if next_song else 'Không có bài hát'
                }
            
            socketio.emit('next_schedule_update', {
                'next_schedule': next_schedule_info
            })
            logger.info(f"Broadcast next schedule: {next_schedule_info}")
    except Exception as e:
        logger.error(f"Error broadcasting next schedule: {e}")

def schedule_music():
    """Schedule music playback with improved error handling and thread safety."""
    global scheduler
    with app.app_context():
        try:
            if scheduler is None:
                init_scheduler()
            # Store existing jobs we want to preserve
            preserved_jobs = {}
            for job in scheduler.get_jobs():
                if job.id in ['broadcast_playback', 'update_ytdlp']:
                    preserved_jobs[job.id] = job.trigger
                    
            scheduler.remove_all_jobs()
            
            # Restore preserved jobs
            if 'broadcast_playback' in preserved_jobs:
                scheduler.add_job(
                    broadcast_playback_state,
                    'interval',
                    seconds=BROADCAST_INTERVAL,
                    id='broadcast_playback'
                )
            
            if 'update_ytdlp' in preserved_jobs:
                scheduler.add_job(
                    update_ytdlp,
                    'cron',
                    hour=UPDATE_YTDLP_HOUR,
                    id='update_ytdlp'
                )
            with session_scope() as session:
                schedules = session.query(Schedule).filter_by(enabled=True).all()
                logger.info(f"Setting up schedules: {len(schedules)} found")
                
                for schedule in schedules:
                    logger.info(f"Processing schedule {schedule.id} at {schedule.time}")
                    try:
                        hour, minute = map(int, schedule.time.split(':'))
                        if not (0 <= hour <= 23 and 0 <= minute <= 59):
                            logger.error(f"Invalid time format in schedule {schedule.id}: {schedule.time}")
                            continue
                            
                        days_of_week = [
                            day for day, enabled in [
                                ('mon', schedule.monday),
                                ('tue', schedule.tuesday),
                                ('wed', schedule.wednesday),
                                ('thu', schedule.thursday),
                                ('fri', schedule.friday),
                                ('sat', schedule.saturday),
                                ('sun', schedule.sunday)
                            ] if enabled
                        ]
                        
                        if days_of_week:
                            job_id = f"schedule_{schedule.id}"
                            
                            # Check if time is in the past for today
                            now = datetime.now()
                            schedule_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                            
                            # Pass schedule_id and one_time flag to the job
                            job_args = [schedule.id, schedule.one_time]
                            
                            if schedule_time > now:
                                scheduler.add_job(
                                    play_next_song,
                                    'cron',
                                    hour=hour,
                                    minute=minute,
                                    day_of_week=','.join(days_of_week),
                                    id=job_id,
                                    args=job_args,
                                    replace_existing=True,
                                    next_run_time=schedule_time
                                )
                                logger.info(f"Added job {job_id} with next run today at {schedule_time}, one_time={schedule.one_time}")
                            else:
                                scheduler.add_job(
                                    play_next_song,
                                    'cron',
                                    hour=hour,
                                    minute=minute,
                                    day_of_week=','.join(days_of_week),
                                    id=job_id,
                                    args=job_args,
                                    replace_existing=True
                                )
                                logger.info(f"Added job {job_id} for days: {','.join(days_of_week)} at {hour:02d}:{minute:02d}, one_time={schedule.one_time}")
                        else:
                            logger.warning(f"Schedule {schedule.id} has no enabled days, skipping")
                    except ValueError as e:
                        logger.error(f"Error processing schedule {schedule.id}: {e}")
                        continue
                
                # Log final job count for debugging
                all_jobs = scheduler.get_jobs()
                schedule_jobs = [job for job in all_jobs if job.id.startswith('schedule_')]
                logger.info(f"Schedule reload complete. Total jobs: {len(all_jobs)}, Schedule jobs: {len(schedule_jobs)}")
                for job in schedule_jobs:
                    logger.info(f"  Job {job.id}: next run at {job.next_run_time}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error in schedule_music: {e}")
            # Attempt to restore critical jobs on error
            try:
                if 'broadcast_playback' not in scheduler:
                    scheduler.add_job(
                        broadcast_playback_state,
                        'interval',
                        seconds=BROADCAST_INTERVAL,
                        id='broadcast_playback'
                    )
            except Exception as e:
                logger.error(f"Failed to restore broadcast job: {e}")
            return False

def play_next_song(schedule_id=None, one_time=False):
    with app.app_context():
        logger.info(f"Scheduler triggered play next song (schedule_id={schedule_id}, one_time={one_time}, shuffle={shuffle_mode})")
        try:
            with session_scope() as session:
                if shuffle_mode:
                    # Shuffle mode: pick a random song
                    from sqlalchemy.sql.expression import func
                    next_song = session.query(Song).order_by(func.random()).first()
                    logger.info(f"Shuffle mode: randomly selected song")
                else:
                    # Normal mode: prioritize songs that haven't been played
                    next_song = session.query(Song).order_by(
                        Song.position.asc(),
                        Song.last_played_at.is_(None).desc(),
                        Song.priority.desc(),
                        Song.last_played_at.asc()
                    ).first()

                if next_song:
                    logger.info(f"Playing song: {next_song.title}")
                    # Trigger playlist update through socket
                    socketio.emit('schedule_triggered', {
                        'song_id': next_song.id,
                        'title': next_song.title,
                        'time': datetime.now().strftime("%H:%M")
                    })
                    play_music(next_song.id)
                    
                    # If this is a one-time schedule, disable it after playing
                    if one_time and schedule_id:
                        schedule = session.get(Schedule, schedule_id)
                        if schedule:
                            schedule.enabled = False
                            logger.info(f"Disabled one-time schedule {schedule_id}")
                            # Emit schedule update to clients
                            socketio.emit('schedule_updated', {
                                'id': schedule_id,
                                'is_active': False
                            })
                else:
                    logger.warning("No songs found in the playlist")
                    
            # Broadcast next schedule update after potential disable
            if one_time and schedule_id:
                broadcast_next_schedule()
                schedule_music()  # Reload schedules to remove the disabled job
                
        except Exception as e:
            logger.error(f"Error playing next song: {e}")

def play_music(song_id):
    global current_song_id, current_song_duration, is_playing, current_position, seek_offset
    
    try:
        with session_scope() as session:
            song = session.get(Song, song_id)
            if not song:
                logger.error(f"Song with ID {song_id} not found")
                return False

            actual_filename = find_actual_file(song.filename)
            file_path = os.path.join(BASE_DIR, actual_filename)
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return False

            if pygame.mixer.music.get_busy():
                # Fade out current song if fade is enabled
                if fade_enabled:
                    fade_out()
                else:
                    pygame.mixer.music.stop()

            pygame.mixer.music.load(file_path)
            
            # Start with volume 0 if fade is enabled
            if fade_enabled:
                pygame.mixer.music.set_volume(0)
                pygame.mixer.music.play()
                # Fade in
                fade_in()
            else:
                pygame.mixer.music.set_volume(volume)
                pygame.mixer.music.play()
            
            current_song_id = song_id
            current_song_duration = song.duration
            is_playing = True
            current_position = 0
            seek_offset = 0
            
            # Update last_played_at and move song to end of playlist
            song.last_played_at = datetime.utcnow()
            
            # Move this song to the end and reorder other songs
            # Get all songs ordered by current position
            all_songs = session.query(Song).order_by(Song.position.asc()).all()
            
            # Remove the current song from the list and add it to the end
            other_songs = [s for s in all_songs if s.id != song_id]
            other_songs.append(song)
            
            # Reassign positions starting from 0
            for i, s in enumerate(other_songs):
                s.position = i
            
            logger.info(f"Updated song {song.title} - last_played_at: {song.last_played_at}, new position: {song.position} (moved to end)")
            
            broadcast_playback_state()
            return True

    except pygame.error as e:
        logger.error(f"Pygame error playing music: {e}")
        return False
    except Exception as e:
        logger.error(f"Error playing music: {e}")
        return False

def normalize_filename(title):
    # Replace special characters and spaces
    # Remove any character that is not alphanumeric, space, or underscore
    title = re.sub(r'[^\w\s]', '', title)
    # Replace spaces with underscores
    title = title.replace(' ', '_')
    # Ensure only one underscore between words
    title = re.sub(r'_+', '_', title)
    return title

def is_playlist_url(url):
    """Check if URL is a playlist"""
    playlist_indicators = [
        'playlist?list=',
        '&list=',
        '/playlist/',
        'music.youtube.com/playlist'
    ]
    return any(indicator in url for indicator in playlist_indicators)

def download_single_track(url):
    """Download a single track from YouTube"""
    try:
        # First extract info without downloading
        with yt_dlp.YoutubeDL({'extract_flat': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = int(info.get('duration', 0))
            normalized_title = normalize_filename(info['title'])
            
        # Then download with normalized filename
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(MUSIC_DIR, f'{normalized_title}.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Get the actual mp3 file
        mp3_file = os.path.join(MUSIC_DIR, f'{normalized_title}.mp3')
        if not os.path.exists(mp3_file):
            raise Exception(f"Downloaded file not found: {mp3_file}")
            
        actual_filename = os.path.relpath(mp3_file, BASE_DIR)
        
        if duration == 0:
            duration = get_audio_duration(mp3_file)
        
        return {
            'title': info['title'],
            'filename': actual_filename,
            'duration': duration
        }
    except Exception as e:
        logger.error(f"Error downloading single track from {url}: {e}")
        raise

def download_playlist(url):
    """Download all tracks from a YouTube playlist"""
    try:
        logger.info(f"Processing playlist: {url}")
        
        # Update state and emit start event
        set_download_state('analyzing', 'Analyzing playlist...', 0, 0)
        socketio.emit('download_progress', {
            'status': 'analyzing',
            'message': 'Analyzing playlist...',
            'current': 0,
            'total': 0
        })
        
        # Extract playlist info
        ydl_opts_info = {
            'extract_flat': True,
            'quiet': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            playlist_info = ydl.extract_info(url, download=False)
            
        if 'entries' not in playlist_info:
            raise Exception("Unable to extract song list from playlist")
            
        entries = playlist_info['entries']
        if not entries:
            raise Exception("Playlist is empty or inaccessible")
            
        playlist_title = playlist_info.get('title', 'Unknown')
        logger.info(f"Found {len(entries)} songs in playlist: {playlist_title}")
        
        
        downloaded_songs = []
        failed_downloads = []
        
        # Download each track individually
        for i, entry in enumerate(entries, 1):
            # Check if download has been cancelled
            if download_state.get('cancelled', False):
                logger.info("Download cancelled by user, stopping playlist download")
                clear_download_state()
                socketio.emit('download_progress', {
                    'status': 'cancelled',
                    'message': 'Download has been cancelled',
                    'current': i-1,
                    'total': len(entries)
                })
                return {
                    'playlist_title': playlist_info.get('title', 'Unknown Playlist'),
                    'total_tracks': len(entries),
                    'downloaded_tracks': len(downloaded_songs),
                    'failed_tracks': len(failed_downloads),
                    'songs': downloaded_songs,
                    'failed_songs': failed_downloads,
                    'cancelled': True
                }
            
            if not entry:
                continue
                
            try:
                video_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry['id']}"
                video_title = entry.get('title', f'Unknown Track {i}')
                
                logger.info(f"Downloading track {i}/{len(entries)}: {video_title}")
                
                # Update state and emit progress for current track
                set_download_state('downloading', f'Downloading track {i}/{len(entries)}', i, len(entries), video_title, playlist_title)
                socketio.emit('download_progress', {
                    'status': 'downloading',
                    'message': f'Downloading track {i}/{len(entries)}',
                    'current_song': video_title,
                    'current': i,
                    'total': len(entries)
                })
                
                
                # Get detailed info for this specific video
                ydl_opts_detail = {
                    'quiet': True,
                    'no_warnings': True
                }
                
                with yt_dlp.YoutubeDL(ydl_opts_detail) as ydl_detail:
                    video_info = ydl_detail.extract_info(video_url, download=False)
                    duration = int(video_info.get('duration', 0))
                    actual_title = video_info.get('title', video_title)
                    
                normalized_title = normalize_filename(actual_title)
                
                # Check if song already exists
                mp3_file = os.path.join(MUSIC_DIR, f'{normalized_title}.mp3')
                if os.path.exists(mp3_file):
                    logger.info(f"Song already exists, skipping: {actual_title}")
                    continue
                
                # Download the track
                ydl_opts_download = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(MUSIC_DIR, f'{normalized_title}.%(ext)s'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'quiet': True,
                    'no_warnings': True
                }
                
                with yt_dlp.YoutubeDL(ydl_opts_download) as ydl_download:
                    ydl_download.download([video_url])
                
                if not os.path.exists(mp3_file):
                    raise Exception(f"File was not created: {mp3_file}")
                    
                actual_filename = os.path.relpath(mp3_file, BASE_DIR)
                
                if duration == 0:
                    duration = get_audio_duration(mp3_file)
                
                # Add song to database immediately after successful download
                with session_scope() as db_session:
                    try:
                        # Check if song with same filename already exists
                        existing_song = db_session.query(Song).filter_by(filename=actual_filename).first()
                        if not existing_song:
                            # Get max position and add 1
                            max_position = db_session.query(db.func.max(Song.position)).scalar() or -1
                            
                            song = Song(
                                title=actual_title,
                                filename=actual_filename,
                                source='youtube_playlist',
                                duration=duration,
                                position=max_position + 1
                            )
                            db_session.add(song)
                            db_session.commit()
                            logger.info(f"Added song to database immediately: {actual_title}")
                            
                            # Emit update to refresh UI
                            socketio.emit('song_added', {
                                'title': actual_title,
                                'message': f'Added song: {actual_title}'
                            })
                        else:
                            logger.info(f"Song already exists in database: {actual_title}")
                    except Exception as db_error:
                        logger.error(f"Error adding song to database: {actual_title} - {db_error}")
                
                downloaded_songs.append({
                    'title': actual_title,
                    'filename': actual_filename,
                    'duration': duration
                })
                
                logger.info(f"Successfully downloaded: {actual_title}")
                
            except Exception as e:
                logger.error(f"Error downloading track {i} ({video_title}): {e}")
                failed_downloads.append({
                    'title': video_title,
                    'error': str(e)
                })
                continue
        
        result = {
            'playlist_title': playlist_info.get('title', 'Unknown Playlist'),
            'total_tracks': len(entries),
            'downloaded_tracks': len(downloaded_songs),
            'failed_tracks': len(failed_downloads),
            'songs': downloaded_songs,
            'failed_songs': failed_downloads
        }
        
        logger.info(f"Completed playlist download: {result['downloaded_tracks']}/{result['total_tracks']} songs successful")
        
        # Clear state and emit completion event
        clear_download_state()
        socketio.emit('download_progress', {
            'status': 'completed',
            'message': f'Completed! Downloaded {result["downloaded_tracks"]}/{result["total_tracks"]} songs',
            'current': result['total_tracks'],
            'total': result['total_tracks'],
            'downloaded': result['downloaded_tracks'],
            'failed': result['failed_tracks']
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Error downloading playlist from {url}: {e}")
        raise

def download_music(url):
    """Main function to download music - handles both single tracks and playlists"""
    if is_playlist_url(url):
        return download_playlist(url)
    else:
        return download_single_track(url)

# =============================================================================
# API Endpoints for React Frontend
# =============================================================================

@app.route('/api/initial-state')
def api_initial_state():
    """API endpoint to get all initial state for React frontend"""
    try:
        # Check authentication
        is_authenticated = 'user_id' in session
        username = session.get('username', '')
        
        if not is_authenticated:
            return jsonify({
                'is_authenticated': False,
                'username': '',
                'songs': [],
                'schedules': [],
                'is_playing': False,
                'current_song_id': None,
                'current_song_title': None,
                'volume': 100,
                'download_state': get_download_state(),
                'next_schedule': None,
                'disk_usage': {
                    'used': 0,
                    'total': 0,
                    'percent': 0,
                    'used_formatted': '0 GB',
                    'total_formatted': '0 GB'
                },
                'ytdlp_version': ''
            })
        
        disk_usage_info = get_disk_usage()
        
        with session_scope() as db_session:
            # Get songs
            songs = db_session.query(Song).order_by(
                Song.position.asc(),
                Song.last_played_at.is_(None).desc(),
                Song.priority.desc(),
                Song.last_played_at.asc()
            ).all()
            
            songs_data = [{
                'id': s.id,
                'title': s.title,
                'duration': s.duration,
                'source': s.source,
                'file_path': s.filename,
                'position': s.position,
                'last_played_at': s.last_played_at.isoformat() if s.last_played_at else None,
                'priority': s.priority,
                'created_at': s.created_at.isoformat() if s.created_at else None
            } for s in songs]
            
            # Get schedules
            schedules = db_session.query(Schedule).order_by(Schedule.time).all()
            schedules_data = [{
                'id': s.id,
                'time': s.time,
                'is_active': s.enabled,
                'one_time': s.one_time,
                'monday': s.monday,
                'tuesday': s.tuesday,
                'wednesday': s.wednesday,
                'thursday': s.thursday,
                'friday': s.friday,
                'saturday': s.saturday,
                'sunday': s.sunday
            } for s in schedules]
            
            # Get next schedule info
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            weekday = now.strftime("%A").lower()
            
            next_schedules = db_session.query(Schedule).filter(
                Schedule.time > current_time,
                Schedule.enabled == True
            ).order_by(Schedule.time).all()
            
            if not next_schedules:
                next_schedules = db_session.query(Schedule).filter(
                    Schedule.enabled == True
                ).order_by(Schedule.time).all()
            
            next_schedule_info = None
            valid_schedules = [s for s in next_schedules if getattr(s, weekday)]
            
            if valid_schedules:
                next_schedule = valid_schedules[0]
                next_song_to_play = db_session.query(Song).order_by(
                    Song.position.asc(),
                    Song.last_played_at.is_(None).desc(),
                    Song.priority.desc(),
                    Song.last_played_at.asc()
                ).first()
                
                next_schedule_info = {
                    'time': next_schedule.time,
                    'song_title': next_song_to_play.title if next_song_to_play else 'Không có bài hát'
                }
            
            # Get current song title
            current_song_title = None
            if current_song_id:
                current_song = db_session.get(Song, current_song_id)
                if current_song:
                    current_song_title = current_song.title
            
            return jsonify({
                'is_authenticated': True,
                'username': username,
                'songs': songs_data,
                'schedules': schedules_data,
                'is_playing': is_playing,
                'current_song_id': current_song_id,
                'current_song_title': current_song_title,
                'volume': int(volume * 100),
                'download_state': get_download_state(),
                'next_schedule': next_schedule_info,
                'disk_usage': {
                    'used': disk_usage_info.get('used_gb', 0) * 1024 * 1024 * 1024,
                    'total': disk_usage_info.get('total_gb', 0) * 1024 * 1024 * 1024,
                    'percent': disk_usage_info.get('percentage_used', 0),
                    'used_formatted': f"{disk_usage_info.get('used_gb', 0):.2f} GB",
                    'total_formatted': f"{disk_usage_info.get('total_gb', 0):.2f} GB"
                },
                'ytdlp_version': get_ytdlp_version(),
                'settings': {
                    'shuffle_mode': shuffle_mode,
                    'fade_enabled': fade_enabled,
                    'fade_duration': fade_duration
                }
            })
            
    except Exception as e:
        logger.error(f"Error getting initial state: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/login', methods=['POST'])
@csrf.exempt
def api_login():
    """API login endpoint for React frontend"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Vui lòng nhập tên đăng nhập và mật khẩu'}), 400
        
        with session_scope() as db_session:
            user = db_session.query(User).filter_by(username=username).first()
            
            if user and user.check_password(password):
                session['user_id'] = user.id
                session['username'] = user.username
                return jsonify({'success': True, 'username': user.username})
            else:
                return jsonify({'error': 'Sai tên đăng nhập hoặc mật khẩu'}), 401
                
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Lỗi đăng nhập'}), 500

@app.route('/api/logout')
def api_logout():
    """API logout endpoint"""
    session.clear()
    return jsonify({'success': True})

# =============================================================================
# Original Routes
# =============================================================================

@app.route('/')
@login_required
def index():
    try:
        # Get disk usage information
        disk_usage = get_disk_usage()
        
        with session_scope() as session:
            songs = session.query(Song).order_by(
                Song.position.asc(),
                Song.last_played_at.is_(None).desc(),
                Song.priority.desc(),
                Song.last_played_at.asc()
            ).all()

            for song in songs:
                actual_filename = find_actual_file(song.filename)
                if actual_filename != song.filename:
                    song.filename = actual_filename

            schedules = session.query(Schedule).order_by(Schedule.time).all()
            
            # Get next scheduled song info within the same session
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            weekday = now.strftime("%A").lower()

            next_schedules = session.query(Schedule).filter(
                Schedule.time > current_time,
                Schedule.enabled == True
            ).order_by(Schedule.time).all()
            
            if not next_schedules:
                next_schedules = session.query(Schedule).filter(
                    Schedule.enabled == True
                ).order_by(Schedule.time).all()
            
            next_song_info = None
            valid_schedules = [s for s in next_schedules if getattr(s, weekday)]
            
            if valid_schedules:
                next_schedule = valid_schedules[0]
                next_song_to_play = session.query(Song).order_by(
                    Song.position.asc(),
                    Song.last_played_at.is_(None).desc(),
                    Song.priority.desc(),
                    Song.last_played_at.asc()
                ).first()

                weekdays = [day for day, enabled in next_schedule.weekdays.items() if enabled]
                next_song_info = {
                    'time': next_schedule.time,
                    'weekdays': weekdays,
                    'song': next_song_to_play.title if next_song_to_play else None
                }

            # Get current song from session if exists
            current_song = None
            current_pos = 0
            if current_song_id:
                current_song = session.get(Song, current_song_id)
                if pygame.mixer.music.get_busy():
                    pos = pygame.mixer.music.get_pos()
                    if pos >= 0:
                        current_pos = pos / 1000

            return render_template('index.html',
                               songs=songs,
                               schedules=schedules,
                               next_song=next_song_info,
                               current_song=current_song,
                               current_position=current_pos,
                               is_playing=is_playing,
                               volume=volume,
                               disk_usage=disk_usage,
                               ytdlp_version=get_ytdlp_version(),
                               download_state=get_download_state())
    except Exception as e:
        logger.error(f"Error rendering index page: {e}")
        return "Internal Server Error", 500

@app.route('/set-volume/<value>')
@login_required
def set_volume(value):
    global volume
    try:
        percent_value = int(float(value))
        percent_value = max(0, min(100, percent_value))
        volume = percent_value / 100.0
        pygame.mixer.music.set_volume(volume)
        return jsonify({'success': True, 'volume': volume})
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid volume value: {value}")
        return jsonify({
            'success': False,
            'error': 'Invalid volume value. Must be between 0 and 100.'
        }), 400

@app.route('/add-schedule', methods=['POST'])
@login_required
@csrf.exempt
def add_schedule():
    # Support both form data and JSON
    if request.is_json:
        data = request.get_json()
        time = data.get('time')
        one_time = data.get('one_time', False)
        weekdays_selected = [day for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] if data.get(day)]
    else:
        time = request.form.get('time')
        one_time = request.form.get('one_time') == 'true'
        weekdays_selected = request.form.getlist('weekdays')
    
    if not time:
        return jsonify({'success': False, 'message': 'Time is required'}), 400

    try:
        datetime.strptime(time, '%H:%M')

        with session_scope() as session:
            schedule = Schedule(time=time)
            schedule.one_time = one_time
            schedule.monday = 'monday' in weekdays_selected
            schedule.tuesday = 'tuesday' in weekdays_selected
            schedule.wednesday = 'wednesday' in weekdays_selected
            schedule.thursday = 'thursday' in weekdays_selected
            schedule.friday = 'friday' in weekdays_selected
            schedule.saturday = 'saturday' in weekdays_selected
            schedule.sunday = 'sunday' in weekdays_selected
            
            session.add(schedule)
            session.flush()

            schedule_data = {
                'id': schedule.id,
                'time': schedule.time,
                'is_active': schedule.enabled,
                'one_time': schedule.one_time,
                'monday': schedule.monday,
                'tuesday': schedule.tuesday,
                'wednesday': schedule.wednesday,
                'thursday': schedule.thursday,
                'friday': schedule.friday,
                'saturday': schedule.saturday,
                'sunday': schedule.sunday
            }

        # Reload schedules after the database transaction is committed
        schedule_music()
        
        # Broadcast updated next schedule to all clients
        broadcast_next_schedule()
        
        return jsonify(schedule_data)

    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid time format. Use HH:MM.'}), 400
    except Exception as e:
        logger.error(f"Error adding schedule: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

@app.route('/toggle-schedule/<int:id>', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def toggle_schedule(id):
    try:
        with session_scope() as session:
            schedule = session.get(Schedule, id)
            if schedule:
                schedule.enabled = not schedule.enabled
                result = {'success': True, 'is_active': schedule.enabled}
            else:
                return jsonify({'success': False, 'message': 'Schedule not found'}), 404
        
        # Reload schedules after the database transaction is committed
        schedule_music()
        
        # Broadcast updated next schedule to all clients
        broadcast_next_schedule()
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error toggling schedule {id}: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500

@app.route('/delete-schedule/<int:id>', methods=['GET', 'DELETE'])
@login_required
@csrf.exempt
def delete_schedule(id):
    try:
        with session_scope() as session:
            schedule = session.get(Schedule, id)
            if schedule:
                session.delete(schedule)
                result = {'success': True}
            else:
                return jsonify({'success': False, 'message': 'Schedule not found'}), 404
        
        # Reload schedules after the database transaction is committed
        schedule_music()
        
        # Broadcast updated next schedule to all clients
        broadcast_next_schedule()
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting schedule {id}: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500

@app.route('/add-music', methods=['POST'])
@login_required
@csrf.exempt
def add_music():
    # Support both form data and JSON
    if request.is_json:
        data = request.get_json()
        url = data.get('url')
    else:
        url = request.form.get('url')
    
    if not url:
        return jsonify({'success': False, 'message': 'No URL provided'}), 400

    try:
        # Check if it's a playlist to start progress tracking
        if is_playlist_url(url):
            socketio.emit('download_progress', {
                'status': 'starting',
                'message': 'Starting playlist processing...',
                'current': 0,
                'total': 0
            })
        
        music_info = download_music(url)
        
        # Handle playlist response
        if 'songs' in music_info:  # This is a playlist
            playlist_title = music_info['playlist_title']
            downloaded_songs = music_info['songs']
            failed_songs = music_info['failed_songs']
            cancelled = music_info.get('cancelled', False)
            
            if cancelled:
                return jsonify({
                    'success': True,
                    'message': f"Playlist download '{playlist_title}' was cancelled. Downloaded {len(downloaded_songs)} songs.",
                    'cancelled': True
                })
            
            if not downloaded_songs:
                error_msg = f"Unable to download any songs from playlist '{playlist_title}'"
                if failed_songs:
                    error_msg += f". Error: {len(failed_songs)} songs failed"
                return jsonify({'success': False, 'message': error_msg}), 400
            
            # Songs are already added to database during download process
            # Just count them for response
            added_songs = [song['title'] for song in downloaded_songs]
            skipped_songs = []
            
            logger.info(f"Playlist processing completed: {len(added_songs)} songs were added during download")
            
            # Create response message
            message_parts = []
            if added_songs:
                message_parts.append(f"Added {len(added_songs)} songs from playlist '{playlist_title}'")
            if skipped_songs:
                message_parts.append(f"{len(skipped_songs)} songs already exist in playlist")
            if failed_songs:
                message_parts.append(f"{len(failed_songs)} songs failed to download")
            
            response_message = ". ".join(message_parts)
            
            return jsonify({
                'success': True,
                'message': response_message,
                'playlist_info': {
                    'playlist_title': playlist_title,
                    'total_tracks': music_info['total_tracks'],
                    'added_tracks': len(added_songs),
                    'skipped_tracks': len(skipped_songs),
                    'failed_tracks': len(failed_songs)
                }
            })
            
        else:  # This is a single track
            if not music_info['duration']:
                return jsonify({'success': False, 'message': 'Could not determine video duration'})
                
            with session_scope() as session:
                # Check if song with same filename already exists
                existing_song = session.query(Song).filter_by(filename=music_info['filename']).first()
                if existing_song:
                    return jsonify({'success': False, 'message': 'This song already exists in the playlist'}), 400

                # Get max position and add 1
                max_position = session.query(db.func.max(Song.position)).scalar() or -1
                
                song = Song(
                    title=music_info['title'],
                    filename=music_info['filename'],
                    source='youtube',
                    duration=music_info['duration'],
                    position=max_position + 1
                )
                session.add(song)
                return jsonify({'success': True, 'message': 'Music added successfully'})
                
    except Exception as e:
        logger.error(f"Error adding music from URL {url}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/upload-music', methods=['POST'])
@login_required
def upload_music():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': f'Invalid file type. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join('music', filename)
        full_filepath = os.path.join(MUSIC_DIR, filename)

        with session_scope() as session:
            # Check if song with same filename already exists
            existing_song = session.query(Song).filter_by(filename=filepath).first()
            if existing_song:
                return jsonify({'success': False, 'message': 'A file with this name already exists'}), 400

            file.save(full_filepath)
            duration = get_audio_duration(full_filepath)
            
            if duration == 0:
                os.remove(full_filepath)
                return jsonify({'success': False, 'message': 'Could not determine audio duration'}), 400

            # Get max position and add 1
            max_position = session.query(db.func.max(Song.position)).scalar() or -1
            
            song = Song(
                title=os.path.splitext(filename)[0],
                filename=filepath,
                source='upload',
                duration=duration,
                position=max_position + 1
            )
            session.add(song)
            return jsonify({'success': True, 'message': 'File uploaded successfully'})
    except Exception as e:
        logger.error(f"Error uploading file {file.filename}: {e}")
        if os.path.exists(full_filepath):
            os.remove(full_filepath)
        return jsonify({'success': False, 'message': 'Error uploading file'}), 500

@app.route('/update-ytdlp', methods=['POST'])
@login_required
@csrf.exempt
def update_ytdlp_manual():
    """Manual update yt-dlp and reload the module"""
    try:
        logger.info("Manual yt-dlp update requested")
        update_ytdlp()
        
        # Reload yt_dlp module to use new version without restarting server
        import importlib
        import yt_dlp
        importlib.reload(yt_dlp)
        logger.info("yt-dlp module reloaded successfully")
        
        new_version = get_ytdlp_version()
        return jsonify({'success': True, 'message': 'yt-dlp updated successfully', 'version': new_version})
    except Exception as e:
        logger.error(f"Error manually updating yt-dlp: {e}")
        return jsonify({'success': False, 'message': 'Failed to update yt-dlp'}), 500


@app.route('/play/<int:id>', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def play(id):
    success = play_music(id)
    return jsonify({'success': success})

@socketio.on('toggle_play_pause')
def handle_toggle_play_pause():
    global is_playing, current_position, current_song_id
    try:
        logger.info(f"Toggle play/pause - current state: is_playing={is_playing}, current_position={current_position}, current_song_id={current_song_id}")
        
        if pygame.mixer.music.get_busy():
            logger.info("Music is playing, attempting to pause")
            pos = pygame.mixer.music.get_pos()
            logger.info(f"Current position from pygame: {pos}")
            if pos >= 0:
                current_position = pos / 1000
            pygame.mixer.music.pause()
            is_playing = False
            broadcast_playback_state()
            logger.info("Successfully paused music")
        elif current_song_id:
            logger.info("Music is paused, attempting to resume")
            try:
                pygame.mixer.music.unpause()
                is_playing = True
                broadcast_playback_state()
                logger.info("Successfully resumed music")
            except Exception as e:
                logger.error(f"Error during resume: {e}")
                raise
    except Exception as e:
        logger.error(f"Error in toggle_play_pause: {e}")
        emit('error', {'message': str(e)})
        emit('error', {'message': 'Error toggling playback'})

@socketio.on('stop_music')
def handle_stop():
    global current_song_id, current_song_duration, is_playing, current_position
    try:
        if pygame.mixer.music.get_busy():
            # Use fade out if enabled
            if fade_enabled:
                fade_out()
            else:
                pygame.mixer.music.stop()
            current_song_id = None
            current_song_duration = 0
            is_playing = False
            current_position = 0
            broadcast_playback_state()
            emit('music_stopped')
    except Exception as e:
        logger.error(f"Error stopping music: {e}")
        try:
            broadcast_playback_state()
        except Exception:
            pass
        emit('stop_error', {'error': str(e)})

@socketio.on('toggle_shuffle')
def handle_toggle_shuffle():
    """Toggle shuffle mode on/off"""
    global shuffle_mode
    try:
        shuffle_mode = not shuffle_mode
        logger.info(f"Shuffle mode: {shuffle_mode}")
        socketio.emit('settings_updated', {
            'shuffle_mode': shuffle_mode,
            'fade_enabled': fade_enabled,
            'fade_duration': fade_duration
        })
    except Exception as e:
        logger.error(f"Error toggling shuffle: {e}")
        emit('error', {'message': 'Error toggling shuffle'})

@socketio.on('toggle_fade')
def handle_toggle_fade():
    """Toggle fade in/out effect on/off"""
    global fade_enabled
    try:
        fade_enabled = not fade_enabled
        logger.info(f"Fade enabled: {fade_enabled}")
        socketio.emit('settings_updated', {
            'shuffle_mode': shuffle_mode,
            'fade_enabled': fade_enabled,
            'fade_duration': fade_duration
        })
    except Exception as e:
        logger.error(f"Error toggling fade: {e}")
        emit('error', {'message': 'Error toggling fade'})

@socketio.on('set_fade_duration')
def handle_set_fade_duration(data):
    """Set fade duration in seconds"""
    global fade_duration
    try:
        new_duration = float(data.get('duration', 2.0))
        if 0.5 <= new_duration <= 10.0:
            fade_duration = new_duration
            logger.info(f"Fade duration set to: {fade_duration}s")
            socketio.emit('settings_updated', {
                'shuffle_mode': shuffle_mode,
                'fade_enabled': fade_enabled,
                'fade_duration': fade_duration
            })
        else:
            emit('error', {'message': 'Fade duration must be between 0.5 and 10 seconds'})
    except Exception as e:
        logger.error(f"Error setting fade duration: {e}")
        emit('error', {'message': 'Error setting fade duration'})

@app.route('/seek', methods=['POST'])
@login_required
@csrf.exempt
def seek():
    """Seek to a specific position in the current song."""
    global current_position, is_playing
    try:
        if request.is_json:
            data = request.get_json()
            position = data.get('position', 0)
        else:
            position = float(request.form.get('position', 0))
        
        logger.info(f"Seek requested to position: {position}")
        
        if not current_song_id:
            return jsonify({'success': False, 'message': 'No song is currently loaded'}), 400

        with session_scope() as session:
            current_song = session.get(Song, current_song_id)
            if not current_song:
                return jsonify({'success': False, 'message': 'Song not found in database'}), 404

            if not (0 <= position <= current_song.duration):
                return jsonify({'success': False, 'message': 'Invalid position'}), 400

            # Reload and play from position
            actual_filename = find_actual_file(current_song.filename)
            file_path = os.path.join(BASE_DIR, actual_filename)
            
            logger.info(f"Seeking in file: {file_path}")
        
            if not os.path.exists(file_path):
                return jsonify({'success': False, 'message': 'Song file not found'}), 404

            # Stop current playback
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            
            # Reload the file
            pygame.mixer.music.load(file_path)
            
            # For MP3 files, use play with start parameter
            # Convert to float for pygame
            seek_position = float(position)
            logger.info(f"Starting playback at position: {seek_position}")
            
            # Set seek_offset before playing
            global seek_offset
            seek_offset = seek_position
            
            # Play from the beginning first
            pygame.mixer.music.play()
            
            # Then seek to position (works better with MP3)
            try:
                pygame.mixer.music.rewind()
                pygame.mixer.music.set_pos(seek_position)
                logger.info(f"set_pos successful to {seek_position}, seek_offset set to {seek_offset}")
            except Exception as seek_error:
                logger.warning(f"set_pos failed: {seek_error}, trying play with start")
                pygame.mixer.music.stop()
                pygame.mixer.music.play(start=seek_position)
            
            current_position = seek_position
            is_playing = True
        
        broadcast_playback_state()
        
        return jsonify({'success': True, 'position': current_position})
    except Exception as e:
        logger.error(f"Error seeking to position {position}: {e}")
        return jsonify({'success': False, 'message': f'Error during seek: {str(e)}'}), 500

@app.route('/delete-song/<int:id>', methods=['GET', 'DELETE'])
@login_required
@csrf.exempt
def delete_song(id):
    global current_song_id, current_song_duration, is_playing, current_position
    try:
        with session_scope() as session:
            song = session.get(Song, id)
            if not song:
                return jsonify({'success': False, 'message': 'Song not found'}), 404
                
            # Stop playback if this is the current song
            if current_song_id == id:
                pygame.mixer.music.stop()
                current_song_id = None
                current_song_duration = 0
                is_playing = False
                current_position = 0
                broadcast_playback_state()

            actual_filename = find_actual_file(song.filename)
            filepath = os.path.join(BASE_DIR, actual_filename)
            if os.path.exists(filepath):
                os.remove(filepath)
            session.delete(song)
            return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting song {id}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/stream/<int:id>')
@login_required
def stream(id):
    try:
        with session_scope() as session:
            song = session.get(Song, id)
            if song:
                actual_filename = find_actual_file(song.filename)
                return send_file(os.path.join(BASE_DIR, actual_filename))
            return jsonify({'success': False, 'message': 'Song not found'}), 404
    except Exception as e:
        logger.error(f"Error streaming song {id}: {e}")
        return jsonify({'success': False, 'message': 'Error streaming file'}), 500

@socketio.on('set_volume')
def handle_volume(data):
    global volume
    try:
        # Support both 'value' and 'volume' keys
        vol = data.get('volume', data.get('value'))
        percent_value = int(float(vol))
        percent_value = max(0, min(100, percent_value))
        volume = percent_value / 100.0
        pygame.mixer.music.set_volume(volume)
        emit('volume_updated', {'volume': percent_value}, broadcast=True)
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid volume value: {data}")
        emit('error', {'message': 'Invalid volume value. Must be between 0 and 100.'})
    except Exception as e:
        logger.error(f"Error setting volume: {e}")
        emit('error', {'message': 'Error setting volume'})

@app.route('/update-song-order', methods=['POST'])
@login_required
@csrf.exempt
def update_song_order():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Support both 'songs' array and 'song_ids' array formats
        song_order = data.get('songs')
        song_ids = data.get('song_ids')
        
        if song_ids:
            # React frontend sends song_ids as array of IDs in new order
            with session_scope() as session:
                for position, song_id in enumerate(song_ids):
                    song = session.get(Song, song_id)
                    if song:
                        song.position = position
            return jsonify({'success': True})
        
        if not song_order:
            return jsonify({'success': False, 'message': 'No song order data provided'}), 400
            
        # Original format: List of {id: song_id, position: new_position}
        
        with session_scope() as session:
            for item in song_order:
                song_id = item.get('id')
                position = item.get('position')
                
                if song_id is None or position is None:
                    continue
                    
                song = session.get(Song, song_id)
                if song:
                    song.position = position
            
            return jsonify({'success': True})
            
    except Exception as e:
        logger.error(f"Error updating song order: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500

def reset_song_positions():
    """Reset song positions based on play history and priority"""
    try:
        with session_scope() as session:
            # Get all songs ordered by priority (desc), then by last_played_at (asc, nulls first)
            songs = session.query(Song).order_by(
                Song.priority.desc(),
                Song.last_played_at.is_(None).desc(),
                Song.last_played_at.asc()
            ).all()
            
            # Reassign positions starting from 0
            for i, song in enumerate(songs):
                song.position = i
                
            logger.info(f"Reset positions for {len(songs)} songs")
            return True
            
    except Exception as e:
        logger.error(f"Error resetting song positions: {e}")
        return False

@app.route('/reset-playlist-order', methods=['POST'])
@login_required
@csrf.exempt
def reset_playlist_order():
    """Reset playlist order based on play history and priority"""
    try:
        success = reset_song_positions()
        if success:
            return jsonify({'success': True, 'message': 'Playlist order reset successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to reset playlist order'}), 500
    except Exception as e:
        logger.error(f"Error in reset playlist order route: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500

@socketio.on('sort_unplayed_first')
def handle_sort_unplayed_first():
    """Sort unplayed songs to the top of the playlist via socket"""
    try:
        with app.app_context():
            with session_scope() as session:
                # Get all songs
                all_songs = session.query(Song).all()
                
                # Divide into 2 groups: unplayed and played
                unplayed_songs = [song for song in all_songs if song.last_played_at is None]
                played_songs = [song for song in all_songs if song.last_played_at is not None]
                
                # Sort unplayed songs by priority desc, id asc (to maintain add order)
                unplayed_songs.sort(key=lambda x: (-x.priority, x.id))
                
                # Sort played songs by last_played_at asc (oldest played first)
                played_songs.sort(key=lambda x: x.last_played_at)
                
                # Combine 2 groups: unplayed first, played after
                sorted_songs = unplayed_songs + played_songs
                
                # Update position for all songs
                for index, song in enumerate(sorted_songs):
                    song.position = index
                
                logger.info(f"Sorted {len(unplayed_songs)} unplayed songs to top, {len(played_songs)} played songs to bottom")
                
                # Prepare song data for frontend
                songs_data = []
                for song in sorted_songs:
                    songs_data.append({
                        'id': song.id,
                        'title': song.title,
                        'source': song.source,
                        'duration': song.duration,
                        'position': song.position,
                        'last_played_at': song.last_played_at.isoformat() if song.last_played_at else None,
                        'duration_formatted': f"{song.duration//60}:{song.duration%60:02d}"
                    })
                
                # Emit success with new song order
                emit('sort_completed', {
                    'success': True,
                    'message': f'Moved {len(unplayed_songs)} unplayed songs to top',
                    'unplayed_count': len(unplayed_songs),
                    'played_count': len(played_songs),
                    'songs': songs_data
                })
                
    except Exception as e:
        logger.error(f"Error sorting unplayed songs first: {e}")
        emit('sort_error', {
            'success': False,
            'message': 'Error sorting playlist'
        })

@app.route('/get-disk-usage')
@login_required
def disk_usage_api():
    """API endpoint to get disk usage information"""
    try:
        disk_info = get_disk_usage()
        return jsonify({
            'used': disk_info.get('used_gb', 0) * 1024 * 1024 * 1024,
            'total': disk_info.get('total_gb', 0) * 1024 * 1024 * 1024,
            'percent': disk_info.get('percentage_used', 0),
            'used_formatted': f"{disk_info.get('used_gb', 0):.2f} GB",
            'total_formatted': f"{disk_info.get('total_gb', 0):.2f} GB"
        })
    except Exception as e:
        logger.error(f"Error getting disk usage: {e}")
        return jsonify({'success': False, 'message': 'Error retrieving disk space information'}), 500

@app.route('/get-download-state')
@login_required
def get_download_state_api():
    """API endpoint to get current download state"""
    try:
        return jsonify({'success': True, 'data': get_download_state()})
    except Exception as e:
        logger.error(f"Error getting download state: {e}")
        return jsonify({'success': False, 'message': 'Error retrieving download state'}), 500

@app.route('/cancel-download', methods=['POST'])
@login_required
@csrf.exempt
def cancel_download_api():
    """API endpoint to cancel current download"""
    try:
        success = cancel_download()
        if success:
            return jsonify({'success': True, 'message': 'Download cancelled'})
        else:
            return jsonify({'success': False, 'message': 'No download in progress'}), 400
    except Exception as e:
        logger.error(f"Error cancelling download: {e}")
        return jsonify({'success': False, 'message': 'Error cancelling download'}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login route"""
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            error = "Please provide both username and password"
        else:
            with session_scope() as db_session:
                user = db_session.query(User).filter_by(username=username).first()
                
                if user and user.check_password(password):
                    session['user_id'] = user.id
                    session['username'] = user.username
                    
                    # Redirect to requested page or default to index
                    next_page = request.args.get('next', url_for('index'))
                    return redirect(next_page)
                else:
                    error = "Invalid username or password"
    
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    """Logout route"""
    session.clear()
    return redirect(url_for('login'))

# =============================================================================
# Serve React Frontend (Production)
# =============================================================================

REACT_BUILD_DIR = os.path.join(BASE_DIR, 'static', 'react')

@app.route('/app')
@app.route('/app/')
@app.route('/app/<path:path>')
def serve_react(path=''):
    """Serve React frontend for production"""
    if path and os.path.exists(os.path.join(REACT_BUILD_DIR, path)):
        return send_file(os.path.join(REACT_BUILD_DIR, path))
    return send_file(os.path.join(REACT_BUILD_DIR, 'index.html'))

@app.route('/assets/<path:filename>')
def serve_react_assets(filename):
    """Serve React static assets"""
    return send_file(os.path.join(REACT_BUILD_DIR, 'assets', filename))

# =============================================================================
# Scheduler and Initialization
# =============================================================================

def list_scheduler_jobs():
    """List all current jobs in the scheduler"""
    global scheduler
    if scheduler is None:
        logger.error("Scheduler not initialized")
        return
        
    jobs = scheduler.get_jobs()
    for job in jobs:
        logger.info(f"Job {job.id}: {job.func.__name__} at {job.next_run_time}")

with app.app_context():
    db.create_all()
    init_scheduler()
    init_admin_user()
    schedule_music()
    list_scheduler_jobs()

if __name__ == '__main__':
    # For development only - in production use Gunicorn with eventlet
    # eventlet monkey patching is already done at the top of the file
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)