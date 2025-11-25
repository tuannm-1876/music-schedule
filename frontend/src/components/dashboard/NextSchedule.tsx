import { motion } from 'framer-motion';
import { Clock, Music } from 'lucide-react';
import { useSocket } from '@/contexts/SocketContext';
import { Card } from '@/components/ui';

export function NextSchedule() {
  const { nextSchedule } = useSocket();

  if (!nextSchedule) {
    return (
      <Card className="p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
            <Clock className="w-5 h-5 text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">
              Lịch phát tiếp theo
            </p>
            <p className="text-xs text-muted-foreground/70">
              Chưa có lịch nào được đặt
            </p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
    >
      <Card className="p-4 bg-gradient-to-br from-primary/10 to-purple-500/10 border-primary/20">
        <div className="flex items-center gap-3">
          <motion.div
            animate={{ scale: [1, 1.05, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center shadow-lg"
          >
            <Clock className="w-6 h-6 text-white" />
          </motion.div>
          
          <div className="flex-1 min-w-0">
            <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">
              Phát tiếp theo
            </p>
            <p className="font-bold text-2xl text-primary">
              {nextSchedule.time}
            </p>
            <div className="flex items-center gap-1.5 mt-1">
              <Music className="w-3 h-3 text-muted-foreground" />
              <p className="text-sm text-muted-foreground truncate">
                {nextSchedule.song_title}
              </p>
            </div>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
