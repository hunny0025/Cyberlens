import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws/scraper-feed': { target: 'ws://localhost:8000', ws: true },
      '/health': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
