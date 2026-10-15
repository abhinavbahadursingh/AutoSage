import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backendOrigin = process.env.VITE_BACKEND_ORIGIN ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: backendOrigin,
        changeOrigin: true,
        ws: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes, req) => {
            // Disable buffering for SSE streams so events reach the browser
            // in real-time instead of being buffered until the response ends.
            if (req.url?.includes('/stream')) {
              proxyRes.headers['x-accel-buffering'] = 'no'
              proxyRes.headers['cache-control'] = 'no-cache'
            }
          })
        },
      },
      '/health': {
        target: backendOrigin,
        changeOrigin: true,
      },
    },
  },
})
