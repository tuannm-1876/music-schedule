import React, { createContext, useContext, useEffect, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import type { PlaybackState, DownloadState, Song, Schedule, PlaybackSettings } from '@/types';

interface SocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  playbackState: PlaybackState;
  downloadState: DownloadState;
  songs: Song[];
  schedules: Schedule[];
  nextSchedule: { time: string; song_title: string } | null;
  settings: PlaybackSettings;
  setSongs: React.Dispatch<React.SetStateAction<Song[]>>;
  setSchedules: React.Dispatch<React.SetStateAction<Schedule[]>>;
  setPlaybackState: React.Dispatch<React.SetStateAction<PlaybackState>>;
  setNextSchedule: React.Dispatch<React.SetStateAction<{ time: string; song_title: string } | null>>;
  setSettings: React.Dispatch<React.SetStateAction<PlaybackSettings>>;
  togglePlayPause: () => void;
  stopMusic: () => void;
  setVolume: (volume: number) => void;
  sortUnplayedFirst: () => void;
  toggleShuffle: () => void;
  toggleFade: () => void;
  setFadeDuration: (duration: number) => void;
}

const defaultPlaybackState: PlaybackState = {
  is_playing: false,
  current_song_id: null,
  current_song_title: null,
  position: 0,
  duration: 0,
  volume: 100,
};

const defaultDownloadState: DownloadState = {
  active: false,
  progress: 0,
  current_file: '',
  status: '',
  error: null,
};

const defaultSettings: PlaybackSettings = {
  shuffle_mode: false,
  fade_enabled: true,
  fade_duration: 2.0,
};

const SocketContext = createContext<SocketContextType | null>(null);

export function SocketProvider({ children }: { children: React.ReactNode }) {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [playbackState, setPlaybackState] = useState<PlaybackState>(defaultPlaybackState);
  const [downloadState, setDownloadState] = useState<DownloadState>(defaultDownloadState);
  const [songs, setSongs] = useState<Song[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [nextSchedule, setNextSchedule] = useState<{ time: string; song_title: string } | null>(null);
  const [settings, setSettings] = useState<PlaybackSettings>(defaultSettings);

  useEffect(() => {
    const socketInstance = io({
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    socketInstance.on('connect', () => {
      console.log('Socket connected');
      setIsConnected(true);
    });

    socketInstance.on('disconnect', () => {
      console.log('Socket disconnected');
      setIsConnected(false);
    });

    // Playback updates
    socketInstance.on('playback_update', (data: any) => {
      setPlaybackState((prev) => ({
        ...prev,
        is_playing: data.is_playing ?? prev.is_playing,
        current_song_id: data.current_song_id ?? prev.current_song_id,
        current_song_title: data.current_song_title ?? prev.current_song_title,
        position: data.position ?? prev.position,
        duration: data.duration ?? prev.duration,
        volume: data.volume ?? prev.volume,
      }));
    });

    // Music stopped
    socketInstance.on('music_stopped', () => {
      setPlaybackState((prev) => ({
        ...prev,
        is_playing: false,
        position: 0,
      }));
    });

    // Song finished
    socketInstance.on('song_finished', (data: { songs?: Song[]; next_schedule?: { time: string; song_title: string } | null; deleted_song_id?: number }) => {
      if (data.songs) {
        setSongs(data.songs);
      } else if (data.deleted_song_id) {
        // Remove the deleted song from the list
        setSongs(prev => prev.filter(s => s.id !== data.deleted_song_id));
      }
      if (data.next_schedule !== undefined) {
        setNextSchedule(data.next_schedule);
      }
    });

    // Song added
    socketInstance.on('song_added', (data: { song: Song; songs: Song[] }) => {
      setSongs(data.songs);
    });

    // Download progress
    socketInstance.on('download_progress', (data: any) => {
      // Map backend download state to frontend format
      setDownloadState({
        active: data.status !== 'idle' && data.status !== 'completed' && data.status !== 'error',
        progress: data.current && data.total ? (data.current / data.total) * 100 : 0,
        current_file: data.current_song || data.message || '',
        status: data.status || '',
        error: data.status === 'error' ? data.message : null,
        playlist_progress: data.total > 1 ? {
          current: data.current || 0,
          total: data.total || 0
        } : undefined
      });
    });

    // Volume updated
    socketInstance.on('volume_updated', (data: { volume: number }) => {
      setPlaybackState((prev) => ({ ...prev, volume: data.volume }));
    });

    // Schedule triggered
    socketInstance.on('schedule_triggered', (data: { message: string; song: string }) => {
      console.log('Schedule triggered:', data);
    });

    // Schedule updated (e.g., one-time schedule disabled)
    socketInstance.on('schedule_updated', (data: { id: number; is_active: boolean }) => {
      setSchedules((prev) =>
        prev.map((s) =>
          s.id === data.id ? { ...s, is_active: data.is_active } : s
        )
      );
    });

    // Sort completed
    socketInstance.on('sort_completed', (data: { songs: Song[] }) => {
      setSongs(data.songs);
    });

    // Next schedule update
    socketInstance.on('next_schedule_update', (data: { next_schedule: { time: string; song_title: string } | null }) => {
      setNextSchedule(data.next_schedule);
    });

    // Settings updated
    socketInstance.on('settings_updated', (data: PlaybackSettings) => {
      setSettings(data);
    });

    setSocket(socketInstance);

    return () => {
      socketInstance.disconnect();
    };
  }, []);

  const togglePlayPause = () => {
    socket?.emit('toggle_play_pause');
  };

  const stopMusic = () => {
    socket?.emit('stop_music');
  };

  const setVolume = (volume: number) => {
    socket?.emit('set_volume', { volume });
  };

  const sortUnplayedFirst = () => {
    socket?.emit('sort_unplayed_first');
  };

  const toggleShuffle = () => {
    socket?.emit('toggle_shuffle');
  };

  const toggleFade = () => {
    socket?.emit('toggle_fade');
  };

  const setFadeDurationFn = (duration: number) => {
    socket?.emit('set_fade_duration', { duration });
  };

  return (
    <SocketContext.Provider
      value={{
        socket,
        isConnected,
        playbackState,
        downloadState,
        songs,
        schedules,
        nextSchedule,
        settings,
        setSongs,
        setSchedules,
        setPlaybackState,
        setNextSchedule,
        setSettings,
        togglePlayPause,
        stopMusic,
        setVolume,
        sortUnplayedFirst,
        toggleShuffle,
        toggleFade,
        setFadeDuration: setFadeDurationFn,
      }}
    >
      {children}
    </SocketContext.Provider>
  );
}

export function useSocket() {
  const context = useContext(SocketContext);
  if (!context) {
    throw new Error('useSocket must be used within a SocketProvider');
  }
  return context;
}
