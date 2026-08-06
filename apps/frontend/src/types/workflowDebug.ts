export type WorkflowDebugScalar = string | number | boolean | null;

export type WorkflowDebugCollectionFixture = {
  raw_output: string[];
  outputs: Record<string, WorkflowDebugScalar>;
};

export type WorkflowDebugCasePayload = {
  step_id: string;
  name: string;
  description: string;
  expected_target_id: string;
  workflow_inputs: Record<string, WorkflowDebugScalar>;
  collection_fixtures: Record<string, WorkflowDebugCollectionFixture>;
};

export type WorkflowDebugCase = WorkflowDebugCasePayload & {
  id: string;
  skill_id: string;
  created_at: string;
  updated_at: string;
};

export type WorkflowDebugRunStatus =
  | "starting"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "external_state_unknown";

export type WorkflowDebugRunError = {
  code: string;
  message: string;
  retryable: boolean;
};

export type WorkflowDebugRun = {
  id: string;
  case_id: string;
  skill_id: string;
  step_id: string;
  status: WorkflowDebugRunStatus;
  passed: boolean | null;
  task_id: string;
  executor_run_id: string | null;
  workflow_revision: number;
  workflow_digest: string;
  expected_target_id: string;
  poll_interval_seconds?: number;
  latest_executor_status: Record<string, unknown> | null;
  error: WorkflowDebugRunError | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

export type WorkflowDebugRunStart = {
  run: WorkflowDebugRun;
  reused: boolean;
};

export type WorkflowDebugRunHistory = {
  items: WorkflowDebugRun[];
  next_cursor: string | null;
};
