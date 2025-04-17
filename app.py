from flask import Flask, render_template, jsonify, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import yt_dlp
import pygame
import os
import json
import subprocess
import sys
from werkzeug.utils import secure_filename
import mutagen
from mutagen.mp3 import MP3
import glob

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///music.db'
app.config['UPLOAD_FOLDER'] = 'music'
app.config['SECRET_KEY'] = 'your-secret-key'  # Required for Flask-SocketIO
socketio = SocketIO(app, async_mode='threading') # Explicitly set async mode
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
db = SQLAlchemy(app)

# Get absolute path for the project directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
MUSIC_DIR = os.path.join(BASE_DIR, "music")

# Initialize pygame mixer for audio playback
pygame.mixer.init()
pygame.mixer.music.set_volume(0.5)  # Default volume 50%

def broadcast_playback_state():
    """Broadcast current playback state to all clients"""
    global current_position, current_song, volume # Ensure globals are accessible
    try:
        # Always get current position if music is playing
        if pygame.mixer.music.get_busy() and current_song:
            pos = pygame.mixer.music.get_pos()
            if pos >= 0:
                current_position = pos / 1000

        # Always broadcast current state, whether playing or paused
        socketio.emit('playback_update', {
            'position': current_position,
            'duration': current_song.duration if current_song else 0,
            'is_playing': pygame.mixer.music.get_busy(),
            'volume': volume
        }, room=None)  # This broadcasts to all clients
    except Exception as e:
        print(f"[ERROR] broadcast_playback_state: {e}")

# Wrapper to run broadcast in SocketIO background task context
def safe_broadcast():
    socketio.start_background_task(broadcast_playback_state)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Schedule playback state broadcasts
# Initialize continuous playback state broadcasting (0.5s interval)
scheduler.add_job(safe_broadcast, 'interval', seconds=0.5, id='broadcast_playback')

# Ensure directories exist
os.makedirs(MUSIC_DIR, exist_ok=True)

# Current playback state
current_song = None
is_playing = False
volume = 0.5  # Default volume (0.0 to 1.0)
current_position = 0  # Track current position
# Removed global last_scheduled_song_id, will use DB field instead

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
    filename = db.Column(db.String(200), nullable=False)
    priority = db.Column(db.Integer, default=0)  # Higher number = higher priority
    source = db.Column(db.String(50))  # 'youtube' or 'upload'
    duration = db.Column(db.Integer, default=0)  # Duration in seconds
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_played_at = db.Column(db.DateTime, nullable=True) # New field to track last playback time

def find_actual_file(filename):
    """Find the actual file regardless of special character differences"""
    base_name = os.path.basename(filename)
    dir_name = os.path.dirname(filename)
    search_path = os.path.join(BASE_DIR, dir_name, '*')
    
    for file in glob.glob(search_path):
        if os.path.basename(file).replace('｜', '|') == base_name:
            return os.path.relpath(file, BASE_DIR)
    return filename

def get_audio_duration(filename):
    try:
        audio = MP3(filename)
        return int(audio.info.length)
    except:
        return 0

def update_ytdlp():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
        print("yt-dlp updated successfully")
    except Exception as e:
        print(f"Error updating yt-dlp: {e}")

# Schedule daily yt-dlp updates at 1 AM
scheduler.add_job(update_ytdlp, 'cron', hour=1)

def get_next_scheduled_song():
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    weekday = now.strftime("%A").lower()  # Get current weekday name
    
    # First try to find next schedule today
    schedules = Schedule.query.filter(
        Schedule.time > current_time,
        Schedule.enabled == True
    ).order_by(Schedule.time).all()
    
    # If no schedules found for today, get first schedule for next day
    if not schedules:
        schedules = Schedule.query.filter(
            Schedule.enabled == True
        ).order_by(Schedule.time).all()
    
    # Filter schedules by weekday
    valid_schedules = [s for s in schedules if getattr(s, weekday)]
    
    if valid_schedules:
        next_schedule = valid_schedules[0]

        # Use the same logic as play_next_song to determine the *actual* next song
        next_song_to_play = Song.query.order_by(
            Song.last_played_at.is_(None).desc(), # Never played first
            Song.priority.desc(),                # Then highest priority
            Song.last_played_at.asc()            # Then oldest played
        ).first()

        weekdays = [day for day, enabled in next_schedule.weekdays.items() if enabled]
        return {
            'time': next_schedule.time,
            'weekdays': weekdays,
            'song': next_song_to_play.title if next_song_to_play else None # Display the actual next song
        }
    return None

def schedule_music():
    with app.app_context():
        # Store the broadcast job ID before removing jobs
        broadcast_job = None
        for job in scheduler.get_jobs():
            if job.id == 'broadcast_playback':
                broadcast_job = job
                break
                
        scheduler.remove_all_jobs()
        
        # Restore broadcast job first
        if broadcast_job:
            scheduler.add_job(
                broadcast_playback_state,
                'interval',
                seconds=0.1,
                id='broadcast_playback'
            )
            
        # Add other scheduled jobs
        scheduler.add_job(update_ytdlp, 'cron', hour=1)
        
        schedules = Schedule.query.filter_by(enabled=True).all()
        for schedule in schedules:
            hour, minute = schedule.time.split(':')
            # Add a job for each enabled weekday
            days_of_week = []
            if schedule.monday: days_of_week.append('mon')
            if schedule.tuesday: days_of_week.append('tue')
            if schedule.wednesday: days_of_week.append('wed')
            if schedule.thursday: days_of_week.append('thu')
            if schedule.friday: days_of_week.append('fri')
            if schedule.saturday: days_of_week.append('sat')
            if schedule.sunday: days_of_week.append('sun')
            
            if days_of_week:  # Only schedule if at least one day is selected
                scheduler.add_job(
                    play_next_song,
                    'cron',
                    hour=hour,
                    minute=minute,
                    day_of_week=','.join(days_of_week)
                )

def play_next_song():
    """Selects and plays the next song based on priority and last played time."""
    with app.app_context():
        print("Scheduler trying to play next song based on played status, priority, and last played time.") # Debugging

        # Query songs:
        # 1. Never played first (last_played_at IS NULL DESC)
        # 2. Then by highest priority (priority DESC)
        # 3. Then by oldest last_played_at (last_played_at ASC)
        next_song = Song.query.order_by(
            Song.last_played_at.is_(None).desc(), # Puts NULLs (never played) first
            Song.priority.desc(),
            Song.last_played_at.asc()
        ).first()

        if next_song:
            print(f"Scheduler selected song: {next_song.title} (ID: {next_song.id}, Priority: {next_song.priority}, Last Played: {next_song.last_played_at})") # Debugging
            play_music(next_song.id) # play_music handles updating last_played_at
        else:
            print("Scheduler: No songs found in the playlist.") # Debugging

def play_music(song_id):
    global current_song, is_playing, current_position
    song = db.session.get(Song, song_id)
    if song:
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        try:
            # Find the actual file path
            actual_filename = find_actual_file(song.filename)
            file_path = os.path.join(BASE_DIR, actual_filename)
            
            if not os.path.exists(file_path):
                print(f"Error: File not found: {file_path}")
                return False
                
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            current_song = song
            is_playing = True
            current_position = 0
            # Immediately broadcast the new state
            broadcast_playback_state()

            # Update last played time in DB
            song.last_played_at = datetime.utcnow()
            db.session.commit()
            print(f"Updated last_played_at for song ID {song.id}") # Debugging

            return True
        except pygame.error as e:
            print(f"Error playing music: {e}")
            db.session.rollback() # Rollback if updating last_played_at failed
            return False
        except Exception as e: # Catch potential DB errors too
             print(f"Error updating last_played_at: {e}")
             db.session.rollback()
             return False # Indicate playback didn't fully succeed
    return False

def download_music(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(MUSIC_DIR, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'extract_flat': False,  # We need full video info
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # First get video info to get duration
        info = ydl.extract_info(url, download=False)
        duration = int(info.get('duration', 0))
        
        # Then download the audio
        info = ydl.extract_info(url, download=True)
        # Get the actual filename from the filesystem
        actual_file = glob.glob(os.path.join(MUSIC_DIR, f"{info['title'].replace('|', '｜')}*.mp3"))[0]
        actual_filename = os.path.relpath(actual_file, BASE_DIR)
        
        # Fallback to audio file duration if YouTube duration is not available
        if duration == 0:
            duration = get_audio_duration(actual_file)
        
        return {
            'title': info['title'],
            'filename': actual_filename,
            'duration': duration
        }

@app.route('/')
def index():
    # Query songs using the same logic as the scheduler for consistent display order
    songs = Song.query.order_by(
        Song.last_played_at.is_(None).desc(), # Never played first
        Song.priority.desc(),                # Then highest priority
        Song.last_played_at.asc()            # Then oldest played
    ).all()

    # --- DEBUGGING: Print the order of songs fetched from DB ---
    print("\n--- Playlist Order in Index Route ---")
    for i, s in enumerate(songs):
        print(f"{i+1}. Title: {s.title}, Priority: {s.priority}, Last Played: {s.last_played_at}")
    print("-------------------------------------\n")
    # --- END DEBUGGING ---

    # Update any mismatched filenames (keep this logic)
    needs_commit = False
    for song in songs:
        actual_filename = find_actual_file(song.filename)
        if actual_filename != song.filename:
            song.filename = actual_filename
            needs_commit = True
    if needs_commit:
        db.session.commit()

    schedules = Schedule.query.order_by(Schedule.time).all()
    next_song_info = get_next_scheduled_song() # Renamed variable for clarity
    return render_template('index.html',
                         songs=songs,
                         schedules=schedules,
                         next_song=next_song_info, # Pass the info dict
                         current_song=current_song,
                         is_playing=is_playing,
                         volume=volume)

@app.route('/set-volume/<value>')
def set_volume(value):
    global volume
    try:
        # Convert string value to int (0-100)
        percent_value = int(float(value))
        # Ensure value is between 0 and 100
        percent_value = max(0, min(100, percent_value))
        # Convert to 0-1 scale for pygame
        volume = percent_value / 100.0
        pygame.mixer.music.set_volume(volume)
        return jsonify({'success': True, 'volume': volume})
    except (ValueError, TypeError) as e:
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
        # Validate time format (optional but recommended)
        datetime.strptime(time, '%H:%M')

        # Create schedule
        schedule = Schedule(time=time)

        # Update weekdays based on form data
        weekdays_selected = request.form.getlist('weekdays')
        schedule.monday = 'monday' in weekdays_selected
        schedule.tuesday = 'tuesday' in weekdays_selected
        schedule.wednesday = 'wednesday' in weekdays_selected
        schedule.thursday = 'thursday' in weekdays_selected
        schedule.friday = 'friday' in weekdays_selected
        schedule.saturday = 'saturday' in weekdays_selected
        schedule.sunday = 'sunday' in weekdays_selected

        db.session.add(schedule)
        db.session.commit() # Commit to get the ID

        # Reschedule jobs
        schedule_music()

        # Prepare data for frontend update
        days_map = {
            'monday': 'Mon', 'tuesday': 'Tue', 'wednesday': 'Wed',
            'thursday': 'Thu', 'friday': 'Fri', 'saturday': 'Sat', 'sunday': 'Sun'
        }
        enabled_days = [days_map[day] for day in weekdays_selected if day in days_map]
        weekdays_display_str = ' • '.join(enabled_days)

        # Return success and the new schedule details
        return jsonify({
            'success': True,
            'schedule': {
                'id': schedule.id,
                'time': schedule.time,
                'weekdays_display': weekdays_display_str,
                'enabled': schedule.enabled # Assuming new schedules are enabled by default
            }
        })
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid time format. Use HH:MM.'}), 400
    except Exception as e:
        db.session.rollback() # Rollback in case of error during commit or scheduling
        print(f"Error adding schedule: {e}") # Log the error
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

@app.route('/toggle-schedule/<int:id>')
def toggle_schedule(id):
    schedule = db.session.get(Schedule, id)
    if schedule:
        schedule.enabled = not schedule.enabled
        db.session.commit()
        schedule_music()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/delete-schedule/<int:id>')
def delete_schedule(id):
    schedule = db.session.get(Schedule, id)
    if schedule:
        db.session.delete(schedule)
        db.session.commit()
        schedule_music()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/add-music', methods=['POST'])
def add_music():
    url = request.form.get('url')
    if url:
        try:
            music_info = download_music(url)
            if not music_info['duration']:
                return jsonify({'success': False, 'message': 'Could not determine video duration'})
                
            song = Song(
                title=music_info['title'],
                filename=music_info['filename'],
                source='youtube',
                duration=music_info['duration']
            )
            db.session.add(song)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Music added successfully'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    return jsonify({'success': False, 'message': 'No URL provided'})

@app.route('/upload-music', methods=['POST'])
def upload_music():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join('music', filename)
        full_filepath = os.path.join(BASE_DIR, filepath)
        file.save(full_filepath)
        duration = get_audio_duration(full_filepath)
        
        song = Song(
            title=os.path.splitext(filename)[0],
            filename=filepath,
            source='upload',
            duration=duration
        )
        db.session.add(song)
        db.session.commit()
        return jsonify({'success': True, 'message': 'File uploaded successfully'})

@app.route('/update-priority/<int:id>', methods=['POST'])
def update_priority(id):
    priority = request.form.get('priority', type=int)
    song = db.session.get(Song, id)
    if song:
        song.priority = priority
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/play/<int:id>')
def play(id):
    success = play_music(id)
    return jsonify({'success': success})

@socketio.on('toggle_play_pause')
def handle_toggle_play_pause():
    global is_playing, current_position
    if pygame.mixer.music.get_busy():
        # Currently playing, so pause it
        pos = pygame.mixer.music.get_pos()
        if pos >= 0:
            current_position = pos / 1000 # Update position before pausing
        pygame.mixer.music.pause()
        is_playing = False
        # Immediately broadcast the new state
        broadcast_playback_state()
    elif current_song:
        # Currently paused or stopped, so resume/play
        resumed = False
        # Check if music is loaded and paused (get_pos returns time since start, -1 if not playing)
        # Use get_busy() == 0 to check if not actively playing, and get_pos() > 0 to check if it was paused mid-song
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy() == 0 and pygame.mixer.music.get_pos() > 0:
             pygame.mixer.music.unpause()
             is_playing = True
             resumed = True
        else:
             # If not paused (likely stopped or never started), try playing the current song
             if current_song:
                 # play_music sets is_playing and calls broadcast_playback_state itself
                 play_music(current_song.id)
                 # Return here to avoid broadcasting again below if play_music was called
                 return

        # Immediately broadcast the new state ONLY if we just resumed from pause
        if resumed:
            broadcast_playback_state()

@socketio.on('stop_music')
def handle_stop():
    global current_song, is_playing, current_position
    try:
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            current_song = None
            is_playing = False
            current_position = 0
            # Immediately broadcast the stopped state
            broadcast_playback_state()
            # Also emit a specific stopped event for client cleanup if needed
            emit('music_stopped')
    except Exception as e:
        # Attempt to broadcast state even on error, might still be useful
        try:
            broadcast_playback_state()
        except Exception: # Ignore errors during broadcast in error handler
            pass
        emit('stop_error', {'error': str(e)})

def get_current_position():
    """Helper function to get current playback position"""
    global current_position
    if pygame.mixer.music.get_busy() and current_song:
        pos = pygame.mixer.music.get_pos()
        if pos >= 0:  # Make sure we have a valid position
            current_position = pos / 1000
    return current_position

@app.route('/seek/<float:position>')
def seek(position):
    global current_position
    if current_song and 0 <= position <= current_song.duration:
        pygame.mixer.music.play(start=position)
        current_position = position
        broadcast_playback_state() # Broadcast immediately after seek
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/delete-song/<int:id>')
def delete_song(id):
    song = db.session.get(Song, id)
    if song:
        actual_filename = find_actual_file(song.filename)
        filepath = os.path.join(BASE_DIR, actual_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        db.session.delete(song)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/stream/<int:id>')
def stream(id):
    song = db.session.get(Song, id)
    if song:
        actual_filename = find_actual_file(song.filename)
        return send_file(os.path.join(BASE_DIR, actual_filename))
    return jsonify({'success': False})

# WebSocket event handlers
@socketio.on('set_volume')
def handle_volume(data):
    global volume
    try:
        # Convert value to int (0-100)
        percent_value = int(float(data['value']))
        # Ensure value is between 0 and 100
        percent_value = max(0, min(100, percent_value))
        # Convert to 0-1 scale for pygame
        volume = percent_value / 100.0
        pygame.mixer.music.set_volume(volume)
        emit('volume_updated', {'volume': volume})
    except (ValueError, TypeError) as e:
        emit('error', {'message': 'Invalid volume value. Must be between 0 and 100.'})

# Add scheduler job to broadcast playback state every 100ms for smoother updates
# Scheduler jobs are initialized above near other scheduler setup code

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        schedule_music()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)