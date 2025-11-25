import axios from 'axios';

const api = axios.create({
  baseURL: '',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;

// API functions
export const authApi = {
  login: (username: string, password: string) =>
    api.post('/api/login', { username, password }),
  logout: () => api.get('/api/logout'),
  getInitialState: () => api.get('/api/initial-state'),
};

export const musicApi = {
  addFromYoutube: (url: string) => api.post('/add-music', { url }),
  uploadFile: (formData: FormData) =>
    api.post('/upload-music', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  play: (songId: number) => api.post(`/play/${songId}`),
  seek: (position: number) => api.post('/seek', { position }),
  deleteSong: (songId: number) => api.delete(`/delete-song/${songId}`),
  updateOrder: (songIds: number[]) =>
    api.post('/update-song-order', { song_ids: songIds }),
  resetOrder: () => api.post('/reset-playlist-order'),
  setVolume: (volume: number) => api.post('/set-volume', { volume }),
  cancelDownload: () => api.post('/cancel-download'),
};

export const scheduleApi = {
  add: (data: {
    time: string;
    one_time?: boolean;
    monday: boolean;
    tuesday: boolean;
    wednesday: boolean;
    thursday: boolean;
    friday: boolean;
    saturday: boolean;
    sunday: boolean;
  }) => api.post('/add-schedule', data),
  toggle: (scheduleId: number) => api.post(`/toggle-schedule/${scheduleId}`),
  delete: (scheduleId: number) => api.delete(`/delete-schedule/${scheduleId}`),
};

export const systemApi = {
  getDiskUsage: () => api.get('/get-disk-usage'),
  updateYtdlp: () => api.post('/update-ytdlp'),
};
