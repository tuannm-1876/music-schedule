from flask import Flask, render_template, jsonify, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import yt_dlp
import pygame
import os
import json
import subprocess
import sys
import logging
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
MAX_UPLOAD_SIZE = 16 * 1024 * 1024  # 16MB

app = Flask(__name__)
csrf = CSRFProtect(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///music.db'
app.config['UPLOAD_FOLDER'] = 'music'
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE
app.config['CORS_HEADERS'] = 'Content-Type'
socketio = SocketIO(app, async_mode='threading')
CORS(app)
db = SQLAlchemy(app)

# Get absolute path for the project directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
MUSIC_DIR = os.path.join(BASE_DIR, "music")

# Initialize pygame mixer for audio playback
pygame.mixer.init()
pygame.mixer.music.set_volume(DEFAULT_VOLUME)

# Initialize scheduler
scheduler = None
def init_scheduler():
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler()
        scheduler.start()
        scheduler.add_job(safe_broadcast, 'interval', seconds=BROADCAST_INTERVAL, id='broadcast_playback')
        scheduler.add_job(update_ytdlp, 'cron', hour=UPDATE_YTDLP_HOUR, id='update_ytdlp')

# Ensure directories exist
os.makedirs(MUSIC_DIR, exist_ok=True)

# Global variables for playback state
current_song_id = None
current_song_duration = 0
is_playing = False
volume = DEFAULT_VOLUME
current_position = 0

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
        if pygame.mixer.music.get_busy() and current_song_id:
            pos = pygame.mixer.music.get_pos()
            if pos >= 0:
                global current_position
                current_position = pos / 1000

        socketio.emit('playback_update', {
            'position': current_position,
            'duration': current_song_duration,
            'is_playing': pygame.mixer.music.get_busy(),
            'volume': volume
        })
    except Exception as e:
        logger.error(f"Error in broadcast_playback_state: {e}")

def safe_broadcast():
    socketio.start_background_task(broadcast_playback_state)


# Models
class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(5), nullable=False)  # Format: "HH:MM"
    enabled = db.Column(db.Boolean, default=True)
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
    source = db.Column(db.String(50))
    duration = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_played_at = db.Column(db.DateTime, nullable=True)

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
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
        logger.info("yt-dlp updated successfully")
    except Exception as e:
        logger.error(f"Error updating yt-dlp: {e}")

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
                            
                            if schedule_time > now:
                                scheduler.add_job(
                                    play_next_song,
                                    'cron',
                                    hour=hour,
                                    minute=minute,
                                    day_of_week=','.join(days_of_week),
                                    id=job_id,
                                    replace_existing=True,
                                    next_run_time=schedule_time
                                )
                            else:
                                scheduler.add_job(
                                    play_next_song,
                                    'cron',
                                    hour=hour,
                                    minute=minute,
                                    day_of_week=','.join(days_of_week),
                                    id=job_id,
                                    replace_existing=True
                                )
                    except ValueError as e:
                        logger.error(f"Error processing schedule {schedule.id}: {e}")
                        continue
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

def play_next_song():
    with app.app_context():
        logger.info("Scheduler triggered play next song")
        try:
            with session_scope() as session:
                next_song = session.query(Song).order_by(
                    Song.last_played_at.is_(None).desc(),
                    Song.priority.desc(),
                    Song.last_played_at.asc()
                ).first()

                if next_song:
                    logger.info(f"Selected song to play: {next_song.title}")
                    # Trigger playlist update through socket
                    socketio.emit('schedule_triggered', {
                        'song_id': next_song.id,
                        'title': next_song.title,
                        'time': datetime.now().strftime("%H:%M")
                    })
                else:
                    logger.warning("No songs found in playlist")
                    return
            with session_scope() as session:
                next_song = session.query(Song).order_by(
                    Song.last_played_at.is_(None).desc(),
                    Song.priority.desc(),
                    Song.last_played_at.asc()
                ).first()

                if next_song:
                    logger.info(f"Playing song: {next_song.title}")
                    play_music(next_song.id)
                else:
                    logger.warning("No songs found in the playlist")
        except Exception as e:
            logger.error(f"Error playing next song: {e}")

def play_music(song_id):
    global current_song_id, current_song_duration, is_playing, current_position
    
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
                pygame.mixer.music.stop()

            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            
            current_song_id = song_id
            current_song_duration = song.duration
            is_playing = True
            current_position = 0
            
            song.last_played_at = datetime.utcnow()
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
    import re
    # Remove any character that is not alphanumeric, space, or underscore
    title = re.sub(r'[^\w\s]', '', title)
    # Replace spaces with underscores
    title = title.replace(' ', '_')
    # Ensure only one underscore between words
    title = re.sub(r'_+', '_', title)
    return title

def download_music(url):
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
        logger.error(f"Error downloading music from {url}: {e}")
        raise

@app.route('/')
def index():
    try:
        with session_scope() as session:
            songs = session.query(Song).order_by(
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
                               volume=volume)
    except Exception as e:
        logger.error(f"Error rendering index page: {e}")
        return "Internal Server Error", 500

@app.route('/set-volume/<value>')
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
def add_schedule():
    time = request.form.get('time')
    if not time:
        return jsonify({'success': False, 'message': 'Time is required'}), 400

    try:
        datetime.strptime(time, '%H:%M')
        weekdays_selected = request.form.getlist('weekdays')

        with session_scope() as session:
            schedule = Schedule(time=time)
            schedule.monday = 'monday' in weekdays_selected
            schedule.tuesday = 'tuesday' in weekdays_selected
            schedule.wednesday = 'wednesday' in weekdays_selected
            schedule.thursday = 'thursday' in weekdays_selected
            schedule.friday = 'friday' in weekdays_selected
            schedule.saturday = 'saturday' in weekdays_selected
            schedule.sunday = 'sunday' in weekdays_selected
            
            session.add(schedule)
            session.flush()

            schedule_music()

            days_map = {
                'monday': 'Mon', 'tuesday': 'Tue', 'wednesday': 'Wed',
                'thursday': 'Thu', 'friday': 'Fri', 'saturday': 'Sat', 'sunday': 'Sun'
            }
            enabled_days = [days_map[day] for day in weekdays_selected if day in days_map]
            weekdays_display_str = ' • '.join(enabled_days)

            return jsonify({
                'success': True,
                'schedule': {
                    'id': schedule.id,
                    'time': schedule.time,
                    'weekdays_display': weekdays_display_str,
                    'enabled': schedule.enabled
                }
            })

    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid time format. Use HH:MM.'}), 400
    except Exception as e:
        logger.error(f"Error adding schedule: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

@app.route('/toggle-schedule/<int:id>')
def toggle_schedule(id):
    try:
        with session_scope() as session:
            schedule = session.get(Schedule, id)
            if schedule:
                schedule.enabled = not schedule.enabled
                schedule_music()
                return jsonify({'success': True})
            return jsonify({'success': False, 'message': 'Schedule not found'}), 404
    except Exception as e:
        logger.error(f"Error toggling schedule {id}: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500

@app.route('/delete-schedule/<int:id>')
def delete_schedule(id):
    try:
        with session_scope() as session:
            schedule = session.get(Schedule, id)
            if schedule:
                session.delete(schedule)
                schedule_music()
                return jsonify({'success': True})
            return jsonify({'success': False, 'message': 'Schedule not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting schedule {id}: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500

@app.route('/add-music', methods=['POST'])
def add_music():
    url = request.form.get('url')
    if not url:
        return jsonify({'success': False, 'message': 'No URL provided'}), 400

    try:
        music_info = download_music(url)
        if not music_info['duration']:
            return jsonify({'success': False, 'message': 'Could not determine video duration'})
            
        with session_scope() as session:
            # Check if song with same filename already exists
            existing_song = session.query(Song).filter_by(filename=music_info['filename']).first()
            if existing_song:
                return jsonify({'success': False, 'message': 'This song already exists in the playlist'}), 400

            song = Song(
                title=music_info['title'],
                filename=music_info['filename'],
                source='youtube',
                duration=music_info['duration']
            )
            session.add(song)
            return jsonify({'success': True, 'message': 'Music added successfully'})
    except Exception as e:
        logger.error(f"Error adding music from URL {url}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/upload-music', methods=['POST'])
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
        full_filepath = os.path.join(BASE_DIR, filepath)

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

            song = Song(
                title=os.path.splitext(filename)[0],
                filename=filepath,
                source='upload',
                duration=duration
            )
            session.add(song)
            return jsonify({'success': True, 'message': 'File uploaded successfully'})
    except Exception as e:
        logger.error(f"Error uploading file {file.filename}: {e}")
        if os.path.exists(full_filepath):
            os.remove(full_filepath)
        return jsonify({'success': False, 'message': 'Error uploading file'}), 500

@app.route('/update-priority/<int:id>', methods=['POST'])
def update_priority(id):
    try:
        priority = request.form.get('priority', type=int)
        if priority is None:
            return jsonify({'success': False, 'message': 'Priority is required'}), 400

        with session_scope() as session:
            song = session.get(Song, id)
            if song:
                song.priority = priority
                return jsonify({'success': True})
            return jsonify({'success': False, 'message': 'Song not found'}), 404
    except Exception as e:
        logger.error(f"Error updating priority for song {id}: {e}")
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500

@app.route('/play/<int:id>')
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

@app.route('/seek/<float:position>')
def seek(position):
    """Seek to a specific position in the current song."""
    global current_position
    try:
        if not current_song:
            return jsonify({'success': False, 'message': 'No song is currently loaded'}), 400

        if not (0 <= position <= current_song.duration):
            return jsonify({'success': False, 'message': 'Invalid position'}), 400

        # Stop current playback
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

        # Reload and play from position
        actual_filename = find_actual_file(current_song.filename)
        file_path = os.path.join(BASE_DIR, actual_filename)
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': 'Song file not found'}), 404

        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play(start=position)
        current_position = position
        broadcast_playback_state()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error seeking to position {position}: {e}")
        return jsonify({'success': False, 'message': 'Error during seek'}), 500

@app.route('/delete-song/<int:id>')
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
        percent_value = int(float(data['value']))
        percent_value = max(0, min(100, percent_value))
        volume = percent_value / 100.0
        pygame.mixer.music.set_volume(volume)
        emit('volume_updated', {'volume': volume})
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid volume value: {data.get('value')}")
        emit('error', {'message': 'Invalid volume value. Must be between 0 and 100.'})
    except Exception as e:
        logger.error(f"Error setting volume: {e}")
        emit('error', {'message': 'Error setting volume'})

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
    schedule_music()
    list_scheduler_jobs()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)