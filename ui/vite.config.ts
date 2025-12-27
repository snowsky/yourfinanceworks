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
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          radix: ['@radix-ui/react-accordion', '@radix-ui/react-alert-dialog', '@radix-ui/react-avatar', '@radix-ui/react-checkbox'],
          router: ['react-router-dom'],
          query: ['@tanstack/react-query'],
          forms: ['react-hook-form', '@hookform/resolvers'],
          charts: ['recharts'],
          pdf: ['@react-pdf/renderer'],
          scanner: ['@ericblade/quagga2'],
          utils: ['date-fns', 'date-fns-tz', 'clsx', 'tailwind-merge'],
          icons: ['lucide-react'],
          ui: ['@radix-ui/react-slot', 'class-variance-authority', 'cmdk', 'sonner']
        }
      }
    },
    chunkSizeWarningLimit: 1000
  },
  server: {
    port: 8080,
    host: '0.0.0.0',
    allowedHosts: ['ui', 'localhost', '127.0.0.1', '0.0.0.0', 'demo.yourfinanceworks.com'],
  },
})