import { defineConfig, devices } from "@playwright/test";
import { localSkillHubServers } from "./playwright.shared";

const apiPort = Number(process.env.SKILLHUB_E2E_API_PORT ?? 18110);
const webPort = Number(process.env.SKILLHUB_E2E_WEB_PORT ?? 13110);

export default defineConfig({
  testDir: "./e2e",
  testIgnore: "**/visual-smoke.spec.ts",
  timeout: 60_000,
  workers: 1,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: localSkillHubServers({ apiPort, webPort, databasePrefix: "skillhub-web-e2e" }),
});
