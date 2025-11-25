// Song type
export interface Song {
  id: number;
  title: string;
  duration: number;
  source: string;
  file_path: string;
  position: number;
  last_played_at: string | null;
  priority: number;
  created_at: string;
}

// Schedule type
export interface Schedule {
  id: number;
  time: string;
  is_active: boolean;
  one_time: boolean;
  monday: boolean;
  tuesday: boolean;
  wednesday: boolean;
  thursday: boolean;
  friday: boolean;
  saturday: boolean;
  sunday: boolean;
}

// Playback state from server
export interface PlaybackState {
  is_playing: boolean;
  current_song_id: number | null;
  current_song_title: string | null;
  position: number;
  duration: number;
  volume: number;
}

// Download state
export interface DownloadState {
  active: boolean;
  progress: number;
  current_file: string;
  status: string;
  error: string | null;
  playlist_progress?: {
    current: number;
    total: number;
  };
}

// Disk usage info
export interface DiskUsage {
  used: number;
  total: number;
  percent: number;
  used_formatted: string;
  total_formatted: string;
}

// Playback settings
export interface PlaybackSettings {
  shuffle_mode: boolean;
  fade_enabled: boolean;
  fade_duration: number;
}

// Initial state from API
export interface InitialState {
  songs: Song[];
  schedules: Schedule[];
  is_playing: boolean;
  current_song_id: number | null;
  current_song_title: string | null;
  volume: number;
  download_state: DownloadState;
  next_schedule: {
    time: string;
    song_title: string;
  } | null;
  disk_usage: DiskUsage;
  ytdlp_version: string;
  is_authenticated: boolean;
  username: string;
  settings?: PlaybackSettings;
}

// Toast notification type
export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}
