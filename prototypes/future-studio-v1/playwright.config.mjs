import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectDir = path.dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.STUDIO_E2E_PORT || 18770);
const baseURL = `http://127.0.0.1:${port}`;

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
  webServer: {
    command: `python3 ../../studio/server.py --fixture --host 127.0.0.1 --port ${port} --no-open`,
    cwd: projectDir,
    url: `${baseURL}/api/runtime`,
    reuseExistingServer: false,
    timeout: 30_000,
    env: {
      ...process.env,
      LOCAL_IMAGE_GEN_STUDIO_OUTPUTS: path.join(projectDir, ".artifacts", "e2e-outputs"),
      LOCAL_IMAGE_GEN_SKIP_UPDATE_CHECK: "1",
    },
  },
});
