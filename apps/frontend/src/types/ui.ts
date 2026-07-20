export type ToastState = { tone: "success" | "danger" | "info"; message: string } | null;

export type WorkerStatus = {
  worker_id: string;
  status: "running" | "idle" | "offline";
  online: boolean;
  stalled?: boolean;
  lease_age_seconds?: number | null;
  recovery_hint?: string | null;
  last_seen_at: string;
  started_at: string;
  current_job?: {
    id: string;
    type?: string | null;
    attempts: number;
    started_at?: string | null;
    run_id?: string | null;
    session_id?: string | null;
    skill_id?: string | null;
    skill_version_id?: string | null;
    error?: string | null;
    status?: string | null;
    last_heartbeat_at?: string | null;
  } | null;
  metadata?: {
    opencode_base_url?: string;
    workdir_host?: string;
    max_attempts?: number;
  } | null;
};

export type WorkerStatusOverview = {
  generated_at: string;
  online_threshold_seconds: number;
  active_window_hours: number;
  summary: {
    total: number;
    online: number;
    running: number;
    idle: number;
    offline: number;
    stalled?: number;
    queued_eval_jobs: number;
    queued_builder_jobs: number;
    queued_publish_jobs?: number;
    running_jobs: number;
  };
  workers: WorkerStatus[];
};
