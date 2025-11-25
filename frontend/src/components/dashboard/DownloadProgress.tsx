import { motion } from 'framer-motion';
import { X, Download } from 'lucide-react';
import { useSocket } from '@/contexts/SocketContext';
import { useToast } from '@/contexts/ToastContext';
import { Card, Button, Progress } from '@/components/ui';
import { musicApi } from '@/lib/api';

export function DownloadProgress() {
  const { downloadState } = useSocket();
  const { addToast } = useToast();

  const handleCancel = async () => {
    try {
      await musicApi.cancelDownload();
      addToast('info', 'Đã hủy tải xuống');
    } catch (error) {
      console.error('Failed to cancel download:', error);
      addToast('error', 'Không thể hủy tải xuống');
    }
  };

  if (!downloadState.active) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
    >
      <Card className="p-4 border-primary/50 bg-primary/5">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
            >
              <Download className="w-5 h-5 text-primary" />
            </motion.div>
            <div>
              <p className="font-medium text-sm">Đang tải xuống</p>
              <p className="text-xs text-muted-foreground truncate max-w-[200px]">
                {downloadState.current_file || downloadState.status}
              </p>
            </div>
          </div>
          
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-destructive"
            onClick={handleCancel}
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        <div className="space-y-2">
          <Progress value={downloadState.progress} />
          
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{downloadState.status}</span>
            <span>{Math.round(downloadState.progress)}%</span>
          </div>

          {downloadState.playlist_progress && (
            <p className="text-xs text-center text-muted-foreground">
              Bài {downloadState.playlist_progress.current} / {downloadState.playlist_progress.total}
            </p>
          )}
        </div>

        {downloadState.error && (
          <p className="mt-2 text-xs text-destructive">
            Lỗi: {downloadState.error}
          </p>
        )}
      </Card>
    </motion.div>
  );
}
