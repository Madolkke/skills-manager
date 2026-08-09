import type { WorkflowBundle, WorkflowSelection } from "./workflow";
import type { WorkflowDebugCase, WorkflowDebugCasePayload } from "./workflowDebug";

export type WorkflowAgentDescriptor = {
  id: string;
  name: string;
  description: string;
  prompt_version: string;
  tools: string[];
  proposal_kind: "debug_case_draft" | null;
};

export type WorkflowAgentCatalog = {
  agents: WorkflowAgentDescriptor[];
  available: boolean;
  unavailable_reason: string;
  agentscope_version: string;
};

export type WorkflowAgentSession = {
  id: string;
  skill_id: string;
  actor_ref: string;
  title: string;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
};

export type WorkflowAgentProposal = {
  id: string;
  run_id: string;
  skill_id: string;
  kind: "debug_case_draft";
  status: "proposed" | "applied" | "stale";
  payload: { candidates: WorkflowDebugCasePayload[] };
  base_revision: number;
  draft_digest: string;
  created_at: string;
  updated_at: string;
};

export type WorkflowAgentRun = {
  id: string;
  session_id: string;
  skill_id: string;
  agent_id: string;
  status: "starting" | "running" | "completed" | "failed" | "canceled" | "interrupted";
  user_input: string;
  response_text: string;
  selection: WorkflowSelection;
  base_revision: number;
  draft_digest: string;
  cancel_requested: boolean;
  usage: Record<string, unknown>;
  error: { code?: string; message?: string } | null;
  proposal: WorkflowAgentProposal | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type WorkflowAgentEvent = {
  event_id: number;
  session_id: string;
  run_id: string;
  event: Record<string, unknown> & { type?: string; id?: string; delta?: string };
};

export type StartWorkflowAgentRun = {
  agent_id: string;
  content: string;
  base_revision: number;
  draft: WorkflowBundle;
  selection: WorkflowSelection;
};

export type WorkflowAgentApplyResult = {
  proposal: WorkflowAgentProposal;
  created_cases: WorkflowDebugCase[];
  stale: boolean;
};
