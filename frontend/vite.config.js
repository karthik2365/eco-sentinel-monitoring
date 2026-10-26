import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true,
        secure: false
      },
      '/reports': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true
      },
      '/static': {
        target: 'http://127.0.0.1:5050',
        changeOrigin: true
      },
      '/socket.io': {
        target: 'http://127.0.0.1:5050',
        ws: true
      }
    }
  }
});
