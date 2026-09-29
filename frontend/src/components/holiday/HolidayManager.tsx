import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CalendarOff,
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  Loader2,
} from 'lucide-react';
import { useSocket } from '@/contexts/SocketContext';
import { useToast } from '@/contexts/ToastContext';
import { Button, Card, Input } from '@/components/ui';
import { holidayApi } from '@/lib/api';

export function HolidayManager() {
  const { holidays, setHolidays } = useSocket();
  const { addToast } = useToast();
  const [isExpanded, setIsExpanded] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Form state
  const [date, setDate] = useState('');
  const [name, setName] = useState('');

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!date || !name.trim()) {
      addToast('warning', 'Vui lòng nhập ngày và tên ngày nghỉ');
      return;
    }

    setIsAdding(true);
    try {
      const response = await holidayApi.add(date, name.trim());
      setHolidays((prev) => [...prev, response.data].sort((a, b) => a.date.localeCompare(b.date)));
      addToast('success', 'Đã thêm ngày nghỉ');
      setShowAddForm(false);
      setDate('');
      setName('');
    } catch (error: any) {
      const msg = error.response?.data?.message || 'Không thể thêm ngày nghỉ';
      addToast('error', msg);
    } finally {
      setIsAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    setDeletingId(id);
    try {
      await holidayApi.delete(id);
      setHolidays((prev) => prev.filter((h) => h.id !== id));
      addToast('success', 'Đã xóa ngày nghỉ');
    } catch {
      addToast('error', 'Không thể xóa ngày nghỉ');
    } finally {
      setDeletingId(null);
    }
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('vi-VN', {
      weekday: 'short',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  const isUpcoming = (dateStr: string) => {
    const today = new Date().toISOString().split('T')[0];
    return dateStr >= today;
  };

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-red-500/20 to-pink-500/20 flex items-center justify-center">
            <CalendarOff className="w-5 h-5 text-red-500" />
          </div>
          <div className="text-left">
            <h2 className="font-semibold">Ngày nghỉ</h2>
            <p className="text-sm text-muted-foreground">
              {holidays.length} ngày đã đặt
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
              {/* Holiday List */}
              {holidays.map((holiday) => (
                <motion.div
                  key={holiday.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`p-3 rounded-lg border transition-colors ${
                    isUpcoming(holiday.date)
                      ? 'bg-red-500/5 border-red-500/20'
                      : 'bg-muted/50 border-border opacity-60'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{holiday.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {formatDate(holiday.date)}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(holiday.id)}
                      disabled={deletingId === holiday.id}
                      className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10 shrink-0"
                    >
                      {deletingId === holiday.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                </motion.div>
              ))}

              {holidays.length === 0 && !showAddForm && (
                <div className="py-6 text-center">
                  <CalendarOff className="w-10 h-10 mx-auto text-muted-foreground/50 mb-2" />
                  <p className="text-sm text-muted-foreground">
                    Chưa có ngày nghỉ nào
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
                    className="p-3 rounded-lg border border-dashed border-red-500/50 bg-red-500/5 space-y-3"
                  >
                    <Input
                      type="date"
                      value={date}
                      onChange={(e) => setDate(e.target.value)}
                      required
                    />
                    <Input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Tên ngày nghỉ (VD: Tết Nguyên Đán)"
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
                            Đang thêm...
                          </>
                        ) : (
                          'Thêm ngày nghỉ'
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
                  Thêm ngày nghỉ
                </Button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}
