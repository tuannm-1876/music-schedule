import { useState } from 'react';
import { motion, AnimatePresence, Reorder } from 'framer-motion';
import { 
  Music, 
  Play, 
  Trash2, 
  GripVertical,
  Youtube,
  Upload,
  Clock,
  ArrowUpDown,
  Megaphone,
  ChevronDown,
  Trash
} from 'lucide-react';
import { useSocket } from '@/contexts/SocketContext';
import { useToast } from '@/contexts/ToastContext';
import { Button, Card } from '@/components/ui';
import { musicApi } from '@/lib/api';
import { formatDuration } from '@/lib/utils';
import type { Song, SongCategory } from '@/types';

export function Playlist() {
  const { songs, setSongs, playbackState, sortUnplayedFirst } = useSocket();
  const { addToast } = useToast();
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [playingId, setPlayingId] = useState<number | null>(null);
  const [filterCategory, setFilterCategory] = useState<SongCategory | 'all'>('all');

  const handlePlay = async (songId: number) => {
    setPlayingId(songId);
    try {
      await musicApi.play(songId);
    } catch (error) {
      console.error('Failed to play song:', error);
      addToast('error', 'Không thể phát bài hát');
    } finally {
      setPlayingId(null);
    }
  };

  const handleDelete = async (songId: number) => {
    setDeletingId(songId);
    try {
      await musicApi.deleteSong(songId);
      setSongs((prev) => prev.filter((s) => s.id !== songId));
      addToast('success', 'Đã xóa bài hát');
    } catch (error) {
      console.error('Failed to delete song:', error);
      addToast('error', 'Không thể xóa bài hát');
    } finally {
      setDeletingId(null);
    }
  };

  const handleCategoryChange = async (songId: number, newCategory: SongCategory) => {
    try {
      await musicApi.updateCategory(songId, newCategory);
      setSongs((prev) =>
        prev.map((s) => (s.id === songId ? { ...s, category: newCategory } : s))
      );
      addToast('success', `Đã chuyển sang ${newCategory === 'music' ? 'Nhạc' : 'Truyền thông'}`);
    } catch (error) {
      console.error('Failed to update category:', error);
      addToast('error', 'Không thể cập nhật loại bài');
    }
  };

  const handleToggleDeleteAfterPlay = async (songId: number) => {
    try {
      const response = await musicApi.toggleDeleteAfterPlay(songId);
      const newValue = response.data.song.delete_after_play;
      setSongs((prev) =>
        prev.map((s) => (s.id === songId ? { ...s, delete_after_play: newValue } : s))
      );
      addToast('success', newValue ? 'Sẽ xóa sau khi phát' : 'Đã tắt xóa sau khi phát');
    } catch (error) {
      console.error('Failed to toggle delete after play:', error);
      addToast('error', 'Không thể cập nhật cài đặt');
    }
  };

  const handleReorder = async (newOrder: Song[]) => {
    setSongs(newOrder);
    try {
      await musicApi.updateOrder(newOrder.map((s) => s.id));
    } catch (error) {
      console.error('Failed to update order:', error);
      addToast('error', 'Không thể cập nhật thứ tự');
    }
  };

  const handleSortUnplayed = () => {
    sortUnplayedFirst();
    addToast('info', 'Đang sắp xếp playlist...');
  };

  const getSourceIcon = (source: string) => {
    if (source.toLowerCase().includes('youtube')) {
      return <Youtube className="w-3 h-3 text-red-500" />;
    }
    return <Upload className="w-3 h-3 text-blue-500" />;
  };

  // Filter songs by category
  const filteredSongs = filterCategory === 'all' 
    ? songs 
    : songs.filter(s => (s.category || 'music') === filterCategory);

  // Count by category
  const musicCount = songs.filter(s => (s.category || 'music') === 'music').length;
  const announcementCount = songs.filter(s => s.category === 'announcement').length;

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary/20 to-purple-500/20 flex items-center justify-center">
              <Music className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="font-semibold">Playlist</h2>
              <p className="text-sm text-muted-foreground">
                {songs.length} bài hát
              </p>
            </div>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={handleSortUnplayed}
            className="gap-2"
          >
            <ArrowUpDown className="w-4 h-4" />
            Sắp xếp
          </Button>
        </div>

        {/* Category Filter Tabs */}
        <div className="flex gap-2">
          <button
            onClick={() => setFilterCategory('all')}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
              filterCategory === 'all'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted hover:bg-muted/80'
            }`}
          >
            Tất cả ({songs.length})
          </button>
          <button
            onClick={() => setFilterCategory('music')}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors flex items-center gap-1.5 ${
              filterCategory === 'music'
                ? 'bg-blue-500 text-white'
                : 'bg-muted hover:bg-muted/80'
            }`}
          >
            <Music className="w-3.5 h-3.5" />
            Nhạc ({musicCount})
          </button>
          <button
            onClick={() => setFilterCategory('announcement')}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors flex items-center gap-1.5 ${
              filterCategory === 'announcement'
                ? 'bg-orange-500 text-white'
                : 'bg-muted hover:bg-muted/80'
            }`}
          >
            <Megaphone className="w-3.5 h-3.5" />
            Truyền thông ({announcementCount})
          </button>
        </div>
      </div>

      {/* Song List */}
      <div className="divide-y divide-border max-h-[600px] overflow-y-auto">
        {filteredSongs.length === 0 ? (
          <div className="p-8 text-center">
            <Music className="w-12 h-12 mx-auto text-muted-foreground/50 mb-3" />
            <p className="text-muted-foreground">Chưa có bài hát nào</p>
            <p className="text-sm text-muted-foreground/70 mt-1">
              Thêm nhạc từ YouTube hoặc tải file lên
            </p>
          </div>
        ) : (
          <Reorder.Group
            axis="y"
            values={filteredSongs}
            onReorder={handleReorder}
            className="divide-y divide-border"
          >
            <AnimatePresence>
              {filteredSongs.map((song, index) => (
                <Reorder.Item
                  key={song.id}
                  value={song}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -100 }}
                  transition={{ delay: index * 0.05 }}
                >
                  <SongItem
                    song={song}
                    isPlaying={playbackState.current_song_id === song.id}
                    isCurrentlyLoading={playingId === song.id}
                    isDeleting={deletingId === song.id}
                    onPlay={() => handlePlay(song.id)}
                    onDelete={() => handleDelete(song.id)}
                    onCategoryChange={(cat) => handleCategoryChange(song.id, cat)}
                    onToggleDeleteAfterPlay={() => handleToggleDeleteAfterPlay(song.id)}
                    getSourceIcon={getSourceIcon}
                  />
                </Reorder.Item>
              ))}
            </AnimatePresence>
          </Reorder.Group>
        )}
      </div>
    </Card>
  );
}

interface SongItemProps {
  song: Song;
  isPlaying: boolean;
  isCurrentlyLoading: boolean;
  isDeleting: boolean;
  onPlay: () => void;
  onDelete: () => void;
  onCategoryChange: (category: SongCategory) => void;
  onToggleDeleteAfterPlay: () => void;
  getSourceIcon: (source: string) => React.ReactNode;
}

function SongItem({
  song,
  isPlaying,
  isCurrentlyLoading,
  isDeleting,
  onPlay,
  onDelete,
  onCategoryChange,
  onToggleDeleteAfterPlay,
  getSourceIcon,
}: SongItemProps) {
  const [showActions, setShowActions] = useState(false);
  const [showCategoryMenu, setShowCategoryMenu] = useState(false);

  const categoryConfig = {
    music: { label: 'Nhạc', color: 'bg-blue-500/20 text-blue-600 dark:text-blue-400', icon: Music },
    announcement: { label: 'Truyền thông', color: 'bg-orange-500/20 text-orange-600 dark:text-orange-400', icon: Megaphone },
  };

  const currentCategory = song.category || 'music';
  const config = categoryConfig[currentCategory];

  return (
    <motion.div
      className={`group relative flex items-center gap-3 px-4 py-3 transition-colors ${
        isPlaying
          ? 'bg-primary/10'
          : 'hover:bg-muted/50'
      }`}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {/* Drag Handle */}
      <div className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground transition-colors">
        <GripVertical className="w-4 h-4" />
      </div>

      {/* Playing Indicator / Play Button */}
      <div className="relative w-10 h-10 shrink-0">
        {isPlaying ? (
          <div className="w-full h-full rounded-lg bg-primary flex items-center justify-center">
            <motion.div
              className="flex items-end gap-0.5 h-4"
              animate={{ scale: [1, 1.1, 1] }}
              transition={{ duration: 1, repeat: Infinity }}
            >
              {[1, 2, 3].map((i) => (
                <motion.div
                  key={i}
                  className="w-1 bg-white rounded-full"
                  animate={{ height: ['40%', '100%', '40%'] }}
                  transition={{
                    duration: 0.5,
                    repeat: Infinity,
                    delay: i * 0.1,
                  }}
                />
              ))}
            </motion.div>
          </div>
        ) : (
          <button
            onClick={onPlay}
            disabled={isCurrentlyLoading}
            className="w-full h-full rounded-lg bg-muted group-hover:bg-primary/20 flex items-center justify-center transition-all hover:scale-105"
          >
            {isCurrentlyLoading ? (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              >
                <Clock className="w-4 h-4" />
              </motion.div>
            ) : (
              <Play className="w-4 h-4 ml-0.5" />
            )}
          </button>
        )}
      </div>

      {/* Song Info */}
      <div className="flex-1 min-w-0">
        <p className={`font-medium truncate ${isPlaying ? 'text-primary' : ''}`}>
          {song.title}
        </p>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
          <span className="flex items-center gap-1">
            {getSourceIcon(song.source)}
            {song.source}
          </span>
          <span>•</span>
          <span>{formatDuration(song.duration)}</span>
          {song.last_played_at && (
            <>
              <span>•</span>
              <span className="text-green-600 dark:text-green-400">Đã phát</span>
            </>
          )}
        </div>
      </div>

      {/* Category Badge with Dropdown */}
      <div className="relative">
        <button
          onClick={() => setShowCategoryMenu(!showCategoryMenu)}
          className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-colors ${config.color}`}
        >
          <config.icon className="w-3 h-3" />
          {config.label}
          <ChevronDown className="w-3 h-3" />
        </button>

        <AnimatePresence>
          {showCategoryMenu && (
            <motion.div
              initial={{ opacity: 0, y: -5, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -5, scale: 0.95 }}
              className="absolute right-0 top-full mt-1 z-50 bg-card border border-border rounded-lg shadow-lg overflow-hidden min-w-[140px]"
            >
              <button
                onClick={() => {
                  onCategoryChange('music');
                  setShowCategoryMenu(false);
                }}
                className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors ${
                  currentCategory === 'music' ? 'bg-primary/10' : ''
                }`}
              >
                <Music className="w-4 h-4 text-blue-500" />
                Nhạc
                {currentCategory === 'music' && <span className="ml-auto text-primary">✓</span>}
              </button>
              <button
                onClick={() => {
                  onCategoryChange('announcement');
                  setShowCategoryMenu(false);
                }}
                className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors ${
                  currentCategory === 'announcement' ? 'bg-primary/10' : ''
                }`}
              >
                <Megaphone className="w-4 h-4 text-orange-500" />
                Truyền thông
                {currentCategory === 'announcement' && <span className="ml-auto text-primary">✓</span>}
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Delete After Play Badge */}
      {song.delete_after_play && (
        <div className="flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-red-500/20 text-red-600 dark:text-red-400">
          <Trash className="w-3 h-3" />
          Xóa sau phát
        </div>
      )}

      {/* Actions */}
      <AnimatePresence>
        {(showActions || isDeleting) && (
          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            className="flex items-center gap-1"
          >
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggleDeleteAfterPlay}
              title={song.delete_after_play ? 'Tắt xóa sau khi phát' : 'Xóa sau khi phát'}
              className={`h-8 w-8 ${
                song.delete_after_play 
                  ? 'text-red-500 hover:text-red-600 hover:bg-red-500/10' 
                  : 'text-muted-foreground hover:text-red-500 hover:bg-red-500/10'
              }`}
            >
              <Trash className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onDelete}
              disabled={isDeleting}
              className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
            >
              {isDeleting ? (
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                >
                  <Clock className="w-4 h-4" />
                </motion.div>
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
