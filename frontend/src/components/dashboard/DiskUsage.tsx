import { useState } from 'react';
import { motion } from 'framer-motion';
import { HardDrive, RefreshCw } from 'lucide-react';
import { Card, Button } from '@/components/ui';
import { systemApi } from '@/lib/api';
import type { DiskUsage as DiskUsageType } from '@/types';

interface DiskUsageProps {
  diskUsage: DiskUsageType;
  onRefresh: (data: DiskUsageType) => void;
}

export function DiskUsage({ diskUsage, onRefresh }: DiskUsageProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      const response = await systemApi.getDiskUsage();
      onRefresh(response.data);
    } catch (error) {
      console.error('Failed to refresh disk usage:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  const getProgressColor = (percent: number) => {
    if (percent >= 90) return 'bg-red-500';
    if (percent >= 70) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <HardDrive className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium">Dung lượng</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={handleRefresh}
          disabled={isRefreshing}
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      <div className="space-y-2">
        <div className="h-2 rounded-full bg-muted overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${diskUsage.percent}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className={`h-full rounded-full ${getProgressColor(diskUsage.percent)}`}
          />
        </div>
        
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>
            Đã dùng: {diskUsage.used_formatted}
          </span>
          <span>
            Tổng: {diskUsage.total_formatted}
          </span>
        </div>
        
        <p className="text-xs text-center font-medium">
          {diskUsage.percent.toFixed(1)}% đã sử dụng
        </p>
      </div>
    </Card>
  );
}
