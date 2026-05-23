import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/query': 'http://localhost:8002',
      '/approve-edge': 'http://localhost:8002',
      '/feedback': 'http://localhost:8002',
      '/traces': 'http://localhost:8002',
      '/health': 'http://localhost:8002',
      '/benchmark': 'http://localhost:8002',
      '/ws': { target: 'ws://localhost:8002', ws: true },
    },
  },
})
