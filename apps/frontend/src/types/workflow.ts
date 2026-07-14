export type VersionedRef = { id: string; revision: number };

export type WorkflowParameter = {
  id: string;
  key: string;
  name: string;
  description: string;
  dataType: string;
  required: boolean;
};

export type WorkflowBinding = { kind: "workflow_input" | "collection_output" | "literal"; reference: Record<string, string>; value?: unknown };
export type WorkflowMetadata = { name: string; code: string; description: string; symptom: string; industry: string; device: string; versions: string[] };
export type DeviceRole = { id: string; key: string; name: string; description: string; required: boolean };
export type CollectionMetadata = { name: string; description: string; industry: string; device: string; versions: string[]; tags: string[] };
export type CollectionOutput = { id: string; key: string; description: string; dataType: string };
export type CliOutputSample = { id: string; name: string; stdout: string; inputValues: Record<string, unknown> };

export type CollectionDefinition = {
  id: string;
  revision: number;
  key: string;
  metadata: CollectionMetadata;
  spec: { collectionType: "cli"; commandTemplate: string; outputSamples: CliOutputSample[] };
  inputs: WorkflowParameter[];
  outputs: CollectionOutput[];
  forkedFrom?: VersionedRef;
};

export type CollectionCall = {
  id: string;
  key: string;
  name: string;
  definition: VersionedRef;
  deviceRoleId?: string;
  sampleCount: number;
  inputBindings: Record<string, WorkflowBinding>;
};

export type WorkflowTransition = {
  id: string;
  target: { id: string };
  conditionText: string;
  conditionExpression: string;
};

export type WorkflowStep = {
  id: string;
  name: string;
  description: string;
  isStart: boolean;
  collectionCalls: CollectionCall[];
  topology: WorkflowTransition[];
  stepType: "expression" | "script";
  script?: { language: string; source: string; options: Record<string, unknown> };
};

export type WorkflowConclusion = { id: string; name: string; rootCause: string; repairRecommendation: string; nodeType: "conclusion" };
export type WorkflowNode = WorkflowStep | WorkflowConclusion;
export type WorkflowBundle = {
  documentType: "workflow_bundle";
  workflow: { id: string; revision: number; metadata: WorkflowMetadata; inputs: WorkflowParameter[]; deviceRoles: DeviceRole[]; nodes: WorkflowNode[] };
  collectionSnapshots: CollectionDefinition[];
};

export type WorkflowEditorSection = "overview" | "script" | "collections" | "paths";

export type WorkflowSelection =
  | { type: "metadata" | "inputs" | "roles" | "collections" }
  | { type: "step"; id: string; section?: WorkflowEditorSection; itemId?: string; field?: string }
  | { type: "conclusion"; id: string; field?: string }
  | { type: "collection"; id: string; revision?: number; field?: string };

export type WorkflowValidationIssue = {
  id: string;
  code: string;
  severity: "error" | "warning";
  message: string;
  selection: WorkflowSelection;
};

export type WorkflowSyncStatus = "never_synced" | "in_sync" | "workflow_changed" | "skill_changed" | "diverged";
export type WorkflowSummary = {
  id: string;
  skill_id: string;
  revision: number;
  document_schema_version: number;
  updated_at: string;
  status: WorkflowSyncStatus;
  last_synced_revision: number | null;
  last_synced_skill_version_id: string | null;
  last_synced_at: string | null;
};

export type WorkflowDetail = {
  id: string;
  skill_id: string;
  revision: number;
  document_schema_version: number;
  document: WorkflowBundle;
  validation: { errors: WorkflowValidationIssue[]; warnings: WorkflowValidationIssue[] };
  sync: Pick<WorkflowSummary, "status" | "last_synced_revision" | "last_synced_skill_version_id" | "last_synced_at">;
  created_at: string;
  updated_at: string;
  created_by: string;
  last_saved_by: string;
  capabilities: import("./skill").SkillCapabilities;
};

export type WorkflowCollectionChange = { operation: "create" | "revise" | "fork"; definition: CollectionDefinition };
export type WorkflowSyncResult = { mode: "created" | "reactivated" | "already_current"; skill_id: string; skill_version_id: string; workflow_revision: number; version?: string; version_number?: number };
