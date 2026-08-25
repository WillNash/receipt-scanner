import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      external: ['heic2any'],
      output: {
        globals: { heic2any: 'heic2any' },
      },
    },
  },
})
