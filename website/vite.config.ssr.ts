import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/',
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, '.') } },
  build: {
    ssr: 'entry-server.tsx',
    outDir: 'dist-server',
    emptyOutDir: true,
    rollupOptions: { output: { format: 'esm', entryFileNames: 'entry-server.js' } },
  },
});
