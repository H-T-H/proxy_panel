import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";


export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.js",
    exclude: ["tests/e2e/**", "node_modules/**", "dist/**"]
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/sub": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  }
});
