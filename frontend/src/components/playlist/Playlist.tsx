import { useState } from 'react';
import { motion, AnimatePresence, Reorder, useDragControls } from 'framer-motion';
import { 
  Music, 
  Play, 
  Trash2, 
  GripVertical,
  Youtube,
  Upload,
  Clock,
  ArrowUpDown,
  ChevronDown,
  Trash,
  ListMusic
} from 'lucide-react';
import { useSocket } from '@/contexts/SocketContext';
import { useToast } from '@/contexts/ToastContext';
import { Button, Card } from '@/components/ui';
import { musicApi, playlistApi } from '@/lib/api';
import { formatDuration } from '@/lib/utils';
import type { Song } from '@/types';

export function Playlist() {
  const { songs, setSongs, playbackState, sortUnplayedFirst, playlists } = useSocket();
  const { addToast } = useToast();
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [playingId, setPlayingId] = useState<number | null>(null);
  const [filterPlaylist, setFilterPlaylist] = useState<number | 'all'>('all');

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

  const handlePlaylistAssign = async (songId: number, playlistIdVal: number | null) => {
    try {
      await playlistApi.assignSong(songId, playlistIdVal);
      setSongs((prev) =>
        prev.map((s) => (s.id === songId ? { ...s, playlist_id: playlistIdVal } : s))
      );
      const playlistName = playlistIdVal
        ? playlists.find(p => p.id === playlistIdVal)?.name || 'Playlist'
        : 'Chung';
      addToast('success', `Đã gán vào ${playlistName}`);
    } catch {
      addToast('error', 'Không thể gán playlist');
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

  // Filter songs by playlist
  let filteredSongs = songs;
  
  if (filterPlaylist !== 'all') {
    filteredSongs = filteredSongs.filter(s => 
      filterPlaylist === 0 ? !s.playlist_id : s.playlist_id === filterPlaylist
    );
  }

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

        {/* Playlist Filter Tabs */}
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setFilterPlaylist('all')}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors flex items-center gap-1.5 ${
              filterPlaylist === 'all'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted hover:bg-muted/80'
            }`}
          >
            <ListMusic className="w-3.5 h-3.5" />
            Tất cả ({songs.length})
          </button>
          {playlists.length > 0 && (
            <>
              <button
                onClick={() => setFilterPlaylist(0)}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  filterPlaylist === 0
                    ? 'bg-gray-500 text-white'
                    : 'bg-muted hover:bg-muted/80'
                }`}
              >
                Chưa gán ({songs.filter(s => !s.playlist_id).length})
              </button>
              {playlists.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setFilterPlaylist(p.id)}
                  className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                    filterPlaylist === p.id
                      ? 'bg-green-500 text-white'
                      : 'bg-muted hover:bg-muted/80'
                  }`}
                >
                  {p.name} ({songs.filter(s => s.playlist_id === p.id).length})
                </button>
              ))}
            </>
          )}
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
                <SongItem
                  key={song.id}
                  song={song}
                  isPlaying={playbackState.current_song_id === song.id}
                  isCurrentlyLoading={playingId === song.id}
                  isDeleting={deletingId === song.id}
                  onPlay={() => handlePlay(song.id)}
                  onDelete={() => handleDelete(song.id)}
                  onToggleDeleteAfterPlay={() => handleToggleDeleteAfterPlay(song.id)}
                  onPlaylistAssign={(pId) => handlePlaylistAssign(song.id, pId)}
                  playlists={playlists}
                  getSourceIcon={getSourceIcon}
                  index={index}
                />
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
  onToggleDeleteAfterPlay: () => void;
  onPlaylistAssign: (playlistId: number | null) => void;
  playlists: { id: number; name: string }[];
  getSourceIcon: (source: string) => React.ReactNode;
  index: number;
}

function SongItem({
  song,
  isPlaying,
  isCurrentlyLoading,
  isDeleting,
  onPlay,
  onDelete,
  onToggleDeleteAfterPlay,
  onPlaylistAssign,
  playlists,
  getSourceIcon,
  index,
}: SongItemProps) {
  const [showActions, setShowActions] = useState(false);
  const [showPlaylistMenu, setShowPlaylistMenu] = useState(false);
  const dragControls = useDragControls();

  return (
    <Reorder.Item
      value={song}
      dragListener={false}
      dragControls={dragControls}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -100 }}
      transition={{ delay: index * 0.05 }}
    >
      <motion.div
        className={`group relative flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-3 transition-colors ${
          isPlaying
            ? 'bg-primary/10'
            : 'hover:bg-muted/50'
        }`}
        onMouseEnter={() => setShowActions(true)}
        onMouseLeave={() => setShowActions(false)}
      >
        {/* Drag Handle - Only this triggers drag */}
        <div 
          className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground transition-colors touch-none select-none p-2 -m-2 shrink-0"
          onPointerDown={(e) => dragControls.start(e)}
        >
          <GripVertical className="w-5 h-5" />
        </div>

      {/* Playing Indicator / Play Button */}
      <div className="relative w-9 h-9 sm:w-10 sm:h-10 shrink-0">
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
      <div className="flex-1 min-w-0 overflow-hidden">
        <p className={`font-medium truncate text-sm sm:text-base ${isPlaying ? 'text-primary' : ''}`}>
          {song.title}
        </p>
        <div className="flex items-center gap-1.5 sm:gap-2 text-xs text-muted-foreground mt-0.5 flex-wrap">
          <span className="flex items-center gap-1 shrink-0">
            {getSourceIcon(song.source)}
            <span className="hidden sm:inline">{song.source}</span>
          </span>
          <span className="hidden sm:inline">•</span>
          <span className="shrink-0">{formatDuration(song.duration)}</span>
          {song.last_played_at && (
            <>
              <span className="hidden sm:inline">•</span>
              <span className="text-green-600 dark:text-green-400 shrink-0">Đã phát</span>
            </>
          )}
        </div>
      </div>

      {/* Playlist Badge with Dropdown */}
      {playlists.length > 0 && (
        <div className="relative shrink-0">
          <button
            onClick={() => setShowPlaylistMenu(!showPlaylistMenu)}
            className={`flex items-center gap-1 px-1.5 sm:px-2 py-1 rounded-md text-xs font-medium transition-colors ${
              song.playlist_id
                ? 'bg-green-500/20 text-green-600 dark:text-green-400'
                : 'bg-muted text-muted-foreground'
            }`}
          >
            <ListMusic className="w-3 h-3" />
            <span className="hidden sm:inline">
              {song.playlist_id
                ? playlists.find(p => p.id === song.playlist_id)?.name || 'Playlist'
                : 'Chung'}
            </span>
            <ChevronDown className="w-3 h-3" />
          </button>

          <AnimatePresence>
            {showPlaylistMenu && (
              <motion.div
                initial={{ opacity: 0, y: -5, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -5, scale: 0.95 }}
                className="absolute right-0 top-full mt-1 z-50 bg-card border border-border rounded-lg shadow-lg overflow-hidden min-w-[140px]"
              >
                <button
                  onClick={() => {
                    onPlaylistAssign(null);
                    setShowPlaylistMenu(false);
                  }}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors ${
                    !song.playlist_id ? 'bg-primary/10' : ''
                  }`}
                >
                  Chung
                  {!song.playlist_id && <span className="ml-auto text-primary">✓</span>}
                </button>
                {playlists.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      onPlaylistAssign(p.id);
                      setShowPlaylistMenu(false);
                    }}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors ${
                      song.playlist_id === p.id ? 'bg-primary/10' : ''
                    }`}
                  >
                    <ListMusic className="w-4 h-4 text-green-500" />
                    {p.name}
                    {song.playlist_id === p.id && <span className="ml-auto text-primary">✓</span>}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Delete After Play Badge - Hidden on mobile, show icon only */}
      {song.delete_after_play && (
        <div className="flex items-center gap-1 px-1.5 sm:px-2 py-1 rounded-md text-xs font-medium bg-red-500/20 text-red-600 dark:text-red-400 shrink-0">
          <Trash className="w-3 h-3" />
          <span className="hidden sm:inline">Xóa sau phát</span>
        </div>
      )}

      {/* Actions - Always visible on mobile */}
      <div className="flex items-center gap-0.5 sm:gap-1 shrink-0">
        <AnimatePresence>
          {(showActions || isDeleting || true) && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-0.5 sm:gap-1"
            >
              <Button
                variant="ghost"
                size="icon"
                onClick={onToggleDeleteAfterPlay}
                title={song.delete_after_play ? 'Tắt xóa sau khi phát' : 'Xóa sau khi phát'}
                className={`h-7 w-7 sm:h-8 sm:w-8 ${
                  song.delete_after_play 
                    ? 'text-red-500 hover:text-red-600 hover:bg-red-500/10' 
                    : 'text-muted-foreground hover:text-red-500 hover:bg-red-500/10'
                }`}
              >
                <Trash className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={onDelete}
                disabled={isDeleting}
                className="h-7 w-7 sm:h-8 sm:w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
              >
                {isDeleting ? (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  >
                    <Clock className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                  </motion.div>
                ) : (
                  <Trash2 className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                )}
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      </motion.div>
    </Reorder.Item>
  );
}
