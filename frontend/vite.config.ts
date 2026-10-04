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
      },
      '/health': {
        target: backendOrigin,
        changeOrigin: true,
      },
    },
  },
})
