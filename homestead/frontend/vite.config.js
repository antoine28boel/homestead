import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// Relative paths: behind Home Assistant's ingress the page lives under
// /api/hassio_ingress/<token>/, which is only known at run time.
export default defineConfig({
  base: "./",
  plugins: [vue()],
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8099", ws: true },
    },
  },
});
