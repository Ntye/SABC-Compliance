import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'

// In the dev container a self-signed cert is generated into /certs on launch
// (see docker-compose.dev.yml). When present, serve the dev server over HTTPS
// so the platform is https end-to-end on launch. The existsSync guard keeps
// the production `vite build` (which has no /certs) unaffected.
const CERT = '/certs/server.crt'
const KEY = '/certs/server.key'
const https =
  fs.existsSync(CERT) && fs.existsSync(KEY)
    ? { cert: fs.readFileSync(CERT), key: fs.readFileSync(KEY) }
    : undefined

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    https,
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
