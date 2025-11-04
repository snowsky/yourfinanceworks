import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import path from "path"

// https://vitejs.dev/config/
// monster-humane-currently.ngrok-free.app is for local testing with ngrok only
// need a correct domain for production
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 8080,
    host: '0.0.0.0',
    allowedHosts: ['ui', 'localhost', '127.0.0.1', '0.0.0.0'],
  },
})