import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://localhost:5000',
        ws: true,
      },
      '/login': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/logout': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/add-music': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/upload-music': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/play': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/seek': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/delete-song': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/add-schedule': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/toggle-schedule': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/delete-schedule': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/set-volume': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/update-song-order': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/reset-playlist-order': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/cancel-download': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/update-ytdlp': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/get-disk-usage': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/music': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../static/react',
    emptyOutDir: true,
  },
})
