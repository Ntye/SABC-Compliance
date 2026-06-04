import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://backend:3000',
        rewrite: (path) => path.replace(/^\/api/, ''),
        ws: true,           // covers WebSocket job-log streaming too
        changeOrigin: true,
      },
    },
  },
})
