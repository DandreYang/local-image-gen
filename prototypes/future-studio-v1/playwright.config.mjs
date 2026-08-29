import { defineConfig, devices } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectDir = path.dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.STUDIO_E2E_PORT || 18770);
const noProviderPort = port + 1;
const baseURL = `http://127.0.0.1:${port}`;
const artifacts = path.join(projectDir, ".artifacts");
// A HOME with no coding-agent logins reproduces a fresh machine for the
// "接通一条通路" journey without touching the developer's real credentials.
const emptyHome = path.join(artifacts, "e2e-empty-home");
mkdirSync(emptyHome, { recursive: true });

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  outputDir: "test-results",
  use: {
    baseURL,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: `python3 ../../studio/server.py --fixture --host 127.0.0.1 --port ${port} --no-open`,
      cwd: projectDir,
      url: `${baseURL}/api/runtime`,
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        ...process.env,
        LOCAL_IMAGE_GEN_STUDIO_OUTPUTS: path.join(artifacts, "e2e-outputs"),
        LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK: "1",
      },
    },
    {
      command: `python3 ../../studio/server.py --host 127.0.0.1 --port ${noProviderPort} --no-open`,
      cwd: projectDir,
      url: `http://127.0.0.1:${noProviderPort}/api/runtime`,
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        ...process.env,
        HOME: emptyHome,
        USERPROFILE: emptyHome,
        // No official keys may leak in from the developer's shell either.
        XAI_API_KEY: "",
        OPENAI_API_KEY: "",
        GEMINI_API_KEY: "",
        GOOGLE_API_KEY: "",
        NANOBANANA_API_KEY: "",
        LOCAL_IMAGE_GEN_STUDIO_OUTPUTS: path.join(artifacts, "e2e-empty-outputs"),
        LOCAL_IMAGE_GEN_HOME: path.join(artifacts, "e2e-empty-share"),
        LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK: "1",
      },
    },
  ],
});
