/// <reference types="vitest" />
import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    return {
      base: '/',
      publicDir: 'public',
      server: {
        port: 3000,
        host: '0.0.0.0',
      },
      plugins: [react()],
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      },
      build: {
        outDir: 'dist',
        emptyOutDir: true,
        chunkSizeWarningLimit: 600, // Raise slightly since charity data is large
        rollupOptions: {
          output: {
            manualChunks: (id): string | undefined => {
              // Node modules chunking
              if (id.includes('node_modules')) {
                // React core
                if (id.includes('react-dom') || id.includes('react-router') || id.includes('/react/')) {
                  return 'vendor';
                }
                // Firebase
                if (id.includes('firebase')) {
                  return 'firebase';
                }
                // Charts - must be with vendor since recharts uses React.forwardRef
                if (id.includes('recharts') || id.includes('d3-') || id.includes('victory')) {
                  return 'vendor';
                }
                // Icons
                if (id.includes('lucide-react')) {
                  return 'icons';
                }
              }
              // Charity data - largest chunk, split it out
              if (id.includes('src/data/charities')) {
                return 'charity-data';
              }
              return undefined;
            },
          },
        },
      },
      test: {
        environment: 'jsdom',
        globals: true,
        setupFiles: [],
      },
    };
});
