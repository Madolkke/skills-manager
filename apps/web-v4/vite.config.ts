import react from "@vitejs/plugin-react";
import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 3030,
  },
  test: {
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
