let currentSongId = null;
let socket = null;
let isPlaying = false; // Track actual playback state

function updatePlayPauseButton(playing) {
    const btn = document.getElementById('play-pause-btn');
    if (btn) {
        btn.innerHTML = playing ?
            '<i class="fas fa-pause"></i>' :
            '<i class="fas fa-play"></i>';
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // Initialize Socket.IO connection
    socket = io();

    // Listen for playback updates
    socket.on('playback_update', function (data) {
        if (currentSongId) {
            updateProgress(data.position, data.duration, data.volume);
            if (isPlaying !== data.is_playing) {
                isPlaying = data.is_playing;
                updatePlayPauseButton(isPlaying);
            }
        }
    });

    // Listen for volume updates
    socket.on('volume_updated', function (data) {
        const volumeSlider = document.getElementById('volume-slider');
        if (volumeSlider) {
            const currentVolume = Math.min(100, Math.max(0, Math.round(data.volume * 100)));
            if (volumeSlider.value != currentVolume) {
                volumeSlider.value = currentVolume;
            }
        }
    });

    // Listen for error messages
    socket.on('error', function (data) {
        console.error('Socket error:', data.message);
    });

    // Volume control handling
    const volumeSlider = document.getElementById('volume-slider');
    if (volumeSlider) {
        volumeSlider.addEventListener('input', function () {
            // Use raw slider value (0-100)
            const volume = Math.min(100, Math.max(0, Math.round(parseFloat(this.value))));
            socket.emit('set_volume', { value: volume });
        });
    }

    // YouTube form handling
    document.getElementById('addMusicForm').addEventListener('submit', function (e) {
        e.preventDefault();

        const url = document.getElementById('youtubeUrl').value;
        const formData = new FormData();
        formData.append('url', url);

        const submitButton = this.querySelector('button');
        submitButton.disabled = true;
        submitButton.textContent = 'Adding...';

        fetch('/add-music', {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Error: ' + data.message);
                }
            })
            .catch(error => {
                alert('Error adding music: ' + error);
            })
            .finally(() => {
                submitButton.disabled = false;
                submitButton.textContent = 'Add from YouTube';
                document.getElementById('youtubeUrl').value = '';
            });
    });

    // File upload handling
    document.getElementById('uploadForm').addEventListener('submit', function (e) {
        e.preventDefault();

        const fileInput = document.getElementById('musicFile');
        const file = fileInput.files[0];
        if (!file) {
            alert('Please select a file');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        const submitButton = this.querySelector('button');
        submitButton.disabled = true;
        submitButton.textContent = 'Uploading...';

        fetch('/upload-music', {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Error: ' + data.message);
                }
            })
            .catch(error => {
                alert('Error uploading file: ' + error);
            })
            .finally(() => {
                submitButton.disabled = false;
                submitButton.textContent = 'Upload Music';
                fileInput.value = '';
            });
    });

    // Priority input handling
    document.querySelectorAll('.priority-input').forEach(input => {
        input.addEventListener('change', function () {
            const songId = this.closest('.song-item').dataset.id;
            const formData = new FormData();
            formData.append('priority', this.value);

            fetch(`/update-priority/${songId}`, {
                method: 'POST',
                body: formData
            })
                .then(response => response.json())
                .then(data => {
                    if (!data.success) {
                        alert('Error updating priority');
                        location.reload();
                    }
                })
                .catch(error => {
                    alert('Error updating priority: ' + error);
                    location.reload();
                });
        });
    });

    // Progress bar click handling
    document.querySelector('.progress-bar')?.addEventListener('click', function (e) {
        const rect = this.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const width = rect.width;
        const percentage = x / width;

        if (currentSongId) {
            const song = document.querySelector(`.song-item[data-id="${currentSongId}"]`);
            const duration = parseInt(song.dataset.duration);
            seekTo(duration * percentage);
        }
    });

    // Start position polling if there's a current song
    const playerControls = document.querySelector('.player-controls');
    if (!playerControls.classList.contains('hidden')) {
        startProgressPolling();
    }

    // Add Schedule form handling
    const addScheduleForm = document.getElementById('add-schedule-form');
    if (addScheduleForm) {
        addScheduleForm.addEventListener('submit', handleAddSchedule);
    }
});

// Function to handle adding a schedule via fetch
function handleAddSchedule(e) {
    e.preventDefault(); // Prevent default form submission

    const form = e.target;
    const formData = new FormData(form);
    const submitButton = form.querySelector('button[type="submit"]');
    const errorDiv = document.getElementById('schedule-error');

    // Disable button and clear errors
    submitButton.disabled = true;
    submitButton.textContent = 'Adding...';
    errorDiv.textContent = '';

    fetch(form.action, {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.schedule) {
                addScheduleItemToDOM(data.schedule); // Add new item to the list
                form.reset(); // Clear the form fields
                // Uncheck all weekday boxes (optional, could keep defaults)
                form.querySelectorAll('input[name="weekdays"]').forEach(cb => cb.checked = true);
            } else {
                errorDiv.textContent = data.message || 'An unknown error occurred.';
            }
        })
        .catch(error => {
            console.error('Error adding schedule:', error);
            errorDiv.textContent = 'Network error or server issue.';
        })
        .finally(() => {
            // Re-enable button
            submitButton.disabled = false;
            submitButton.textContent = 'Add Schedule Time';
        });
}

// Function to dynamically add a schedule item to the DOM
function addScheduleItemToDOM(schedule) {
    const listContainer = document.getElementById('schedule-list-container');
    if (!listContainer) return;

    const newItem = document.createElement('div');
    newItem.classList.add('schedule-item');
    // Add 'disabled' class if needed, assuming new schedules are enabled by default
    // newItem.classList.toggle('disabled', !schedule.enabled);

    newItem.innerHTML = `
        <div class="schedule-info">
            <span class="time">${schedule.time}</span>
            <small class="weekdays">${schedule.weekdays_display}</small>
        </div>
        <div class="schedule-controls">
            <a href="#" onclick="toggleSchedule(${schedule.id})" class="toggle-btn">Disable</a>
            <a href="#" onclick="deleteSchedule(${schedule.id})" class="delete-btn">Delete</a>
        </div>
    `;

    listContainer.appendChild(newItem);
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

    // Ensure position is valid
    position = Math.max(0, position);
    duration = duration || currentSongDuration;

    // Update progress bar and current time
    const progress = Math.min(100, (position / duration) * 100);
    progressBar.style.width = `${progress}%`;
    currentTimeDisplay.textContent = formatTime(Math.floor(position));

    // Update volume slider if value is different
    if (volumeSlider && typeof volume === 'number') {
        const currentVolume = Math.min(100, Math.max(0, Math.round(volume * 100)));
        if (volumeSlider.value != currentVolume) {
            volumeSlider.value = currentVolume;
        }
    }
}

function startProgressPolling() {
    // Show controls if we have a current song
    if (currentSongId) {
        document.querySelector('.player-controls').classList.remove('hidden');
    }
}

function toggleSchedule(id) {
    fetch(`/toggle-schedule/${id}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Error toggling schedule');
            }
        })
        .catch(error => {
            alert('Error: ' + error);
        });
}

function deleteSchedule(id) {
    if (confirm('Are you sure you want to delete this schedule?')) {
        fetch(`/delete-schedule/${id}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Error deleting schedule');
                }
            })
            .catch(error => {
                alert('Error: ' + error);
            });
    }
}

let currentSongDuration = 0;

function playMusic(id, title) {
    // Get the song element to access its duration
    const songElement = document.querySelector(`.song-item[data-id="${id}"]`);
    if (songElement) {
        // Get duration from the element
        currentSongDuration = parseInt(songElement.dataset.duration);
        // Get formatted duration text
        const durationText = songElement.querySelector('.song-duration').textContent;
        // Update the duration display immediately
        document.getElementById('duration').textContent = durationText;
    }

    fetch(`/play/${id}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentSongId = id;
                isPlaying = true; // Set initial playback state
                document.getElementById('current-song-title').textContent = title;
                document.querySelector('.player-controls').classList.remove('hidden');
                startProgressPolling();
            } else {
                alert('Error playing music');
            }
        })
        .catch(error => {
            alert('Error: ' + error);
        });
}

function togglePlayPause() {
    if (!currentSongId) return;
    // Send a single toggle event to the server
    socket.emit('toggle_play_pause');
}

function seekTo(position) {
    fetch(`/seek/${position}`)
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                alert('Error seeking position');
            }
        })
        .catch(error => {
            alert('Error: ' + error);
        });
}

function stopMusic() {
    socket.emit('stop_music');
}

// Listen for stop music response
socket.on('music_stopped', function () {
    // Clear song state
    currentSongId = null;
    currentSongDuration = 0;
    isPlaying = false;

    // Reset displays
    const durationDisplay = document.getElementById('duration');
    const currentTimeDisplay = document.getElementById('current-time');
    const progressBar = document.getElementById('song-progress');
    const songTitleDisplay = document.getElementById('current-song-title');

    durationDisplay.textContent = '0:00';
    currentTimeDisplay.textContent = '0:00';
    progressBar.style.width = '0%';
    songTitleDisplay.textContent = '';
    // Hide controls
    document.querySelector('.player-controls').classList.add('hidden');
});

socket.on('stop_error', function (data) {
    console.error('Error:', data.error);
    alert('Error stopping music. Please try again.');
});

function deleteSong(id) {
    if (confirm('Are you sure you want to delete this song?')) {
        fetch(`/delete-song/${id}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Error deleting song');
                }
            })
            .catch(error => {
                alert('Error: ' + error);
            });
    }
}

// Automatic page refresh every minute to update next scheduled song
setInterval(() => {
    if (!document.querySelector('.player-controls') ||
        document.querySelector('.player-controls').classList.contains('hidden')) {
        location.reload();
    }
}, 60000);