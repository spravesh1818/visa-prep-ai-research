import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy so the SPA can call the FastAPI backend without CORS config.
const API_TARGET = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8090";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/config": API_TARGET,
      "/voice": API_TARGET,
      "/interview": API_TARGET,
      "/health": API_TARGET,
    },
  },
});
