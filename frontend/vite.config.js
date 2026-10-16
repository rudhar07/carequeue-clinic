import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` proxies /api to a locally running backend (uvicorn on :8000),
// the same relative-URL contract nginx provides in Docker and Kubernetes.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.js"],
    globals: false,
  },
});
