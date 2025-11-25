import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  LogOut, 
  Moon, 
  Sun, 
  Music,
  Wifi,
  WifiOff
} from 'lucide-react';
import { useSocket } from '@/contexts/SocketContext';
import { useTheme } from '@/contexts/ThemeContext';
import { Button } from '@/components/ui';
import { Player } from '@/components/player';
import { Playlist } from '@/components/playlist';
import { ScheduleManager } from '@/components/schedule';
import { 
  DiskUsage, 
  AddMusic, 
  DownloadProgress, 
  NextSchedule,
  YtdlpInfo
} from '@/components/dashboard';
import { authApi } from '@/lib/api';
import type { DiskUsage as DiskUsageType, InitialState } from '@/types';

interface DashboardProps {
  username: string;
  onLogout: () => void;
}

export function Dashboard({ username, onLogout }: DashboardProps) {
  const { isConnected, downloadState } = useSocket();
  const { theme, toggleTheme } = useTheme();
  const [diskUsage, setDiskUsage] = useState<DiskUsageType | null>(null);
  const [ytdlpVersion, setYtdlpVersion] = useState('');

  useEffect(() => {
    const loadSystemInfo = async () => {
      try {
        const response = await authApi.getInitialState();
        const data: InitialState = response.data;
        setDiskUsage(data.disk_usage);
        setYtdlpVersion(data.ytdlp_version);
      } catch (error) {
        console.error('Failed to load system info:', error);
      }
    };

    loadSystemInfo();
  }, []);

  return (
    <div className="min-h-screen bg-background pb-24">
      {/* Header */}
      <motion.header
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="sticky top-0 z-30 glass border-b border-border"
      >
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center">
                <Music className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="font-bold text-lg">Music Scheduler</h1>
                <p className="text-xs text-muted-foreground">
                  Xin chào, {username}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Connection Status */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted text-sm">
                {isConnected ? (
                  <>
                    <Wifi className="w-4 h-4 text-green-500" />
                    <span className="text-green-600 dark:text-green-400">Đã kết nối</span>
                  </>
                ) : (
                  <>
                    <WifiOff className="w-4 h-4 text-red-500" />
                    <span className="text-red-600 dark:text-red-400">Mất kết nối</span>
                  </>
                )}
              </div>

              {/* Theme Toggle */}
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleTheme}
                className="rounded-full"
              >
                {theme === 'dark' ? (
                  <Sun className="w-5 h-5" />
                ) : (
                  <Moon className="w-5 h-5" />
                )}
              </Button>

              {/* Logout */}
              <Button
                variant="ghost"
                size="icon"
                onClick={onLogout}
                className="rounded-full text-muted-foreground hover:text-destructive"
              >
                <LogOut className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      </motion.header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Download Progress (shows when active) */}
            {downloadState.active && <DownloadProgress />}

            {/* Playlist */}
            <Playlist />
          </div>

          {/* Right Column - Sidebar */}
          <div className="space-y-6">
            {/* Next Schedule */}
            <NextSchedule />

            {/* Add Music */}
            <AddMusic />

            {/* Schedule Manager */}
            <ScheduleManager />

            {/* System Info */}
            {diskUsage && <DiskUsage diskUsage={diskUsage} onRefresh={setDiskUsage} />}
            
            {/* yt-dlp Info */}
            <YtdlpInfo 
              version={ytdlpVersion} 
              onVersionUpdate={setYtdlpVersion} 
            />
          </div>
        </div>
      </main>

      {/* Player (Fixed Bottom) */}
      <Player />
    </div>
  );
}
