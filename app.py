# Apply eventlet monkey patching at the very start
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, jsonify, request, redirect, url_for, send_file, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event as sa_event
from sqlalchemy.engine import Engine
from flask_socketio import SocketIO, emit
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pygame
import time
import os
import json
import logging
import shutil
import secrets
import sqlite3
from werkzeug.utils import secure_filename
import mutagen
from mutagen.mp3 import MP3
import glob
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()
import youtube_downloader  # noqa: E402 - reads YTDLP_* env at import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set APScheduler logging to WARNING level to reduce noise
logging.getLogger('apscheduler').setLevel(logging.WARNING)

# Constants
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a'}
DEFAULT_VOLUME = 0.5
BROADCAST_INTERVAL = 1.0  # seconds; 1s is smooth enough for the progress bar and cheap on a Pi
UPDATE_YTDLP_HOUR = 3  # off-peak; skipped while playing or downloading
PROGRESS_EMIT_INTERVAL = 1.0  # seconds between download progress events
MAX_UPLOAD_SIZE = 150 * 1024 * 1024  # 150MB

# Global download state
download_state = {
    'active': False,
    'status': '',
    'message': '',
    'current': 0,
    'total': 0,
    'current_song': '',
    'playlist_title': '',
    'cancelled': False,
    'percent': 0
}
download_job = None  # youtube_downloader.DownloadJob while a download runs
ytdlp_updating = False  # blocks new downloads while pip rewrites the yt-dlp package

app = Flask(__name__)
csrf = CSRFProtect(app)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///music.db')
app.config['UPLOAD_FOLDER'] = 'music'
app.config['SECRET_KEY'] = 'super-secret-key-for-music-scheduler-app' # In production, use a secure random key and keep it secret!
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours session lifetime
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE # Limit upload size to prevent abuse
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' # Adjust as needed for your frontend setup (e.g., 'None' for cross-origin)
app.config['SESSION_COOKIE_SECURE'] = False # Set to True if using HTTPS
app.config['REMEMBER_COOKIE_DURATION'] = 365 * 24 * 3600  # 1 year

socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*', message_queue=None)
db = SQLAlchemy(app)

@sa_event.listens_for(Engine, 'connect')
def _set_sqlite_pragmas(dbapi_conn, _record):
    """WAL + NORMAL sync: far fewer fsyncs on the Pi's SD card, readers never block writers."""
    if isinstance(dbapi_conn, sqlite3.Connection):
        cursor = dbapi_conn.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        cursor.close()

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

# Scheduled playlist queue for sequential playback (play_all mode)
scheduled_playlist_queue = []  # List of song IDs to play sequentially
scheduled_playlist_volume = 100  # Volume for the current scheduled playlist
# Download state management functions
def publish_download_state(status, message='', current=0, total=0, current_song='', percent=0, cancelled=False):
    """Update global download state and push it to every client."""
    download_state.update({
        'active': status not in ('completed', 'error', 'cancelled'),
        'status': status,
        'message': message,
        'current': current,
        'total': total,
        'current_song': current_song,
        'cancelled': cancelled,
        'percent': round(percent, 1),
    })
    logger.debug(f"Download state updated: {download_state}")
    socketio.emit('download_progress', dict(download_state))

def get_download_state():
    """Get current download state"""
    return download_state.copy()

def cancel_download():
    """Cancel the running download job, if any"""
    if download_job is None:
        return False
    download_job.cancel()
    publish_download_state('cancelling', 'Đang hủy...', download_state['current'], download_state['total'])
    logger.info("Download cancelled by user")
    return True

def init_scheduler():
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler()
        scheduler.start()
        socketio.start_background_task(playback_broadcast_loop)
        scheduler.add_job(scheduled_ytdlp_update, 'cron', hour=UPDATE_YTDLP_HOUR, id='update_ytdlp')

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

_title_cache = {'song_id': None, 'title': None}
_last_idle_payload = None

def get_cached_song_title(song_id):
    """Title of the playing song; the DB is only hit when the song changes."""
    if song_id is None:
        return None
    if _title_cache['song_id'] != song_id:
        with app.app_context():
            with session_scope() as session:
                song = session.get(Song, song_id)
                _title_cache.update(song_id=song_id, title=song.title if song else None)
    return _title_cache['title']

def playback_broadcast_loop():
    """Single long-lived greenlet replacing the old 0.5s APScheduler job."""
    while True:
        broadcast_playback_state(force=False)
        socketio.sleep(BROADCAST_INTERVAL)

def broadcast_playback_state(force=True):
    """Broadcast current playback state to all clients.

    With force=False (the periodic loop) nothing is sent while idle and unchanged.
    """
    global _last_idle_payload
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
            finished_song_id = current_song_id
            current_position = 0
            current_song_id = None
            current_song_duration = 0
            is_playing = False
            
            # Check if song should be deleted after playing
            deleted_song_id = None
            try:
                with app.app_context():
                    with session_scope() as session:
                        song = session.get(Song, finished_song_id)
                        if song and song.delete_after_play:
                            logger.info(f"Deleting song after play: {song.title}")
                            deleted_song_id = song.id
                            actual_filename = find_actual_file(song.filename)
                            filepath = os.path.join(BASE_DIR, actual_filename)
                            if os.path.exists(filepath):
                                os.remove(filepath)
                            session.delete(song)
            except Exception as e:
                logger.error(f"Error deleting song after play: {e}")
            
            # Emit song finished event
            socketio.emit('song_finished', {
                'message': 'Song playback completed',
                'deleted_song_id': deleted_song_id
            })

            # Auto-advance scheduled playlist queue (play_all mode)
            if scheduled_playlist_queue:
                next_id = scheduled_playlist_queue.pop(0)
                logger.info(f"Auto-advancing scheduled playlist queue: playing song_id={next_id}, remaining={len(scheduled_playlist_queue)}")
                def _play_queued():
                    with app.app_context():
                        apply_volume(scheduled_playlist_volume)
                        play_music(next_id)
                socketio.start_background_task(_play_queued)

        try:
            current_title = get_cached_song_title(current_song_id)
        except Exception as e:
            logger.error(f"Error getting song title: {e}")
            current_title = None

        payload = {
            'position': current_position,
            'duration': current_song_duration,
            'is_playing': music_busy,
            'volume': int(volume * 100),
            'current_song_id': current_song_id,
            'current_song_title': current_title
        }
        if not music_busy:
            if not force and payload == _last_idle_payload:
                return
            _last_idle_payload = payload
        else:
            _last_idle_payload = None
        socketio.emit('playback_update', payload)
    except Exception as e:
        logger.error(f"Error in broadcast_playback_state: {e}")


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
class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    songs = db.relationship('Song', backref='playlist', lazy=True)

class Holiday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False, unique=True)  # Format: "YYYY-MM-DD"
    name = db.Column(db.String(200), nullable=False)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(5), nullable=False)  # Format: "HH:MM"
    enabled = db.Column(db.Boolean, default=True)
    one_time = db.Column(db.Boolean, default=False)  # If True, disable after playing once
    volume = db.Column(db.Integer, default=100)  # Volume level (0-100)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'), nullable=True)  # If set, play from this playlist
    play_all = db.Column(db.Boolean, default=False)  # If True, play all songs in the playlist sequentially
    playlist = db.relationship('Playlist', backref='schedules')
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
    delete_after_play = db.Column(db.Boolean, default=False)  # Delete song after playing
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'), nullable=True)
    source = db.Column(db.String(50))
    duration = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_played_at = db.Column(db.DateTime, nullable=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    remember_token = db.Column(db.String(100), unique=True, nullable=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_remember_token(self):
        self.remember_token = secrets.token_urlsafe(64)
        return self.remember_token

# Create a function to check if a user is logged in
def get_authenticated_user():
    """Check authentication via session cookie, with remember_token fallback.
    Returns (user_id, username) or (None, None)."""
    # Check session first
    if 'user_id' in session:
        return session['user_id'], session.get('username', '')
    
    # Check remember_token cookie for persistent login
    remember_token = request.cookies.get('remember_token')
    if remember_token:
        try:
            with session_scope() as db_session:
                user = db_session.query(User).filter_by(remember_token=remember_token).first()
                if user:
                    # Restore session from remember token
                    session['user_id'] = user.id
                    session['username'] = user.username
                    session.permanent = True
                    return user.id, user.username
        except Exception as e:
            logger.error(f"[Auth] Error checking remember_token: {e}")
    
    return None, None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id, _ = get_authenticated_user()
        if user_id is None:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Create a decorator for SocketIO events that require authentication
def socketio_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' in session:
            return f(*args, **kwargs)
        emit('error', {'message': 'Unauthorized. Please login.'})
        return
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
            # Rebuild only the playback schedules; system jobs (yt-dlp update) stay as they are
            for job in scheduler.get_jobs():
                if job.id.startswith('schedule_'):
                    job.remove()

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
                            
                            # Pass schedule_id, one_time flag, volume, playlist_id, and play_all to the job
                            volume = schedule.volume if schedule.volume is not None else 100
                            playlist_id = schedule.playlist_id
                            play_all = schedule.play_all if schedule.play_all is not None else False
                            job_args = [schedule.id, schedule.one_time, volume, playlist_id, play_all]
                            
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
                                logger.info(f"Added job {job_id} with next run today at {schedule_time}, one_time={schedule.one_time}, playlist_id={playlist_id}")
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
                                logger.info(f"Added job {job_id} for days: {','.join(days_of_week)} at {hour:02d}:{minute:02d}, one_time={schedule.one_time}, playlist_id={playlist_id}")
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
            return False

def play_next_song(schedule_id=None, one_time=False, volume=100, playlist_id=None, play_all=False):
    global scheduled_playlist_queue, scheduled_playlist_volume
    with app.app_context():
        logger.info(f"Scheduler triggered play next song (schedule_id={schedule_id}, one_time={one_time}, shuffle={shuffle_mode}, volume={volume}, playlist_id={playlist_id}, play_all={play_all})")
        try:
            # Check if today is a holiday
            today_str = datetime.now().strftime('%Y-%m-%d')
            with session_scope() as session:
                holiday = session.query(Holiday).filter_by(date=today_str).first()
                if holiday:
                    logger.info(f"Today is a holiday ({holiday.name}), skipping scheduled playback")
                    return

            with session_scope() as session:
                # Build base query with playlist filter
                base_query = session.query(Song)
                if playlist_id:
                    base_query = base_query.filter(Song.playlist_id == playlist_id)

                if play_all and playlist_id:
                    # Play all songs in the playlist sequentially
                    all_songs = base_query.order_by(
                        Song.position.asc(),
                        Song.last_played_at.is_(None).desc(),
                        Song.priority.desc(),
                        Song.last_played_at.asc()
                    ).all()
                    if all_songs:
                        first_song = all_songs[0]
                        # Populate global queue with remaining songs
                        scheduled_playlist_queue = [s.id for s in all_songs[1:]]
                        scheduled_playlist_volume = volume
                        logger.info(f"play_all mode: {len(all_songs)} songs queued, starting with '{first_song.title}'")
                        apply_volume(volume)
                        socketio.emit('schedule_triggered', {
                            'song_id': first_song.id,
                            'title': first_song.title,
                            'time': datetime.now().strftime("%H:%M"),
                            'volume': volume,
                            'play_all': True,
                            'total_songs': len(all_songs)
                        })
                        play_music(first_song.id)
                    else:
                        logger.warning(f"play_all mode: no songs found in playlist_id={playlist_id}")
                else:
                    # Clear any existing queue
                    scheduled_playlist_queue = []

                    if shuffle_mode:
                        # Shuffle mode: pick a random song
                        from sqlalchemy.sql.expression import func
                        next_song = base_query.order_by(func.random()).first()
                        logger.info(f"Shuffle mode: randomly selected song (playlist_id={playlist_id})")
                    else:
                        # Normal mode: prioritize songs that haven't been played
                        next_song = base_query.order_by(
                            Song.position.asc(),
                            Song.last_played_at.is_(None).desc(),
                            Song.priority.desc(),
                            Song.last_played_at.asc()
                        ).first()

                    if next_song:
                        logger.info(f"Playing song: {next_song.title} (playlist_id={next_song.playlist_id})")
                        # Set volume before playing
                        apply_volume(volume)
                        # Trigger playlist update through socket
                        socketio.emit('schedule_triggered', {
                            'song_id': next_song.id,
                            'title': next_song.title,
                            'time': datetime.now().strftime("%H:%M"),
                            'volume': volume
                        })
                        play_music(next_song.id)
                    else:
                        logger.warning(f"No songs found (playlist_id={playlist_id})")

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

            # Broadcast next schedule update after potential disable
            if one_time and schedule_id:
                broadcast_next_schedule()
                schedule_music()  # Reload schedules to remove the disabled job

        except Exception as e:
            logger.error(f"Error playing next song: {e}")

def play_music(song_id):
    global current_song_id, current_song_duration, is_playing, current_position, seek_offset
    _title_cache['song_id'] = None  # SQLite may reuse ids of deleted songs
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

def serialize_songs(db_session):
    """All songs in playlist order, in the shape the React frontend expects."""
    songs = db_session.query(Song).order_by(
        Song.position.asc(),
        Song.last_played_at.is_(None).desc(),
        Song.priority.desc(),
        Song.last_played_at.asc()
    ).all()
    return [{
        'id': s.id,
        'title': s.title,
        'duration': s.duration,
        'source': s.source,
        'file_path': s.filename,
        'position': s.position,
        'delete_after_play': s.delete_after_play or False,
        'playlist_id': s.playlist_id,
        'last_played_at': s.last_played_at.isoformat() if s.last_played_at else None,
        'priority': s.priority,
        'created_at': s.created_at.isoformat() if s.created_at else None
    } for s in songs]

def add_downloaded_song(item, source):
    """Insert a finished yt-dlp item into the DB. Returns False if it already existed."""
    filepath = item.get('filepath')
    if not filepath or not os.path.isfile(filepath):
        logger.error(f"Downloaded file missing: {filepath}")
        return False
    filename = os.path.relpath(filepath, BASE_DIR)
    with session_scope() as db_session:
        if db_session.query(Song).filter_by(filename=filename).first():
            logger.info(f"Song already exists in database: {filename}")
            return False
        max_position = db_session.query(db.func.max(Song.position)).scalar() or -1
        db_session.add(Song(
            title=item.get('title') or os.path.splitext(os.path.basename(filename))[0],
            filename=filename,
            source=source,
            duration=int(item.get('duration') or 0) or get_audio_duration(filepath),
            position=max_position + 1
        ))
    with session_scope() as db_session:
        socketio.emit('song_added', {'title': item.get('title'), 'songs': serialize_songs(db_session)})
    return True

def run_download_job(job):
    """Drive a DownloadJob from a greenlet: persist songs and publish progress."""
    global download_job
    source = 'youtube_playlist' if job.is_playlist else 'youtube'
    index, total, title = 0, 1, ''
    added, existing = 0, 0
    failed_items = set()  # yt-dlp may print several ERROR lines for one item
    last_emit = 0.0
    try:
        with app.app_context():
            for event in job.events():
                kind = event['type']
                if kind == 'start':
                    index = event.get('playlist_index') or index + 1
                    total = max(event.get('n_entries') or total, index)
                    title = event.get('title') or ''
                    publish_download_state('downloading', f'Đang tải bài {index}/{total}', index, total, title,
                                           percent=(index - 1) / total * 100)
                elif kind == 'progress' and time.monotonic() - last_emit >= PROGRESS_EMIT_INTERVAL:
                    last_emit = time.monotonic()
                    publish_download_state('downloading', f'Đang tải bài {index}/{total}', index, total, title,
                                           percent=((index - 1) + event['percent'] / 100) / total * 100)
                elif kind == 'done':
                    try:
                        if add_downloaded_song(event, source):
                            added += 1
                        else:
                            existing += 1
                    except Exception as e:
                        # One bad row must not abort the rest of a playlist
                        logger.error(f"Could not save downloaded song {event.get('filepath')}: {e}")
                        failed_items.add(index)
                elif kind == 'error':
                    failed_items.add(index)
                elif kind == 'finished':
                    finish_download(event, added, existing, len(failed_items), total)
    except Exception as e:
        logger.error(f"Download job failed for {job.url}: {e}")
        publish_download_state('error', 'Lỗi khi tải nhạc, xem log máy chủ')
    finally:
        download_job = None

def finish_download(result, added, existing, failed, total):
    summary = f'Đã thêm {added} bài'
    if existing:
        summary += f', {existing} bài đã có sẵn'
    if failed:
        summary += f', {failed} bài lỗi'
    if result['cancelled']:
        publish_download_state('cancelled', f'Đã hủy. {summary}', cancelled=True)
    elif added or existing:
        publish_download_state('completed', summary, total, total, percent=100)
    else:
        publish_download_state('error', result['error'] or 'Không tải được bài nào')
    logger.info(f"Download finished: {summary} (exit {result['returncode']})")

def scheduled_ytdlp_update():
    """Nightly yt-dlp upgrade; never competes with playback or a running download."""
    global ytdlp_updating
    if is_playing or download_job is not None or ytdlp_updating:
        logger.info("Skipping scheduled yt-dlp update: player or download busy")
        return
    ytdlp_updating = True
    try:
        youtube_downloader.update_ytdlp()
    except Exception as e:
        logger.error(f"Scheduled yt-dlp update failed: {e}")
    finally:
        ytdlp_updating = False

# =============================================================================
# API Endpoints for React Frontend
# =============================================================================

@app.route('/api/initial-state')
def api_initial_state():
    """API endpoint to get all initial state for React frontend"""
    try:
        # Check authentication via session or token
        user_id, username = get_authenticated_user()
        is_authenticated = user_id is not None
        
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
            songs_data = serialize_songs(db_session)
            
            # Get schedules
            schedules = db_session.query(Schedule).order_by(Schedule.time).all()
            schedules_data = [{
                'id': s.id,
                'time': s.time,
                'is_active': s.enabled,
                'one_time': s.one_time,
                'volume': s.volume if s.volume is not None else 100,
                'playlist_id': s.playlist_id,
                'play_all': s.play_all if s.play_all is not None else False,
                'monday': s.monday,
                'tuesday': s.tuesday,
                'wednesday': s.wednesday,
                'thursday': s.thursday,
                'friday': s.friday,
                'saturday': s.saturday,
                'sunday': s.sunday
            } for s in schedules]
            
            # Get holidays
            holidays = db_session.query(Holiday).order_by(Holiday.date.asc()).all()
            holidays_data = [{
                'id': h.id,
                'date': h.date,
                'name': h.name
            } for h in holidays]
            
            # Get playlists
            playlists = db_session.query(Playlist).order_by(Playlist.name.asc()).all()
            playlists_data = [{
                'id': p.id,
                'name': p.name,
                'song_count': db_session.query(Song).filter_by(playlist_id=p.id).count(),
                'created_at': p.created_at.isoformat() if p.created_at else None
            } for p in playlists]
            
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
                # Filter songs by schedule's playlist
                song_query = db_session.query(Song)
                if next_schedule.playlist_id:
                    song_query = song_query.filter(Song.playlist_id == next_schedule.playlist_id)
                next_song_to_play = song_query.order_by(
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
                'holidays': holidays_data,
                'playlists': playlists_data,
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
                'ytdlp_version': youtube_downloader.get_ytdlp_version(),
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
        data = request.get_json(silent=True)

        if data is None:
            # Fallback: try form data
            data = request.form.to_dict()

        if not data:
            logger.warning("Login failed: empty request body")
            return jsonify({'error': 'Không nhận được dữ liệu'}), 400

        username = data.get('username')
        password = data.get('password')

        logger.info(f"Login attempt for username: '{username}'")
        
        if not username or not password:
            logger.warning("Login failed: missing username or password")
            return jsonify({'error': 'Vui lòng nhập tên đăng nhập và mật khẩu'}), 400
        
        with session_scope() as db_session:
            user = db_session.query(User).filter_by(username=username).first()
            
            if user is None:
                logger.warning(f"Login failed: user '{username}' not found")
                return jsonify({'error': 'Sai tên đăng nhập hoặc mật khẩu'}), 401

            if user.check_password(password):
                session['user_id'] = user.id
                session['username'] = user.username
                session.permanent = True
                
                # Generate remember_token for persistent login
                remember_token = user.generate_remember_token()
                
                logger.info(f"Login success for user: '{username}'")
                response = jsonify({'success': True, 'username': user.username})
                # Set remember_token cookie (1 year)
                response.set_cookie(
                    'remember_token', 
                    remember_token,
                    max_age=365 * 24 * 3600,
                    httponly=True,
                    samesite='Lax'
                )
                return response
            else:
                logger.warning(f"Login failed: wrong password for user '{username}'")
                return jsonify({'error': 'Sai tên đăng nhập hoặc mật khẩu'}), 401
                
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return jsonify({'error': 'Lỗi đăng nhập'}), 500

@app.route('/api/logout')
def api_logout():
    """API logout endpoint"""
    # Clear remember_token from DB
    remember_token = request.cookies.get('remember_token')
    if remember_token:
        try:
            with session_scope() as db_session:
                user = db_session.query(User).filter_by(remember_token=remember_token).first()
                if user:
                    user.remember_token = None
        except Exception as e:
            logger.error(f"Error clearing remember_token: {e}")
    
    session.clear()
    response = jsonify({'success': True})
    response.delete_cookie('remember_token')
    return response

# =============================================================================
# Original Routes
# =============================================================================

@app.route('/')
# @login_required
def index():
    # Serve React frontend
    return send_from_directory('static/react', 'index.html')

def apply_volume(value):
    global volume
    try:
        percent_value = int(float(value))
        percent_value = max(0, min(100, percent_value))
        volume = percent_value / 100.0
        pygame.mixer.music.set_volume(volume)
        return True, volume
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid volume value: {value}")
        return False, str(e)

@app.route('/set-volume/<value>')
@login_required
def set_volume(value):
    success, result = apply_volume(value)
    if success:
        return jsonify({'success': True, 'volume': result})
    else:
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
        volume = data.get('volume', 100)
        playlist_id = data.get('playlist_id')  # Optional playlist assignment
        play_all = data.get('play_all', False)  # Play all songs in playlist sequentially
        weekdays_selected = [day for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] if data.get(day)]
    else:
        time = request.form.get('time')
        one_time = request.form.get('one_time') == 'true'
        volume = int(request.form.get('volume', 100))
        playlist_id = request.form.get('playlist_id') or None
        play_all = request.form.get('play_all') == 'true'
        weekdays_selected = request.form.getlist('weekdays')
    
    if not time:
        return jsonify({'success': False, 'message': 'Time is required'}), 400
    
    # Validate volume
    try:
        volume = int(volume)
        if volume < 0 or volume > 100:
            volume = 100
    except (ValueError, TypeError):
        volume = 100

    try:
        datetime.strptime(time, '%H:%M')

        with session_scope() as session:
            schedule = Schedule(time=time)
            schedule.one_time = one_time
            schedule.volume = volume
            schedule.playlist_id = int(playlist_id) if playlist_id else None
            schedule.play_all = bool(play_all) if schedule.playlist_id else False
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
                'volume': schedule.volume,
                'playlist_id': schedule.playlist_id,
                'play_all': schedule.play_all if schedule.play_all is not None else False,
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

@app.route('/toggle-schedule-play-all/<int:id>', methods=['POST'])
@login_required
@csrf.exempt
def toggle_schedule_play_all(id):
    try:
        with session_scope() as session:
            schedule = session.get(Schedule, id)
            if schedule:
                if not schedule.playlist_id:
                    return jsonify({'success': False, 'message': 'Schedule has no playlist selected'}), 400
                schedule.play_all = not (schedule.play_all or False)
                result = {'success': True, 'play_all': schedule.play_all}
            else:
                return jsonify({'success': False, 'message': 'Schedule not found'}), 404

        # Reload schedules to pick up the updated play_all arg
        schedule_music()

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error toggling play_all for schedule {id}: {e}")
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

# Holiday API endpoints
@app.route('/api/holidays', methods=['GET'])
@login_required
def get_holidays():
    try:
        with session_scope() as session:
            holidays = session.query(Holiday).order_by(Holiday.date.asc()).all()
            return jsonify([{
                'id': h.id,
                'date': h.date,
                'name': h.name
            } for h in holidays])
    except Exception as e:
        logger.error(f"Error getting holidays: {e}")
        return jsonify([])

@app.route('/api/holidays', methods=['POST'])
@login_required
@csrf.exempt
def add_holiday():
    data = request.get_json()
    date = data.get('date')
    name = data.get('name', '')
    
    if not date:
        return jsonify({'success': False, 'message': 'Date is required'}), 400
    
    try:
        # Validate date format
        datetime.strptime(date, '%Y-%m-%d')
        
        with session_scope() as session:
            existing = session.query(Holiday).filter_by(date=date).first()
            if existing:
                return jsonify({'success': False, 'message': 'Holiday already exists for this date'}), 400
            
            holiday = Holiday(date=date, name=name)
            session.add(holiday)
            session.flush()
            
            holiday_data = {
                'id': holiday.id,
                'date': holiday.date,
                'name': holiday.name
            }
        
        return jsonify(holiday_data)
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400
    except Exception as e:
        logger.error(f"Error adding holiday: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500

@app.route('/api/holidays/<int:id>', methods=['DELETE'])
@login_required
@csrf.exempt
def delete_holiday(id):
    try:
        with session_scope() as session:
            holiday = session.get(Holiday, id)
            if holiday:
                session.delete(holiday)
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'message': 'Holiday not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting holiday: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500

# Playlist API endpoints
@app.route('/api/playlists', methods=['GET'])
@login_required
def get_playlists():
    try:
        with session_scope() as session:
            playlists = session.query(Playlist).order_by(Playlist.name.asc()).all()
            return jsonify([{
                'id': p.id,
                'name': p.name,
                'song_count': session.query(Song).filter_by(playlist_id=p.id).count(),
                'created_at': p.created_at.isoformat() if p.created_at else None
            } for p in playlists])
    except Exception as e:
        logger.error(f"Error getting playlists: {e}")
        return jsonify([])

@app.route('/api/playlists', methods=['POST'])
@login_required
@csrf.exempt
def create_playlist():
    data = request.get_json()
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'success': False, 'message': 'Name is required'}), 400
    
    try:
        with session_scope() as session:
            existing = session.query(Playlist).filter_by(name=name).first()
            if existing:
                return jsonify({'success': False, 'message': 'Playlist name already exists'}), 400
            
            playlist = Playlist(name=name)
            session.add(playlist)
            session.flush()
            
            playlist_data = {
                'id': playlist.id,
                'name': playlist.name,
                'song_count': 0,
                'created_at': playlist.created_at.isoformat() if playlist.created_at else None
            }
        
        return jsonify(playlist_data)
    except Exception as e:
        logger.error(f"Error creating playlist: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500

@app.route('/api/playlists/<int:id>', methods=['DELETE'])
@login_required
@csrf.exempt
def delete_playlist(id):
    try:
        with session_scope() as session:
            playlist = session.get(Playlist, id)
            if not playlist:
                return jsonify({'success': False, 'message': 'Playlist not found'}), 404
            
            # Unassign songs from this playlist
            session.query(Song).filter_by(playlist_id=id).update({'playlist_id': None})
            # Unassign schedules from this playlist
            session.query(Schedule).filter_by(playlist_id=id).update({'playlist_id': None})
            session.delete(playlist)
        
        # Reload schedules since playlist assignments may have changed
        schedule_music()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting playlist: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500

@app.route('/api/songs/<int:song_id>/playlist', methods=['POST'])
@login_required
@csrf.exempt
def assign_song_to_playlist(song_id):
    data = request.get_json()
    playlist_id = data.get('playlist_id')  # None to unassign
    
    try:
        with session_scope() as session:
            song = session.get(Song, song_id)
            if not song:
                return jsonify({'success': False, 'message': 'Song not found'}), 404
            
            if playlist_id is not None:
                playlist = session.get(Playlist, playlist_id)
                if not playlist:
                    return jsonify({'success': False, 'message': 'Playlist not found'}), 404
            
            song.playlist_id = playlist_id
        
        return jsonify({'success': True, 'playlist_id': playlist_id})
    except Exception as e:
        logger.error(f"Error assigning song to playlist: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500

@app.route('/add-music', methods=['POST'])
@login_required
@csrf.exempt
def add_music():
    """Queue a YouTube download. Progress and results arrive over Socket.IO."""
    global download_job
    data = request.get_json(silent=True) or request.form
    url = (data.get('url') or '').strip()
    if not youtube_downloader.is_allowed_url(url):
        return jsonify({'success': False, 'message': 'Chỉ hỗ trợ link YouTube'}), 400
    if download_job is not None:
        return jsonify({'success': False, 'message': 'Đang có bài đang tải, vui lòng chờ'}), 409
    if ytdlp_updating:
        return jsonify({'success': False, 'message': 'Đang cập nhật yt-dlp, thử lại sau ít phút'}), 409

    download_job = youtube_downloader.DownloadJob(url)
    try:
        publish_download_state('starting', 'Đang phân tích link...')
        socketio.start_background_task(run_download_job, download_job)
    except Exception as e:
        download_job = None
        logger.error(f"Could not start download job: {e}")
        return jsonify({'success': False, 'message': 'Không thể bắt đầu tải'}), 500
    return jsonify({'success': True, 'queued': True, 'message': 'Đã bắt đầu tải'}), 202

@app.route('/upload-music', methods=['POST'])
@csrf.exempt
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
    """Upgrade yt-dlp. Downloads run in a child process, so no restart is needed."""
    global ytdlp_updating
    if download_job is not None or ytdlp_updating:
        return jsonify({'success': False, 'message': 'Đang tải nhạc hoặc đang cập nhật, hãy thử lại sau'}), 409
    ytdlp_updating = True
    try:
        logger.info("Manual yt-dlp update requested")
        new_version = youtube_downloader.update_ytdlp()
        return jsonify({'success': True, 'message': 'yt-dlp updated successfully', 'version': new_version})
    except Exception as e:
        logger.error(f"Error manually updating yt-dlp: {e}")
        return jsonify({'success': False, 'message': 'Failed to update yt-dlp'}), 500
    finally:
        ytdlp_updating = False


@app.route('/play/<int:id>', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def play(id):
    success = play_music(id)
    return jsonify({'success': success})

@socketio.on('toggle_play_pause')
@socketio_login_required
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
@socketio_login_required
def handle_stop():
    global current_song_id, current_song_duration, is_playing, current_position
    try:
        # get_busy() returns False when paused, so also check is_playing / current_song_id
        music_active = pygame.mixer.music.get_busy() or is_playing or current_song_id is not None
        if music_active:
            # Use fade out if enabled and actually playing (not paused)
            if fade_enabled and pygame.mixer.music.get_busy():
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
@socketio_login_required
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
@socketio_login_required
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
@socketio_login_required
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

@app.route('/toggle-delete-after-play/<int:id>', methods=['POST'])
@login_required
@csrf.exempt
def toggle_delete_after_play(id):
    """Toggle delete_after_play option for a song"""
    try:
        with session_scope() as session:
            song = session.get(Song, id)
            if not song:
                return jsonify({'success': False, 'message': 'Song not found'}), 404
            
            song.delete_after_play = not song.delete_after_play
            logger.info(f"Toggled delete_after_play for song {id}: {song.delete_after_play}")
            
            return jsonify({
                'success': True,
                'song': {
                    'id': song.id,
                    'title': song.title,
                    'delete_after_play': song.delete_after_play
                }
            })
    except Exception as e:
        logger.error(f"Error toggling delete_after_play for song {id}: {e}")
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
@socketio_login_required
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
@socketio_login_required
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
                        'delete_after_play': song.delete_after_play or False,
                        'playlist_id': song.playlist_id,
                        'last_played_at': song.last_played_at.isoformat() if song.last_played_at else None,
                        'priority': song.priority,
                        'created_at': song.created_at.isoformat() if song.created_at else None,
                        'file_path': song.filename,
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
    
    # GET request - serve React frontend
    if request.method == 'GET':
        return send_from_directory('static/react', 'index.html')
        
    # POST request - handle login API
    error = None
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
@login_required
def serve_react(path=''):
    """Serve React frontend for production"""
    if path and os.path.exists(os.path.join(REACT_BUILD_DIR, path)):
        return send_file(os.path.join(REACT_BUILD_DIR, path))
    return send_file(os.path.join(REACT_BUILD_DIR, 'index.html'))

@app.route('/assets/<path:filename>')
def serve_react_assets(filename):
    """Serve React static assets (no login required for CSS/JS files)"""
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