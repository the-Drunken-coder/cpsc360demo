import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": loadEnv(mode, ".", "CPSC360_").CPSC360_API_URL || "http://127.0.0.1:8000" },
  },
}));
