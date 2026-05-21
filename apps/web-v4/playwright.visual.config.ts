import { defineConfig, devices } from "@playwright/test";
import { localSkillHubServers } from "./playwright.shared";

const apiPort = Number(process.env.SKILLHUB_VISUAL_API_PORT ?? 18110);
const webPort = Number(process.env.SKILLHUB_VISUAL_WEB_PORT ?? 13110);

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/visual-smoke.spec.ts",
  timeout: 90_000,
  workers: 1,
  expect: {
    timeout: 10_000,
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
    },
  },
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    colorScheme: "light",
    deviceScaleFactor: 1,
    trace: "retain-on-failure",
    viewport: { width: 1586, height: 992 },
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        deviceScaleFactor: 1,
        viewport: { width: 1586, height: 992 },
      },
    },
  ],
  webServer: localSkillHubServers({ apiPort, webPort, databasePrefix: "skillhub-web-v4-visual" }),
});
