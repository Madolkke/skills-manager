import type { SkillTagPayload } from "./skill";

export type SkillBuilderDraftFile = {
  path: string;
  content_text: string;
};

export type SkillBuilderMessage = {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  intent: "chat" | "generate_draft";
  content: string;
  metadata: Record<string, unknown>;
  job_id?: string | null;
  created_at?: string;
};

export type SkillBuilderSession = {
  id: string;
  actor_ref: string;
  title: string;
  status: "active" | "running" | "draft_ready" | "created" | "failed";
  opencode_session_id?: string | null;
  workdir?: string | null;
  draft_files: SkillBuilderDraftFile[];
  workspace_files?: SkillBuilderDraftFile[];
  run_selection: SkillBuilderRunSelection;
  created_skill_id?: string | null;
  created_skill_version_id?: string | null;
  last_error?: string | null;
  created_at?: string;
  updated_at?: string;
  messages: SkillBuilderMessage[];
};

export type SkillBuilderRunSelection = {
  provider_id?: string;
  model_id?: string;
};

export type SkillBuilderMessagePayload = {
  content: string;
  intent: "chat" | "generate_draft";
  provider_id?: string | null;
  model_id?: string | null;
};

export type SkillBuilderDraftPayload = {
  files: SkillBuilderDraftFile[];
};

export type SkillBuilderWorkspacePayload = {
  files: SkillBuilderDraftFile[];
};

export type SkillBuilderCreateSkillPayload = {
  version: string;
  tags: SkillTagPayload[];
  files?: SkillBuilderDraftFile[];
};
