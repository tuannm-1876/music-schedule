import { motion, AnimatePresence } from 'framer-motion';
import { Play, Pause, Square, Volume2, VolumeX, Music, Shuffle, Settings, X } from 'lucide-react';
import { useSocket } from '@/contexts/SocketContext';
import { Button, Slider } from '@/components/ui';
import { formatDuration } from '@/lib/utils';
import { musicApi } from '@/lib/api';
import { useState, useRef, useEffect } from 'react';

export function Player() {
  const { playbackState, togglePlayPause, stopMusic, setVolume, settings, toggleShuffle, toggleFade, setFadeDuration } = useSocket();
  const [localVolume, setLocalVolume] = useState(playbackState.volume);
  const [isMuted, setIsMuted] = useState(false);
  const [previousVolume, setPreviousVolume] = useState(100);
  const [showSettings, setShowSettings] = useState(false);
  const settingsRef = useRef<HTMLDivElement>(null);

  const { is_playing, current_song_title, position, duration } = playbackState;
  const progress = duration > 0 ? (position / duration) * 100 : 0;

  // Close settings when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (settingsRef.current && !settingsRef.current.contains(event.target as Node)) {
        setShowSettings(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSeek = async (e: React.MouseEvent<HTMLDivElement>) => {
    if (!duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    const newPosition = percentage * duration;
    
    try {
      await musicApi.seek(newPosition);
    } catch (error) {
      console.error('Failed to seek:', error);
    }
  };

  const handleVolumeChange = (value: number) => {
    setLocalVolume(value);
    setVolume(value);
    if (value > 0) {
      setIsMuted(false);
    }
  };

  const toggleMute = () => {
    if (isMuted) {
      handleVolumeChange(previousVolume);
      setIsMuted(false);
    } else {
      setPreviousVolume(localVolume);
      handleVolumeChange(0);
      setIsMuted(true);
    }
  };

  return (
    <motion.div
      initial={{ y: 100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="fixed bottom-0 left-0 right-0 z-40"
    >
      <div className="glass border-t border-border shadow-2xl">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center gap-4">
            {/* Album Art / Now Playing */}
            <div className="flex items-center gap-3 min-w-0 flex-1">
              <motion.div
                animate={{ rotate: is_playing ? 360 : 0 }}
                transition={{ duration: 3, repeat: is_playing ? Infinity : 0, ease: 'linear' }}
                className="relative w-12 h-12 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center shrink-0 shadow-lg"
              >
                <Music className="w-6 h-6 text-white" />
                {is_playing && (
                  <motion.div
                    className="absolute inset-0 rounded-full border-2 border-primary"
                    animate={{ scale: [1, 1.2, 1], opacity: [1, 0, 1] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  />
                )}
              </motion.div>
              
              <div className="min-w-0">
                <AnimatePresence mode="wait">
                  <motion.p
                    key={current_song_title || 'no-song'}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="font-medium text-sm truncate"
                  >
                    {current_song_title || 'Chưa có bài hát'}
                  </motion.p>
                </AnimatePresence>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>{formatDuration(position)}</span>
                  <span>/</span>
                  <span>{formatDuration(duration)}</span>
                </div>
              </div>
            </div>

            {/* Playback Controls */}
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={togglePlayPause}
                className="h-12 w-12 rounded-full hover:bg-primary/10"
                disabled={!current_song_title && !playbackState.current_song_id && !is_playing}
              >
                <AnimatePresence mode="wait">
                  {is_playing ? (
                    <motion.div
                      key="pause"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      exit={{ scale: 0 }}
                    >
                      <Pause className="w-6 h-6" />
                    </motion.div>
                  ) : (
                    <motion.div
                      key="play"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      exit={{ scale: 0 }}
                    >
                      <Play className="w-6 h-6 ml-0.5" />
                    </motion.div>
                  )}
                </AnimatePresence>
              </Button>
              
              <Button
                variant="ghost"
                size="icon"
                onClick={stopMusic}
                className="h-10 w-10 rounded-full hover:bg-destructive/10 hover:text-destructive"
                disabled={!is_playing && !current_song_title}
              >
                <Square className="w-4 h-4" />
              </Button>
            </div>

            {/* Progress Bar */}
            <div
              className="flex-1 max-w-md cursor-pointer group"
              onClick={handleSeek}
            >
              <div className="relative h-2 bg-muted rounded-full overflow-hidden">
                <motion.div
                  className="absolute h-full bg-gradient-to-r from-primary to-purple-500"
                  style={{ width: `${progress}%` }}
                  transition={{ type: 'tween', duration: 0.1 }}
                />
                <div className="absolute h-full w-full bg-transparent group-hover:bg-white/5 transition-colors" />
              </div>
            </div>

            {/* Volume Control */}
            <div className="flex items-center gap-2 w-32">
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleMute}
                className="h-8 w-8 shrink-0"
              >
                {isMuted || localVolume === 0 ? (
                  <VolumeX className="w-4 h-4" />
                ) : (
                  <Volume2 className="w-4 h-4" />
                )}
              </Button>
              <Slider
                value={localVolume}
                min={0}
                max={100}
                onValueChange={handleVolumeChange}
                className="flex-1"
              />
            </div>

            {/* Shuffle & Settings */}
            <div className="flex items-center gap-1 relative" ref={settingsRef}>
              {/* Shuffle Toggle */}
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleShuffle}
                className={`h-8 w-8 shrink-0 transition-colors ${
                  settings.shuffle_mode 
                    ? 'text-primary bg-primary/10 hover:bg-primary/20' 
                    : 'hover:bg-muted'
                }`}
                title={settings.shuffle_mode ? 'Tắt phát ngẫu nhiên' : 'Bật phát ngẫu nhiên'}
              >
                <Shuffle className="w-4 h-4" />
              </Button>

              {/* Settings Button */}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowSettings(!showSettings)}
                className={`h-8 w-8 shrink-0 transition-colors ${
                  showSettings ? 'bg-muted' : 'hover:bg-muted'
                }`}
                title="Cài đặt phát nhạc"
              >
                <Settings className="w-4 h-4" />
              </Button>

              {/* Settings Dropdown */}
              <AnimatePresence>
                {showSettings && (
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    transition={{ duration: 0.15 }}
                    className="absolute bottom-full right-0 mb-2 w-72 p-4 bg-card/95 backdrop-blur-xl rounded-lg border border-border shadow-2xl z-50"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="text-sm font-medium">Cài đặt phát nhạc</h4>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setShowSettings(false)}
                        className="h-6 w-6"
                      >
                        <X className="w-3.5 h-3.5" />
                      </Button>
                    </div>

                    {/* Shuffle Mode */}
                    <div className="flex items-center justify-between py-3 border-b border-border">
                      <div className="flex-1 min-w-0 mr-3">
                        <p className="text-sm font-medium">Phát ngẫu nhiên</p>
                        <p className="text-xs text-muted-foreground">Xáo trộn thứ tự phát</p>
                      </div>
                      <button
                        onClick={toggleShuffle}
                        className={`relative flex-shrink-0 w-11 h-6 rounded-full transition-colors duration-200 ${
                          settings.shuffle_mode ? 'bg-primary' : 'bg-muted-foreground/30'
                        }`}
                      >
                        <span
                          className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white shadow-md transition-transform duration-200 ${
                            settings.shuffle_mode ? 'translate-x-5' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>

                    {/* Fade In/Out */}
                    <div className="flex items-center justify-between py-3 border-b border-border">
                      <div className="flex-1 min-w-0 mr-3">
                        <p className="text-sm font-medium">Fade In/Out</p>
                        <p className="text-xs text-muted-foreground">Chuyển bài mượt mà</p>
                      </div>
                      <button
                        onClick={toggleFade}
                        className={`relative flex-shrink-0 w-11 h-6 rounded-full transition-colors duration-200 ${
                          settings.fade_enabled ? 'bg-primary' : 'bg-muted-foreground/30'
                        }`}
                      >
                        <span
                          className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white shadow-md transition-transform duration-200 ${
                            settings.fade_enabled ? 'translate-x-5' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>

                    {/* Fade Duration */}
                    <AnimatePresence>
                      {settings.fade_enabled && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          className="overflow-hidden"
                        >
                          <div className="pt-3">
                            <div className="flex items-center justify-between mb-2">
                              <p className="text-sm">Thời gian fade</p>
                              <span className="text-xs font-medium bg-primary/20 text-primary px-2 py-0.5 rounded">{settings.fade_duration}s</span>
                            </div>
                            <div className="px-1">
                              <Slider
                                value={settings.fade_duration}
                                min={0.5}
                                max={5}
                                step={0.5}
                                onValueChange={(v) => setFadeDuration(v)}
                                className="w-full"
                              />
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
