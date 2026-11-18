import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = process.env.API_URL ?? "http://localhost:4000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/link-analysis": api, "/health": api, "/docs": api, "/openapi.json": api },
  },
  build: { outDir: "dist", sourcemap: false },
});
