import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL(".", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    // Explicit imports over globals: a reader can tell where `describe` comes from,
    // and tsconfig needs no ambient type entry.
    globals: false,
    include: ["**/*.test.ts", "**/*.test.tsx"],
  },
});
