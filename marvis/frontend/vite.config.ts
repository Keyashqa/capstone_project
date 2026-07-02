import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth':        { target: 'http://localhost:8000', changeOrigin: true },
      '/wallet':      { target: 'http://localhost:8000', changeOrigin: true },
      '/marketplace': { target: 'http://localhost:8000', changeOrigin: true },
      '/owned-skills':{ target: 'http://localhost:8000', changeOrigin: true },
      '/platform':    { target: 'http://localhost:8000', changeOrigin: true },
      '/adk-sessions':{ target: 'http://localhost:8000', changeOrigin: true },
      '/run_sse':     { target: 'http://localhost:8000', changeOrigin: true },
      '/marvis':      { target: 'http://localhost:8000', changeOrigin: true },
      '/health':      { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
