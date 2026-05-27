import type { PlaywrightTestConfig } from "@playwright/test";

type LocalServerOptions = {
  apiPort: number;
  webPort: number;
  databasePrefix: string;
};

export function localSkillHubServers({ apiPort, webPort, databasePrefix }: LocalServerOptions): PlaywrightTestConfig["webServer"] {
  const databaseUrl = `sqlite:////tmp/${databasePrefix}-${apiPort}-${process.pid}.sqlite3`;
  return [
    {
      command: `cd ../api && UV_NO_CACHE=1 SKILLHUB_DATABASE_URL=${databaseUrl} uv run uvicorn skillhub.api.main:app --host 127.0.0.1 --port ${apiPort}`,
      url: `http://127.0.0.1:${apiPort}/health`,
      reuseExistingServer: false,
      timeout: 90_000,
    },
    {
      command: `VITE_SKILLHUB_API_URL=http://127.0.0.1:${apiPort} npm run dev -- --host 127.0.0.1 --port ${webPort}`,
      url: `http://127.0.0.1:${webPort}/skills`,
      reuseExistingServer: false,
      timeout: 90_000,
    },
  ];
}
