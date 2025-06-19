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
    
    // Properly merge headers
    const mergedOptions = { ...defaultOptions, ...options };
    if (options.headers) {
        mergedOptions.headers = { ...defaultOptions.headers, ...options.headers };
    }
    
    return fetch(url, mergedOptions);
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

// Special handler for add music form with playlist support
function handleAddMusicForm() {
    const form = document.getElementById('addMusicForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitButton = form.querySelector('button[type="submit"]');
        const messageDiv = form.querySelector('.form-message') || createMessageDiv(form);
        
        setLoading(submitButton, true);
        messageDiv.textContent = '';
        messageDiv.className = 'form-message';

        // Setup progress tracking for playlists
        const url = form.querySelector('input[name="url"]').value;
        const isPlaylistUrl = url.includes('playlist') || url.includes('list=');
        
        if (isPlaylistUrl) {
            // Show global progress bar
            showGlobalProgress();
        }

        try {
            const formData = new FormData(form);
            const response = await fetchWithCsrf('/add-music', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                // Hide global progress bar
                hideGlobalProgress();
                
                // Check if this is a playlist response
                if (data.playlist_info) {
                    const info = data.playlist_info;
                    messageDiv.innerHTML = `
                        <div class="playlist-success">
                            <h4>✅ Playlist "${info.playlist_title}" đã được xử lý</h4>
                            <ul>
                                <li>📊 Tổng số bài hát: ${info.total_tracks}</li>
                                <li>✅ Đã thêm: ${info.added_tracks} bài hát</li>
                                ${info.skipped_tracks > 0 ? `<li>⏭️ Đã bỏ qua: ${info.skipped_tracks} bài hát (đã tồn tại)</li>` : ''}
                                ${info.failed_tracks > 0 ? `<li>❌ Thất bại: ${info.failed_tracks} bài hát</li>` : ''}
                            </ul>
                        </div>
                    `;
                    messageDiv.className = 'form-message success';
                } else {
                    messageDiv.textContent = data.message;
                    messageDiv.className = 'form-message success';
                }
                
                form.reset();
                
                // Reload page after showing results
                setTimeout(() => {
                    window.location.reload();
                }, 3000);
                
            } else {
                hideGlobalProgress();
                messageDiv.textContent = data.message || 'Operation failed';
                messageDiv.className = 'form-message error';
            }
        } catch (error) {
            console.error('Add music error:', error);
            hideGlobalProgress();
            messageDiv.textContent = 'Network error occurred';
            messageDiv.className = 'form-message error';
        } finally {
            setLoading(submitButton, false);
        }
    });
}

// Show global progress bar
function showGlobalProgress() {
    const progressContainer = document.getElementById('global-progress');
    if (progressContainer) {
        progressContainer.style.display = 'block';
        
        // Reset progress
        const progressFill = document.getElementById('global-progress-fill');
        const progressPercentage = document.getElementById('global-progress-percentage');
        const progressCurrentSong = document.getElementById('progress-current-song');
        const progressCount = document.getElementById('progress-count');
        
        if (progressFill) progressFill.style.width = '0%';
        if (progressPercentage) progressPercentage.textContent = '0%';
        if (progressCurrentSong) progressCurrentSong.textContent = 'Đang chuẩn bị...';
        if (progressCount) progressCount.textContent = '0/0';
    }
}

// Hide global progress bar
function hideGlobalProgress() {
    const progressContainer = document.getElementById('global-progress');
    if (progressContainer) {
        progressContainer.style.display = 'none';
    }
}

// Update global progress bar
function updateGlobalProgress(data) {
    const progressFill = document.getElementById('global-progress-fill');
    const progressPercentage = document.getElementById('global-progress-percentage');
    const progressCurrentSong = document.getElementById('progress-current-song');
    const progressCount = document.getElementById('progress-count');
    
    if (!progressFill || !progressPercentage) return;
    
    if (data.status === 'analyzing') {
        progressCurrentSong.textContent = data.message;
        progressCount.textContent = '0/0';
    } else if (data.status === 'downloading') {
        const percentage = data.total > 0 ? Math.round((data.current / data.total) * 100) : 0;
        progressFill.style.width = `${percentage}%`;
        progressPercentage.textContent = `${percentage}%`;
        progressCurrentSong.textContent = data.current_song || data.message;
        progressCount.textContent = `${data.current}/${data.total}`;
    } else if (data.status === 'completed') {
        progressFill.style.width = '100%';
        progressPercentage.textContent = '100%';
        progressCurrentSong.textContent = data.message;
        progressCount.textContent = `${data.downloaded}/${data.total}`;
        
        // Hide after a delay
        setTimeout(() => {
            hideGlobalProgress();
        }, 2000);
    }
}


// Helper function to create message div if it doesn't exist
function createMessageDiv(form) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'form-message';
    form.appendChild(messageDiv);
    return messageDiv;
}

document.addEventListener('DOMContentLoaded', function () {
    socket = io();
    
    // Check if there's an active download on page load
    const progressContainer = document.getElementById('global-progress');
    if (progressContainer && progressContainer.style.display === 'block') {
        // There's an active download, connect to progress updates immediately
        console.log('Active download detected on page load');
    }
    
    // Initialize drag-and-drop functionality
    initDragAndDrop();
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

    // Listen for download progress updates
    socket.on('download_progress', function(data) {
        updateGlobalProgress(data);
    });

    // Listen for individual song additions during playlist download
    socket.on('song_added', function(data) {
        console.log('Song added to playlist:', data.title);
        // Could add visual notification here or refresh part of the playlist
        // For now, we'll let the final reload handle the full refresh
    });

    // Listen for playlist progress updates
    socket.on('playlist_progress', function(data) {
        updatePlaylistProgress(data);
    });

    socket.on('playback_update', function (data) {
        if (currentSongId && data.current_song_id) {
            updateProgress(data.position, data.duration, data.volume);
            if (isPlaying !== data.is_playing) {
                isPlaying = data.is_playing;
                updatePlayPauseButton(isPlaying);
            }
        } else if (!data.current_song_id && currentSongId) {
            // Song has finished or been reset
            currentSongId = null;
            currentSongDuration = 0;
            isPlaying = false;
            
            const elements = {
                duration: document.getElementById('duration'),
                currentTime: document.getElementById('current-time'),
                progress: document.getElementById('song-progress')
            };
            
            if (elements.duration) elements.duration.textContent = '0:00';
            if (elements.currentTime) elements.currentTime.textContent = '0:00';
            if (elements.progress) elements.progress.style.width = '0%';
            
            updatePlayPauseButton(false);
        }
    });

    socket.on('song_finished', function(data) {
        console.log('Song finished:', data.message);
        // Reload the page to get updated playlist order
        setTimeout(() => {
            window.location.reload();
        }, 1000);
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

    // Volume control buttons
    const volumeDownBtn = document.getElementById('volume-down-btn');
    const volumeUpBtn = document.getElementById('volume-up-btn');

    if (volumeDownBtn && volumeSlider) {
        volumeDownBtn.addEventListener('click', function() {
            const currentVolume = parseInt(volumeSlider.value);
            const newVolume = Math.max(0, currentVolume - 5); // Decrease by 5%
            volumeSlider.value = newVolume;
            socket.emit('set_volume', { value: newVolume });
            
            // Update button states
            updateVolumeButtonStates(newVolume);
        });
    }

    if (volumeUpBtn && volumeSlider) {
        volumeUpBtn.addEventListener('click', function() {
            const currentVolume = parseInt(volumeSlider.value);
            const newVolume = Math.min(100, currentVolume + 5); // Increase by 5%
            volumeSlider.value = newVolume;
            socket.emit('set_volume', { value: newVolume });
            
            // Update button states
            updateVolumeButtonStates(newVolume);
        });
    }

    // Function to update volume button states
    function updateVolumeButtonStates(volume) {
        if (volumeDownBtn) {
            volumeDownBtn.disabled = volume <= 0;
        }
        if (volumeUpBtn) {
            volumeUpBtn.disabled = volume >= 100;
        }
    }

    // Initialize button states
    if (volumeSlider) {
        updateVolumeButtonStates(parseInt(volumeSlider.value));
        
        // Also update states when slider changes
        volumeSlider.addEventListener('input', function() {
            updateVolumeButtonStates(parseInt(this.value));
        });
    }

    handleAddMusicForm();
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


    // Drag and drop for song reordering
    function initDragAndDrop() {
        const songList = document.getElementById('sortable-song-list');
        if (!songList) return;
        
        let draggedItem = null;
        
        // Initialize all song items
        const songItems = songList.querySelectorAll('.song-item');
        songItems.forEach(item => {
            // Set up drag start
            item.addEventListener('dragstart', function(e) {
                draggedItem = this;
                setTimeout(() => this.classList.add('dragging'), 0);
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/html', this.innerHTML);
            });
            
            // Set up drag end
            item.addEventListener('dragend', function() {
                this.classList.remove('dragging');
                draggedItem = null;
                
                // Update positions and save to server
                updateSongPositions();
            });
            
            // Handle drag over
            item.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                return false;
            });
            
            // Highlight drop area
            item.addEventListener('dragenter', function(e) {
                e.preventDefault();
                if (draggedItem !== this) {
                    this.classList.add('drag-over');
                }
            });
            
            // Remove highlight
            item.addEventListener('dragleave', function() {
                this.classList.remove('drag-over');
            });
            
            // Handle drop
            item.addEventListener('drop', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                this.classList.remove('drag-over');
                
                // Don't do anything if dropping on the original item
                if (draggedItem === this) return false;
                
                // Get positions 
                const list = Array.from(songList.children);
                const fromIndex = list.indexOf(draggedItem);
                const toIndex = list.indexOf(this);
                
                // Move element in the DOM
                if (fromIndex < toIndex) {
                    songList.insertBefore(draggedItem, this.nextElementSibling);
                } else {
                    songList.insertBefore(draggedItem, this);
                }
                
                return false;
            });
        });
    }

    // Update song positions after drag and drop
    function updateSongPositions() {
        const songList = document.getElementById('sortable-song-list');
        if (!songList) return;
        
        // Get all songs and their current order
        const songItems = Array.from(songList.querySelectorAll('.song-item'));
        const songOrder = songItems.map((item, index) => ({
            id: parseInt(item.dataset.id),
            position: index
        }));
        
        // Update the data-position attribute
        songItems.forEach((item, index) => {
            item.dataset.position = index;
        });
        // Create a notification to indicate status
        const notification = document.createElement('div');
        notification.className = 'song-order-notification';
        notification.textContent = 'Saving order...';
        notification.style.position = 'fixed';
        notification.style.bottom = '20px';
        notification.style.right = '20px';
        notification.style.padding = '10px 20px';
        notification.style.backgroundColor = 'rgba(33, 150, 243, 0.8)';
        notification.style.color = 'white';
        notification.style.borderRadius = '4px';
        notification.style.zIndex = '1000';
        document.body.appendChild(notification);
    
    // Send the new order to the server
    fetchWithCsrf('/update-song-order', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ songs: songOrder })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            notification.textContent = 'Order saved successfully!';
            notification.style.backgroundColor = 'rgba(76, 175, 80, 0.8)';
            setTimeout(() => {
                notification.remove();
            }, 2000);
        } else {
            notification.textContent = 'Failed to save order: ' + (data.message || 'Unknown error');
            notification.style.backgroundColor = 'rgba(244, 67, 54, 0.8)';
            setTimeout(() => {
                notification.remove();
            }, 3000);
            console.error('Failed to update song order:', data.message);
        }
    })
    .catch(error => {
        notification.textContent = 'Error saving order';
        notification.style.backgroundColor = 'rgba(244, 67, 54, 0.8)';
        setTimeout(() => {
            notification.remove();
        }, 3000);
        console.error('Error updating song order:', error);
    });
    }

    if (!playerControls?.classList.contains('hidden')) {
        startProgressPolling();
    }
    setInterval(() => {
        if (!playerControls || playerControls.classList.contains('hidden')) {
            window.location.reload();
        }
    }, 60000);

    // yt-dlp update button handler
    const updateYtdlpBtn = document.getElementById('update-ytdlp-btn');
    if (updateYtdlpBtn) {
        updateYtdlpBtn.addEventListener('click', async function() {
            const button = this;
            const icon = button.querySelector('i');
            const originalText = button.textContent;
            
            // Show loading state
            button.disabled = true;
            icon.className = 'fas fa-sync-alt fa-spin';
            button.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Updating...';
            
            try {
                const response = await fetchWithCsrf('/update-ytdlp', {
                    method: 'POST'
                });
                const data = await response.json();
                
                if (data.success) {
                    // Show success message briefly
                    button.innerHTML = '<i class="fas fa-check"></i> Updated!';
                    setTimeout(() => {
                        window.location.reload(); // Refresh to show new version
                    }, 1500);
                } else {
                    showError(button.closest('.ytdlp-container'), data.message || 'Failed to update yt-dlp');
                    // Reset button
                    button.disabled = false;
                    button.innerHTML = originalText;
                }
            } catch (error) {
                console.error('Update yt-dlp error:', error);
                showError(button.closest('.ytdlp-container'), 'Network error occurred');
                // Reset button
                button.disabled = false;
                button.innerHTML = originalText;
            }
        });
    }

    // Schedule form toggle functionality
    const toggleScheduleBtn = document.getElementById('toggle-schedule-form');
    const scheduleForm = document.getElementById('add-schedule-form');
    const cancelScheduleBtn = document.getElementById('cancel-schedule-form');

    if (toggleScheduleBtn && scheduleForm) {
        toggleScheduleBtn.addEventListener('click', function() {
            const isCollapsed = scheduleForm.classList.contains('collapsed');
            
            if (isCollapsed) {
                // Show form
                scheduleForm.classList.remove('collapsed');
                this.classList.add('active');
                this.innerHTML = '<i class="fas fa-plus"></i> Cancel';
            } else {
                // Hide form
                scheduleForm.classList.add('collapsed');
                this.classList.remove('active');
                this.innerHTML = '<i class="fas fa-plus"></i> Add New';
                // Reset form
                scheduleForm.reset();
            }
        });

        if (cancelScheduleBtn) {
            cancelScheduleBtn.addEventListener('click', function() {
                // Hide form
                scheduleForm.classList.add('collapsed');
                toggleScheduleBtn.classList.remove('active');
                toggleScheduleBtn.innerHTML = '<i class="fas fa-plus"></i> Add New';
                // Reset form
                scheduleForm.reset();
            });
        }
    }

    // Generic collapsible sections functionality
    const toggleSectionBtns = document.querySelectorAll('.toggle-section-btn');
    
    toggleSectionBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const targetId = this.getAttribute('data-target');
            const targetContent = document.getElementById(targetId);
            const isCollapsed = targetContent.classList.contains('collapsed');
            
            if (isCollapsed) {
                // Show content
                targetContent.classList.remove('collapsed');
                this.classList.add('active');
            } else {
                // Hide content
                targetContent.classList.add('collapsed');
                this.classList.remove('active');
            }
        });
    });

    // Also make section headers clickable
    const sectionHeaders = document.querySelectorAll('.collapsible-section .section-header');
    
    sectionHeaders.forEach(header => {
        header.addEventListener('click', function() {
            const toggleBtn = this.querySelector('.toggle-section-btn');
            if (toggleBtn) {
                toggleBtn.click();
            }
        });
    });
});