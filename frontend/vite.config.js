import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: true,
    host: '0.0.0.0',
    port: 8090,
    proxy: {
      '/api': 'http://localhost:8091',
      '/media': 'http://localhost:8091'
    }
  },
  build: {
    outDir: 'dist'
  }
})
