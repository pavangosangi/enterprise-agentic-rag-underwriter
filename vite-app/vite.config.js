import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 8086,
    proxy: {
      '/api': {
        target: 'http://app:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/mcp': {
        target: 'http://deepeval-mcp:8083',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/mcp/, ''),
        headers: {
          'Host': '127.0.0.1:8000'
        }
      }
    }
  }
})
