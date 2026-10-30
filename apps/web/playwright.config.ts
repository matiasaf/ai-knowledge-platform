import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { defineConfig, devices } from "@playwright/test";

// Dedicated ports and a throwaway data directory, so E2E runs never touch the
// documents or index of a developer's `make api` / `make web` session.
const API_PORT = 8100;
const WEB_PORT = 3100;
const dataDir = mkdtempSync(join(tmpdir(), "akp-e2e-"));

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `uv run uvicorn ai_knowledge_platform.main:app --port ${API_PORT}`,
      cwd: "../../services/api",
      url: `http://localhost:${API_PORT}/health`,
      reuseExistingServer: false,
      env: {
        AKP_DATA_DIR: dataDir,
        AKP_CORS_ALLOW_ORIGINS: JSON.stringify([`http://localhost:${WEB_PORT}`]),
        // Empty credentials: the suite covers the provider-free product.
        AKP_OPENAI_API_KEY: "",
        AKP_OPENAI_MODEL: "",
      },
    },
    {
      command: `npm run dev -- --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      env: { NEXT_PUBLIC_API_BASE_URL: `http://localhost:${API_PORT}` },
    },
  ],
});
