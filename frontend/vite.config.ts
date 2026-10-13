import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development the Django API runs on :8000; Vite proxies to it so cookies
// (session + CSRF) stay same-origin.
const backend = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: { '/api': backend, '/admin': backend, '/static': backend },
  },
})
