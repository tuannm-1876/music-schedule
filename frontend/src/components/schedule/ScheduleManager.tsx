import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Calendar, 
  Clock, 
  Plus, 
  Trash2, 
  ChevronDown,
  ChevronUp,
  Loader2,
  Zap,
  ListMusic,
  Volume2,
  PlaySquare
} from 'lucide-react';
import { useSocket } from '@/contexts/SocketContext';
import { useToast } from '@/contexts/ToastContext';
import { Button, Card, Input, Switch, Slider } from '@/components/ui';
import { scheduleApi } from '@/lib/api';
import { getWeekdayLabel, WEEKDAYS } from '@/lib/utils';
import type { Schedule } from '@/types';

export function ScheduleManager() {
  const { schedules, setSchedules, playlists } = useSocket();
  const { addToast } = useToast();
  const [isExpanded, setIsExpanded] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [togglingPlayAllId, setTogglingPlayAllId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Form state
  const [time, setTime] = useState('08:00');
  const [oneTime, setOneTime] = useState(false);
  const [volume, setVolume] = useState(100);
  const [playlistId, setPlaylistId] = useState<number | null>(null);
  const [playAll, setPlayAll] = useState(false);
  const [selectedDays, setSelectedDays] = useState<Record<string, boolean>>({
    monday: true,
    tuesday: true,
    wednesday: true,
    thursday: true,
    friday: true,
    saturday: false,
    sunday: false,
  });

  const handleAddSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const hasSelectedDay = Object.values(selectedDays).some((v) => v);
    if (!hasSelectedDay) {
      addToast('warning', 'Vui lòng chọn ít nhất một ngày');
      return;
    }

    setIsAdding(true);
    try {
      const response = await scheduleApi.add({
        time,
        one_time: oneTime,
        volume,
        playlist_id: playlistId,
        play_all: playAll,
        monday: selectedDays.monday,
        tuesday: selectedDays.tuesday,
        wednesday: selectedDays.wednesday,
        thursday: selectedDays.thursday,
        friday: selectedDays.friday,
        saturday: selectedDays.saturday,
        sunday: selectedDays.sunday,
      });
      
      setSchedules((prev) => [...prev, response.data]);
      addToast('success', 'Đã thêm lịch phát mới');
      setShowAddForm(false);
      
      // Reset form
      setTime('08:00');
      setOneTime(false);
      setVolume(100);
      setPlaylistId(null);
      setPlayAll(false);
      setSelectedDays({
        monday: true,
        tuesday: true,
        wednesday: true,
        thursday: true,
        friday: true,
        saturday: false,
        sunday: false,
      });
    } catch (error) {
      console.error('Failed to add schedule:', error);
      addToast('error', 'Không thể thêm lịch phát');
    } finally {
      setIsAdding(false);
    }
  };

  const handleToggle = async (scheduleId: number) => {
    setTogglingId(scheduleId);
    try {
      const response = await scheduleApi.toggle(scheduleId);
      setSchedules((prev) =>
        prev.map((s) =>
          s.id === scheduleId ? { ...s, is_active: response.data.is_active } : s
        )
      );
    } catch (error) {
      console.error('Failed to toggle schedule:', error);
      addToast('error', 'Không thể thay đổi trạng thái');
    } finally {
      setTogglingId(null);
    }
  };

  const handleDelete = async (scheduleId: number) => {
    setDeletingId(scheduleId);
    try {
      await scheduleApi.delete(scheduleId);
      setSchedules((prev) => prev.filter((s) => s.id !== scheduleId));
      addToast('success', 'Đã xóa lịch phát');
    } catch (error) {
      console.error('Failed to delete schedule:', error);
      addToast('error', 'Không thể xóa lịch phát');
    } finally {
      setDeletingId(null);
    }
  };

  const handleTogglePlayAll = async (scheduleId: number) => {
    setTogglingPlayAllId(scheduleId);
    try {
      const response = await scheduleApi.togglePlayAll(scheduleId);
      setSchedules((prev) =>
        prev.map((s) =>
          s.id === scheduleId ? { ...s, play_all: response.data.play_all } : s
        )
      );
    } catch (error) {
      console.error('Failed to toggle play_all:', error);
      addToast('error', 'Không thể thay đổi chế độ phát');
    } finally {
      setTogglingPlayAllId(null);
    }
  };

  const toggleDay = (day: string) => {
    setSelectedDays((prev) => ({ ...prev, [day]: !prev[day] }));
  };



  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500/20 to-red-500/20 flex items-center justify-center">
            <Calendar className="w-5 h-5 text-orange-500" />
          </div>
          <div className="text-left">
            <h2 className="font-semibold">Lịch phát nhạc</h2>
            <p className="text-sm text-muted-foreground">
              {schedules.length} lịch đã đặt
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
            <div className="px-4 pb-4 space-y-2">
              {/* Schedule List */}
              {schedules.map((schedule) => {
                return (
                <motion.div
                  key={schedule.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`rounded-xl border overflow-hidden transition-all duration-200 ${
                    schedule.is_active
                      ? 'border-primary/25 shadow-sm shadow-primary/10'
                      : 'border-border opacity-70'
                  }`}
                >
                  {/* Left accent bar + content */}
                  <div className="flex">
                    {/* Accent bar */}
                    <div className={`w-1 shrink-0 ${schedule.is_active ? 'bg-primary' : 'bg-muted-foreground/30'}`} />

                    {/* Main content */}
                    <div className="flex-1 p-3 space-y-2">
                      {/* Top row: time + badges + controls */}
                      <div className="flex items-center justify-between gap-2">
                        {/* Left: time + badges */}
                        <div className="flex items-center gap-2 flex-wrap min-w-0">
                          <div className="flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                            <span className={`font-mono font-bold text-xl leading-none ${
                              schedule.is_active ? 'text-foreground' : 'text-muted-foreground'
                            }`}>
                              {schedule.time}
                            </span>
                          </div>

                          {schedule.one_time && (
                            <span className="px-2 py-0.5 text-xs rounded-full bg-amber-500/20 text-amber-500 dark:text-amber-400 border border-amber-500/20 flex items-center gap-1 shrink-0">
                              <Zap className="w-3 h-3" />
                              Một lần
                            </span>
                          )}

                          {schedule.playlist_id ? (
                            <span className="px-2 py-0.5 text-xs rounded-full bg-orange-500/15 text-orange-600 dark:text-orange-400 border border-orange-500/20 flex items-center gap-1 shrink-0">
                              <ListMusic className="w-3 h-3" />
                              {playlists.find(p => p.id === schedule.playlist_id)?.name || 'Playlist'}
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 text-xs rounded-full bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/20 flex items-center gap-1 shrink-0">
                              <ListMusic className="w-3 h-3" />
                              Nhạc
                            </span>
                          )}

                          {schedule.play_all && schedule.playlist_id && (
                            <span className="px-2 py-0.5 text-xs rounded-full bg-purple-500/15 text-purple-600 dark:text-purple-400 border border-purple-500/20 flex items-center gap-1 shrink-0">
                              <PlaySquare className="w-3 h-3" />
                              Toàn bộ
                            </span>
                          )}

                          <span className="px-2 py-0.5 text-xs rounded-full bg-muted text-muted-foreground border border-border flex items-center gap-1 shrink-0">
                            <Volume2 className="w-3 h-3" />
                            {schedule.volume || 100}%
                          </span>
                        </div>

                        {/* Right: play-all toggle + enabled toggle + delete */}
                        <div className="flex items-center gap-1.5 shrink-0">
                          {schedule.playlist_id && (
                            <Button
                              variant="ghost"
                              size="icon"
                              title={schedule.play_all ? 'Đang phát toàn bộ playlist – nhấn để chỉ phát 1 bài' : 'Chỉ phát 1 bài – nhấn để phát toàn bộ playlist'}
                              onClick={() => handleTogglePlayAll(schedule.id)}
                              disabled={togglingPlayAllId === schedule.id}
                              className={`h-8 w-8 transition-colors ${
                                schedule.play_all
                                  ? 'text-purple-500 bg-purple-500/10 hover:bg-purple-500/20'
                                  : 'text-muted-foreground hover:text-purple-500 hover:bg-purple-500/10'
                              }`}
                            >
                              {togglingPlayAllId === schedule.id ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <PlaySquare className="w-4 h-4" />
                              )}
                            </Button>
                          )}
                          <Switch
                            checked={schedule.is_active}
                            onCheckedChange={() => handleToggle(schedule.id)}
                            disabled={togglingId === schedule.id}
                          />
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDelete(schedule.id)}
                            disabled={deletingId === schedule.id}
                            className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                          >
                            {deletingId === schedule.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </Button>
                        </div>
                      </div>

                      {/* Bottom row: weekday pills */}
                      <div className="flex gap-1 flex-wrap">
                        {WEEKDAYS.map((day) => (
                          <span
                            key={day}
                            className={`px-2 py-0.5 text-xs rounded-full font-medium transition-colors ${
                              schedule[day as keyof Schedule]
                                ? 'bg-primary text-primary-foreground'
                                : 'bg-muted/60 text-muted-foreground/50'
                            }`}
                          >
                            {getWeekdayLabel(day)}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </motion.div>
              );
              })}

              {schedules.length === 0 && !showAddForm && (
                <div className="py-6 text-center">
                  <Calendar className="w-10 h-10 mx-auto text-muted-foreground/50 mb-2" />
                  <p className="text-sm text-muted-foreground">
                    Chưa có lịch phát nào
                  </p>
                </div>
              )}

              {/* Add Schedule Form */}
              <AnimatePresence>
                {showAddForm && (
                  <motion.form
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    onSubmit={handleAddSchedule}
                    className="p-4 rounded-xl border border-primary/30 bg-primary/5 space-y-4"
                  >
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-muted-foreground" />
                      <Input
                        type="time"
                        value={time}
                        onChange={(e) => setTime(e.target.value)}
                        className="w-32"
                        required
                      />
                    </div>

                    {/* One-time option */}
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={oneTime}
                        onChange={(e) => setOneTime(e.target.checked)}
                        className="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary"
                      />
                      <Zap className="w-4 h-4 text-amber-500" />
                      <span className="text-sm">Chỉ phát một lần (tự tắt sau khi phát)</span>
                    </label>

                    {/* Volume Control */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-sm font-medium flex items-center gap-2">
                          <Volume2 className="w-4 h-4" />
                          Âm lượng:
                        </label>
                        <span className="text-sm font-semibold text-primary">{volume}%</span>
                      </div>
                      <Slider
                        value={volume}
                        onValueChange={(val) => setVolume(val)}
                        min={0}
                        max={100}
                        step={5}
                        className="w-full"
                      />
                    </div>

                    {/* Playlist Selector */}
                    <div className="space-y-2">
                      <label className="text-sm font-medium flex items-center gap-2">
                        <ListMusic className="w-4 h-4" />
                        Playlist:
                      </label>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => { setPlaylistId(null); setPlayAll(false); }}
                          className={`px-3 py-1.5 text-sm rounded-lg transition-all ${
                            playlistId === null
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-muted hover:bg-muted/80'
                          }`}
                        >
                          Tất cả
                        </button>
                        {playlists.map((p) => (
                          <button
                            key={p.id}
                            type="button"
                            onClick={() => setPlaylistId(p.id)}
                            className={`px-3 py-1.5 text-sm rounded-lg transition-all ${
                              playlistId === p.id
                                ? 'bg-green-500 text-white'
                                : 'bg-muted hover:bg-muted/80'
                            }`}
                          >
                            {p.name}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Play All option - only shown when a playlist is selected */}
                    {playlistId !== null && (
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={playAll}
                          onChange={(e) => setPlayAll(e.target.checked)}
                          className="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                        <PlaySquare className="w-4 h-4 text-purple-500" />
                        <span className="text-sm">Phát toàn bộ bài hát trong playlist theo thứ tự</span>
                      </label>
                    )}

                    {/* Weekday Selector */}
                    <div className="flex flex-wrap gap-1">
                      {WEEKDAYS.map((day) => (
                        <button
                          key={day}
                          type="button"
                          onClick={() => toggleDay(day)}
                          className={`px-3 py-1.5 text-xs rounded-full transition-all ${
                            selectedDays[day]
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-muted text-muted-foreground hover:bg-muted/80'
                          }`}
                        >
                          {getWeekdayLabel(day)}
                        </button>
                      ))}
                    </div>

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
                            Đang thêm...
                          </>
                        ) : (
                          'Thêm lịch'
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
                <button
                  onClick={() => setShowAddForm(true)}
                  className="w-full mt-1 py-2.5 flex items-center justify-center gap-2 rounded-xl border border-dashed border-border text-sm text-muted-foreground hover:text-foreground hover:border-primary/50 hover:bg-primary/5 transition-all duration-200"
                >
                  <Plus className="w-4 h-4" />
                  Thêm lịch phát
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}
