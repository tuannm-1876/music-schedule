let currentSongId = null;
let socket = null;
let isPlaying = false;

// CSRF token handling
function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}

// Add CSRF token to all fetch requests
function fetchWithCsrf(url, options = {}) {
    const defaultOptions = {
        headers: {
            'X-CSRF-Token': getCsrfToken(),
            'Accept': 'application/json'
        }
    };
    return fetch(url, { ...defaultOptions, ...options });
}

// Error handling utility
function showError(element, message) {
    const errorElement = element.querySelector('.error-message') || element;
    errorElement.textContent = message;
    errorElement.classList.add('visible');
    setTimeout(() => {
        errorElement.classList.remove('visible');
    }, 5000);
}

// Loading state utility
function setLoading(button, isLoading) {
    button.disabled = isLoading;
    const originalText = button.dataset.originalText || button.textContent;
    if (isLoading) {
        button.dataset.originalText = originalText;
        button.textContent = 'Loading...';
    } else {
        button.textContent = originalText;
        delete button.dataset.originalText;
    }
}

function updatePlayPauseButton(playing) {
    const btn = document.getElementById('play-pause-btn');
    if (btn) {
        const icon = btn.querySelector('i');
        icon.className = playing ? 'fas fa-pause' : 'fas fa-play';
    }
}

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    seconds = Math.floor(seconds % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function updateProgress(position, duration, volume) {
    if (!currentSongId) return;

    const progressBar = document.getElementById('song-progress');
    const currentTimeDisplay = document.getElementById('current-time');
    const volumeSlider = document.getElementById('volume-slider');

    position = Math.max(0, position);
    duration = duration || currentSongDuration;

    const progress = Math.min(100, (position / duration) * 100);
    progressBar.style.width = `${progress}%`;
    currentTimeDisplay.textContent = formatTime(Math.floor(position));

    if (volumeSlider && typeof volume === 'number') {
        const currentVolume = Math.min(100, Math.max(0, Math.round(volume * 100)));
        if (volumeSlider.value != currentVolume) {
            volumeSlider.value = currentVolume;
        }
    }
}

function startProgressPolling() {
    if (currentSongId) {
        const progressBar = document.querySelector('.player-controls');
        const progress = document.getElementById('song-progress');
        const currentPosition = parseFloat(progress.dataset.currentPosition || 0);
        
        progressBar.classList.remove('hidden');
        
        // Update initial progress
        if (currentPosition > 0) {
            const duration = parseFloat(document.querySelector('.song-item[data-id="' + currentSongId + '"]').dataset.duration);
            updateProgress(currentPosition, duration);
        }
    }
}

// Schedule handling
async function handleSchedule(element, action) {
    const scheduleId = element.closest('.schedule-item').dataset.id;
    const isDelete = action === 'delete';
    
    if (isDelete && !confirm('Are you sure you want to delete this schedule?')) {
        return;
    }

    try {
        const url = isDelete ? `/delete-schedule/${scheduleId}` : `/toggle-schedule/${scheduleId}`;
        const response = await fetchWithCsrf(url);
        const data = await response.json();

        if (data.success) {
            window.location.reload();
        } else {
            showError(element.closest('.schedule-item'), data.message || 'Operation failed');
        }
    } catch (error) {
        console.error(`Schedule ${action} error:`, error);
        showError(element.closest('.schedule-item'), 'Network error occurred');
    }
}

// Song handling
async function handleSong(element, action) {
    const songItem = element.closest('.song-item');
    const songId = songItem.dataset.id;
    
    if (action === 'delete') {
        if (!confirm('Are you sure you want to delete this song?')) {
            return;
        }
        try {
            const response = await fetchWithCsrf(`/delete-song/${songId}`);
            const data = await response.json();
            if (data.success) {
                songItem.remove();
            } else {
                showError(songItem, data.message || 'Failed to delete song');
            }
        } catch (error) {
            console.error('Delete song error:', error);
            showError(songItem, 'Network error occurred');
        }
    } else if (action === 'play') {
        playMusic(songId, songItem.dataset.title);
    }
}

let currentSongDuration = 0;

// Initialize from DOM if song is playing
const songTitle = document.getElementById('current-song-title');
if (songTitle && songTitle.textContent) {
    const songElement = Array.from(document.querySelectorAll('.song-item'))
        .find(el => el.querySelector('.song-title').textContent === songTitle.textContent);
    if (songElement) {
        currentSongId = songElement.dataset.id;
        currentSongDuration = parseFloat(songElement.dataset.duration);
    }
}

async function playMusic(id, title) {
    const songElement = document.querySelector(`.song-item[data-id="${id}"]`);
    if (!songElement) return;

    currentSongDuration = parseInt(songElement.dataset.duration);
    document.getElementById('duration').textContent = songElement.querySelector('.song-duration').textContent;

    try {
        const response = await fetchWithCsrf(`/play/${id}`);
        const data = await response.json();

        if (data.success) {
            currentSongId = id;
            isPlaying = true;
            document.getElementById('current-song-title').textContent = title;
            document.querySelector('.player-controls').classList.remove('hidden');
            startProgressPolling();
        } else {
            showError(songElement, data.message || 'Failed to play song');
        }
    } catch (error) {
        console.error('Play music error:', error);
        showError(songElement, 'Network error occurred');
    }
}

// Form handling
function handleForm(formId, url, successCallback) {
    const form = document.getElementById(formId);
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitButton = form.querySelector('button[type="submit"]');
        setLoading(submitButton, true);

        try {
            const formData = new FormData(form);
            const response = await fetchWithCsrf(url, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                successCallback(data);
                form.reset();
            } else {
                showError(form, data.message || 'Operation failed');
            }
        } catch (error) {
            console.error(`${formId} error:`, error);
            showError(form, 'Network error occurred');
        } finally {
            setLoading(submitButton, false);
        }
    });
}

document.addEventListener('DOMContentLoaded', function () {
    socket = io();
    const progress = document.getElementById('song-progress');
    const songTitle = document.getElementById('current-song-title');
    if (progress && songTitle.textContent) {
        const songElement = Array.from(document.querySelectorAll('.song-item'))
            .find(el => el.querySelector('.song-title').textContent === songTitle.textContent);
        if (songElement) {
            currentSongId = songElement.dataset.id;
            currentSongDuration = parseFloat(songElement.dataset.duration);
        }
    }

    // Socket event listeners
    socket.on('schedule_triggered', function(data) {
        window.location.reload();
    });

    socket.on('playback_update', function (data) {
        if (currentSongId) {
            updateProgress(data.position, data.duration, data.volume);
            if (isPlaying !== data.is_playing) {
                isPlaying = data.is_playing;
                updatePlayPauseButton(isPlaying);
            }
        }
    });

    socket.on('volume_updated', function (data) {
        const volumeSlider = document.getElementById('volume-slider');
        if (volumeSlider) {
            const currentVolume = Math.min(100, Math.max(0, Math.round(data.volume * 100)));
            if (volumeSlider.value != currentVolume) {
                volumeSlider.value = currentVolume;
            }
        }
    });

    socket.on('error', function (data) {
        console.error('Socket error:', data.message);
    });

    socket.on('music_stopped', function () {
        currentSongId = null;
        currentSongDuration = 0;
        isPlaying = false;

        const elements = {
            duration: document.getElementById('duration'),
            currentTime: document.getElementById('current-time'),
            progress: document.getElementById('song-progress'),
            songTitle: document.getElementById('current-song-title')
        };

        elements.duration.textContent = '0:00';
        elements.currentTime.textContent = '0:00';
        elements.progress.style.width = '0%';
        elements.songTitle.textContent = '';
        document.querySelector('.player-controls').classList.add('hidden');
    });

    socket.on('stop_error', function (data) {
        console.error('Stop error:', data.error);
        alert('Error stopping music. Please try again.');
    });

    // Event Listeners
    document.addEventListener('click', function(e) {
        const target = e.target.closest('button');
        if (!target) return;

        const action = target.dataset.action;
        if (!action) return;

        const isScheduleAction = target.closest('.schedule-item') !== null;
        const isSongAction = target.closest('.song-item') !== null;

        if (isScheduleAction && ['toggle', 'delete'].includes(action)) {
            handleSchedule(target, action);
        } else if (isSongAction && ['play', 'delete'].includes(action)) {
            handleSong(target, action);
        }
    });

    const playerControls = document.querySelector('.player-controls');
    if (playerControls) {
        document.getElementById('play-pause-btn').addEventListener('click', () => {
            if (currentSongId) {
                socket.emit('toggle_play_pause');
            }
        });

        document.getElementById('stop-btn').addEventListener('click', () => {
            socket.emit('stop_music');
        });

        const progressBar = document.querySelector('.progress-bar');
        if (progressBar) {
            progressBar.addEventListener('click', function(e) {
                if (!currentSongId) return;
                
                const rect = this.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const percentage = x / rect.width;
                const position = currentSongDuration * percentage;
                
                fetchWithCsrf(`/seek/${position}`);
            });
        }
    }

    const volumeSlider = document.getElementById('volume-slider');
    if (volumeSlider) {
        volumeSlider.addEventListener('input', function() {
            const volume = Math.min(100, Math.max(0, Math.round(parseFloat(this.value))));
            socket.emit('set_volume', { value: volume });
        });
    }

    handleForm('addMusicForm', '/add-music', () => window.location.reload());
    handleForm('uploadForm', '/upload-music', () => window.location.reload());
    handleForm('add-schedule-form', '/add-schedule', (data) => {
        if (data.schedule) {
            const listContainer = document.getElementById('schedule-list-container');
            if (listContainer) {
                const newItem = document.createElement('div');
                newItem.className = 'schedule-item';
                newItem.dataset.id = data.schedule.id;
                newItem.innerHTML = `
                    <div class="schedule-info">
                        <span class="time">${data.schedule.time}</span>
                        <small class="weekdays">${data.schedule.weekdays_display}</small>
                    </div>
                    <div class="schedule-controls">
                        <button class="toggle-btn" data-action="toggle">Disable</button>
                        <button class="delete-btn" data-action="delete">Delete</button>
                    </div>
                `;
                listContainer.appendChild(newItem);
            }
        }
    });

    // Priority input handling
    document.querySelectorAll('.priority-input').forEach(input => {
        let timeout;
        input.addEventListener('change', function() {
            const songId = this.closest('.song-item').dataset.id;
            clearTimeout(timeout);
            
            timeout = setTimeout(async () => {
                try {
                    const formData = new FormData();
                    formData.append('priority', this.value);
                    
                    const response = await fetchWithCsrf(`/update-priority/${songId}`, {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    
                    if (!data.success) {
                        showError(this.closest('.song-item'), data.message || 'Failed to update priority');
                    }
                } catch (error) {
                    console.error('Priority update error:', error);
                    showError(this.closest('.song-item'), 'Network error occurred');
                }
            }, 500);
        });
    });

    if (!playerControls?.classList.contains('hidden')) {
        startProgressPolling();
    }
    setInterval(() => {
        if (!playerControls || playerControls.classList.contains('hidden')) {
            window.location.reload();
        }
    }, 60000);
});