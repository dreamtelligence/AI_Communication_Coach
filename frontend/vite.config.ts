import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
    },
  },
  server: {
    proxy: {
      '/api': process.env.VITE_API_PROXY_TARGET || 'https://aliundmaggy--asr-coaching-analysis-fastapi-app.modal.run'
    }
  }
})
