import { useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useSocket } from '@/contexts/SocketContext';
import { useToast } from '@/contexts/ToastContext';
import { authApi } from '@/lib/api';
import { LoginPage } from '@/pages/LoginPage';
import { Dashboard } from '@/pages/Dashboard';
import { Spinner } from '@/components/ui';
import type { InitialState } from '@/types';

function App() {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState('');
  const { setSongs, setSchedules, setPlaybackState, setNextSchedule } = useSocket();
  const { addToast } = useToast();

  useEffect(() => {
    const loadInitialState = async () => {
      try {
        const response = await authApi.getInitialState();
        const data: InitialState = response.data;
        
        setIsAuthenticated(data.is_authenticated);
        setUsername(data.username);
        
        if (data.is_authenticated) {
          setSongs(data.songs);
          setSchedules(data.schedules);
          setNextSchedule(data.next_schedule);
          setPlaybackState({
            is_playing: data.is_playing,
            current_song_id: data.current_song_id,
            current_song_title: data.current_song_title,
            position: 0,
            duration: 0,
            volume: data.volume,
          });
        }
      } catch (error) {
        console.error('Failed to load initial state:', error);
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    };

    loadInitialState();
  }, [setSongs, setSchedules, setPlaybackState]);

  const handleLogin = async (loginUsername: string, password: string) => {
    try {
      await authApi.login(loginUsername, password);
      setIsAuthenticated(true);
      setUsername(loginUsername);
      
      // Load initial state after login
      const response = await authApi.getInitialState();
      const data: InitialState = response.data;
      setSongs(data.songs);
      setSchedules(data.schedules);
      setNextSchedule(data.next_schedule);
      setPlaybackState({
        is_playing: data.is_playing,
        current_song_id: data.current_song_id,
        current_song_title: data.current_song_title,
        position: 0,
        duration: 0,
        volume: data.volume,
      });
      
      addToast('success', 'Đăng nhập thành công!');
    } catch (error: any) {
      addToast('error', error.response?.data?.error || 'Đăng nhập thất bại');
      throw error;
    }
  };

  const handleLogout = async () => {
    try {
      await authApi.logout();
      setIsAuthenticated(false);
      setUsername('');
      addToast('info', 'Đã đăng xuất');
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center gap-4"
        >
          <Spinner size="lg" />
          <p className="text-muted-foreground">Đang tải...</p>
        </motion.div>
      </div>
    );
  }

  return (
    <AnimatePresence mode="wait">
      <Routes>
        <Route
          path="/login"
          element={
            isAuthenticated ? (
              <Navigate to="/" replace />
            ) : (
              <LoginPage onLogin={handleLogin} />
            )
          }
        />
        <Route
          path="/*"
          element={
            isAuthenticated ? (
              <Dashboard username={username} onLogout={handleLogout} />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
      </Routes>
    </AnimatePresence>
  );
}

export default App;
