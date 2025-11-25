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
  Zap
} from 'lucide-react';
import { useSocket } from '@/contexts/SocketContext';
import { useToast } from '@/contexts/ToastContext';
import { Button, Card, Input, Switch } from '@/components/ui';
import { scheduleApi } from '@/lib/api';
import { getWeekdayLabel, WEEKDAYS } from '@/lib/utils';
import type { Schedule } from '@/types';

export function ScheduleManager() {
  const { schedules, setSchedules } = useSocket();
  const { addToast } = useToast();
  const [isExpanded, setIsExpanded] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Form state
  const [time, setTime] = useState('08:00');
  const [oneTime, setOneTime] = useState(false);
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
            <div className="px-4 pb-4 space-y-3">
              {/* Schedule List */}
              {schedules.map((schedule) => (
                <motion.div
                  key={schedule.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`p-3 rounded-lg border transition-colors ${
                    schedule.is_active
                      ? 'bg-primary/5 border-primary/20'
                      : 'bg-muted/50 border-border'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4 text-muted-foreground" />
                        <span className="font-mono font-semibold text-lg">
                          {schedule.time}
                        </span>
                        {schedule.one_time && (
                          <span className="px-2 py-0.5 text-xs rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400 flex items-center gap-1">
                            <Zap className="w-3 h-3" />
                            Một lần
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
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

                  {/* Active Days */}
                  <div className="flex gap-1 mt-2">
                    {WEEKDAYS.map((day) => (
                      <span
                        key={day}
                        className={`px-2 py-0.5 text-xs rounded-full transition-colors ${
                          schedule[day as keyof Schedule]
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground'
                        }`}
                      >
                        {getWeekdayLabel(day)}
                      </span>
                    ))}
                  </div>
                </motion.div>
              ))}

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
                    className="p-3 rounded-lg border border-dashed border-primary/50 bg-primary/5 space-y-3"
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
                <Button
                  variant="outline"
                  className="w-full border-dashed"
                  onClick={() => setShowAddForm(true)}
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Thêm lịch phát
                </Button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}
