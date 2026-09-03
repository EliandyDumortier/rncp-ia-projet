import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { coverageConfigDefaults } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
  build: {
    outDir: "dist",
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
    coverage: {
      provider: "v8",
      // The optional Supabase adapter is tested for safe disabled behavior;
      // the data API remains the canonical, fully covered browser path.
      exclude: [...coverageConfigDefaults.exclude, "src/supabaseClient.ts"],
      thresholds: {
        lines: 44,
        functions: 42,
        branches: 60,
        statements: 44,
      },
    },
  },
});
