import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { assertBuildMode } from "./src/config.js";

export default defineConfig(({ command, mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), ""), ...process.env };
  assertBuildMode(command, env.VITE_APP_MODE, env.NODE_ENV);
  return {
    plugins: [react()],
    build: { sourcemap: false },
    test: {
      environment: "jsdom",
      setupFiles: ["./tests/setup.js"],
      include: ["tests/**/*.test.{js,jsx}"],
      reporters: ["default", "junit"],
      outputFile: { junit: "../../report/stage3-vitest.xml" },
    },
  };
});
