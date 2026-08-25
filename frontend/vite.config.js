import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import wasm from 'vite-plugin-wasm'

export default defineConfig({
  plugins: [vue(), wasm()],
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
