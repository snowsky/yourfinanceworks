import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import path from "path"

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
          vendor: ['react', 'react-dom', 'react-router-dom', '@tanstack/react-query', 'react-i18next', 'i18next'],
          radix_ui: ['@radix-ui/react-accordion', '@radix-ui/react-alert-dialog', '@radix-ui/react-avatar', '@radix-ui/react-checkbox', '@radix-ui/react-slot', 'class-variance-authority', 'cmdk', 'sonner'],
          forms: ['react-hook-form', '@hookform/resolvers', 'zod'],
          charts: ['recharts'],
          pdf: ['@react-pdf/renderer'],
          icons: ['lucide-react'],
          utils: ['date-fns', 'date-fns-tz', 'clsx', 'tailwind-merge']
        }
      }
    },
    chunkSizeWarningLimit: 1000
  },
  server: {
    port: 8080,
    host: '0.0.0.0',
    allowedHosts: ['ui', 'localhost', '127.0.0.1', '0.0.0.0', 'demo.yourfinanceworks.com'],
    hmr: {
      clientPort: 443, // Assuming they use HTTPS on the demo site
    },
    watch: {
      usePolling: true,
      interval: 1000,
      ignored: ['**/node_modules/**', '**/.git/**'],
    },
  },
})