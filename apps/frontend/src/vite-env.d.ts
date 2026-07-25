/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SKILLHUB_API_URL?: string;
  readonly VITE_SKILLHUB_API_PORT?: string;
  readonly VITE_OPENCODE_RUN_POLL_INTERVAL_MS?: string;
  readonly VITE_SKILLHUB_EVALUATIONS_VISIBLE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
