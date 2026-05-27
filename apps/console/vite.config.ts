import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  envDir: "../..",
  cacheDir: "../../data/vite-cache",
  plugins: [vue()],
  server: {
    host: "127.0.0.1",
  },
  build: {
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ["echarts/core", "echarts/charts", "echarts/components", "echarts/renderers"],
          vendor: ["vue", "vue-router", "pinia", "gsap"],
        },
      },
    },
  },
});
