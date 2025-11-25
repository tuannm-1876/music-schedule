import { useState } from 'react';
import { Terminal, RefreshCw, CheckCircle, Loader2 } from 'lucide-react';
import { useToast } from '@/contexts/ToastContext';
import { Card, Button } from '@/components/ui';
import { systemApi } from '@/lib/api';

interface YtdlpInfoProps {
  version: string;
  onVersionUpdate: (version: string) => void;
}

export function YtdlpInfo({ version, onVersionUpdate }: YtdlpInfoProps) {
  const { addToast } = useToast();
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateSuccess, setUpdateSuccess] = useState(false);

  const handleUpdate = async () => {
    setIsUpdating(true);
    setUpdateSuccess(false);
    
    try {
      const response = await systemApi.updateYtdlp();
      onVersionUpdate(response.data.version || version);
      setUpdateSuccess(true);
      addToast('success', 'Đã cập nhật yt-dlp thành công');
      
      setTimeout(() => setUpdateSuccess(false), 3000);
    } catch (error: any) {
      console.error('Failed to update yt-dlp:', error);
      addToast('error', error.response?.data?.error || 'Không thể cập nhật yt-dlp');
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center">
            <Terminal className="w-4 h-4 text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm font-medium">yt-dlp</p>
            <p className="text-xs text-muted-foreground font-mono">
              {version || 'N/A'}
            </p>
          </div>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={handleUpdate}
          disabled={isUpdating}
          className="gap-2"
        >
          {isUpdating ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Đang cập nhật
            </>
          ) : updateSuccess ? (
            <>
              <CheckCircle className="w-3.5 h-3.5 text-green-500" />
              Đã cập nhật
            </>
          ) : (
            <>
              <RefreshCw className="w-3.5 h-3.5" />
              Cập nhật
            </>
          )}
        </Button>
      </div>
    </Card>
  );
}
