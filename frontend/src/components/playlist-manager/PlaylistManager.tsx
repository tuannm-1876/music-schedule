import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ListMusic,
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  Loader2,
  Music,
} from 'lucide-react';
import { useSocket } from '@/contexts/SocketContext';
import { useToast } from '@/contexts/ToastContext';
import { Button, Card, Input } from '@/components/ui';
import { playlistApi } from '@/lib/api';

export function PlaylistManager() {
  const { playlists, setPlaylists } = useSocket();
  const { addToast } = useToast();
  const [isExpanded, setIsExpanded] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Form state
  const [name, setName] = useState('');

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      addToast('warning', 'Vui lòng nhập tên playlist');
      return;
    }

    setIsAdding(true);
    try {
      const response = await playlistApi.create(name.trim());
      setPlaylists((prev) => [...prev, response.data].sort((a, b) => a.name.localeCompare(b.name)));
      addToast('success', 'Đã tạo playlist mới');
      setShowAddForm(false);
      setName('');
    } catch (error: any) {
      const msg = error.response?.data?.message || 'Không thể tạo playlist';
      addToast('error', msg);
    } finally {
      setIsAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    setDeletingId(id);
    try {
      await playlistApi.delete(id);
      setPlaylists((prev) => prev.filter((p) => p.id !== id));
      addToast('success', 'Đã xóa playlist');
    } catch {
      addToast('error', 'Không thể xóa playlist');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500/20 to-emerald-500/20 flex items-center justify-center">
            <ListMusic className="w-5 h-5 text-green-500" />
          </div>
          <div className="text-left">
            <h2 className="font-semibold">Playlist</h2>
            <p className="text-sm text-muted-foreground">
              {playlists.length} playlist
            </p>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-5 h-5 text-muted-foreground" />
        )}
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-3">
              {/* Playlist List */}
              {playlists.map((playlist) => (
                <motion.div
                  key={playlist.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-3 rounded-lg border bg-green-500/5 border-green-500/20 transition-colors"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <div className="w-8 h-8 rounded-md bg-green-500/20 flex items-center justify-center shrink-0">
                        <Music className="w-4 h-4 text-green-500" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium truncate">{playlist.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {playlist.song_count} bài hát
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(playlist.id)}
                      disabled={deletingId === playlist.id}
                      className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10 shrink-0"
                    >
                      {deletingId === playlist.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                </motion.div>
              ))}

              {playlists.length === 0 && !showAddForm && (
                <div className="py-6 text-center">
                  <ListMusic className="w-10 h-10 mx-auto text-muted-foreground/50 mb-2" />
                  <p className="text-sm text-muted-foreground">
                    Chưa có playlist nào
                  </p>
                </div>
              )}

              {/* Add Form */}
              <AnimatePresence>
                {showAddForm && (
                  <motion.form
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    onSubmit={handleAdd}
                    className="p-3 rounded-lg border border-dashed border-green-500/50 bg-green-500/5 space-y-3"
                  >
                    <Input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Tên playlist (VD: Nhạc buổi sáng)"
                      required
                    />
                    <div className="flex gap-2">
                      <Button
                        type="submit"
                        size="sm"
                        disabled={isAdding}
                        className="flex-1"
                      >
                        {isAdding ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Đang tạo...
                          </>
                        ) : (
                          'Tạo playlist'
                        )}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setShowAddForm(false)}
                      >
                        Hủy
                      </Button>
                    </div>
                  </motion.form>
                )}
              </AnimatePresence>

              {/* Add Button */}
              {!showAddForm && (
                <Button
                  variant="outline"
                  className="w-full border-dashed"
                  onClick={() => setShowAddForm(true)}
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Tạo playlist mới
                </Button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}
