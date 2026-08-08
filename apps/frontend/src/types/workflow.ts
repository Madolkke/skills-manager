import type { BundleDiffFile, BundleFile } from "./bundle";

export type VersionedRef = { id: string; revision: number };

export type WorkflowScalarSchema = {
  type: "string" | "integer" | "number" | "boolean";
  title: string;
  description: string;
  "x-skillhub-legacy-loose"?: boolean;
};

export type WorkflowObjectSchema = {
  type: "object";
  title: string;
  description: string;
  properties: Record<string, WorkflowJsonSchema>;
  required: string[];
  additionalProperties: boolean;
  "x-skillhub-legacy-loose"?: boolean;
};

export type WorkflowArraySchema = {
  type: "array";
  title: string;
  description: string;
  items: WorkflowJsonSchema;
  "x-skillhub-legacy-loose"?: boolean;
};

export type WorkflowLegacyAnySchema = {
  type?: undefined;
  title?: string;
  description?: string;
  "x-skillhub-legacy-loose": true;
};

export type WorkflowJsonSchema = WorkflowScalarSchema | WorkflowObjectSchema | WorkflowArraySchema | WorkflowLegacyAnySchema;

export type WorkflowParameter = {
  id: string;
  key: string;
  required: boolean;
  schema: WorkflowJsonSchema;
};

export type WorkflowBinding = { kind: "workflow_input" | "collection_output" | "literal"; reference: Record<string, string>; value?: unknown };
export type WorkflowMetadata = { name: string; code: string; description: string; symptom: string; industry: string; device: string; versions: string[] };
export type DeviceRole = { id: string; key: string; name: string; description: string; required: boolean };
export type CollectionMetadata = { name: string; description: string; industry: string; device: string; versions: string[]; tags: string[] };
export type CollectionOutput = { id: string; key: string; required: boolean; schema: WorkflowJsonSchema };

export type WorkflowExpressionDiagnostic = { severity: "warning"; code: string; message: string; start: number; end: number };
export type WorkflowExpressionValidation = { inferredType: Record<string, unknown>; diagnostics: WorkflowExpressionDiagnostic[] };
export type WorkflowExpressionOutput = { sampleCount: number; fields: Record<string, WorkflowJsonSchema> };
export type WorkflowConfigCapture = WorkflowScalarSchema;
export type WorkflowConfigCommand = {
  name: string;
  unique: boolean;
  pattern: string;
  captures: Record<string, WorkflowConfigCapture>;
  children: WorkflowConfigCommand[];
};
export type ConfigCollectionSpec = { collectionType: "config"; config: { commands: WorkflowConfigCommand[] } };
export type WorkflowExpressionSchema = {
  type: "string" | "integer" | "number" | "boolean" | "object" | "array" | ["object", "null"];
  title: string;
  description: string;
  properties?: Record<string, WorkflowExpressionSchema>;
  items?: WorkflowExpressionSchema;
  required?: string[];
};
export type WorkflowExpressionEnvironment = {
  inputs: Record<string, WorkflowJsonSchema>;
  outputs: Record<string, WorkflowExpressionOutput | Record<string, WorkflowJsonSchema>>;
  config: Record<string, WorkflowExpressionSchema>;
};
export type WorkflowExpressionContract = { contractVersion: number; language: string; roots: string[]; typeAlgebra: string[]; outputModel?: Record<string, string>; functions: Record<string, unknown>; methods: Record<string, unknown> };
export type WorkflowExpressionBatchItem = { id: string; source: string };
export type WorkflowExpressionBatchValidation = { id: string } & WorkflowExpressionValidation;
export type WorkflowExpressionBatchResponse = { validations: WorkflowExpressionBatchValidation[] };
export type CliOutputSample = { id: string; name: string; stdout: string; inputValues: Record<string, unknown> };
export type LogAggregationQuery = { id: string; name: string; sql: string; outputIds: string[] };
export type LogOutputSample = { id: string; name: string; text: string };
export type CliCollectionSpec = { collectionType: "cli"; commandTemplate: string; outputSamples: CliOutputSample[] };
export type LogCollectionSpec = { collectionType: "log"; sqlDialect: "duckdb"; queries: LogAggregationQuery[]; outputSamples: LogOutputSample[] };
export type WorkflowCollectionSpec = CliCollectionSpec | LogCollectionSpec | ConfigCollectionSpec;

export type WorkflowLogSchemaColumn = {
  name: string;
  duckdb_type: "TIMESTAMP" | "VARCHAR";
  nullable: boolean;
  title: string;
  description: string;
};
export type WorkflowLogSchemaCatalog = {
  document_schema_version: number;
  dialect: "duckdb";
  logs_table: "logs";
  params_table: "params";
  columns: WorkflowLogSchemaColumn[];
};

export type CollectionDefinition = {
  id: string;
  revision: number;
  key: string;
  metadata: CollectionMetadata;
  spec: WorkflowCollectionSpec;
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
  | { type: "metadata" | "inputs" | "roles" | "collections"; itemId?: string; field?: string }
  | { type: "step"; id: string; section?: WorkflowEditorSection; itemId?: string; field?: string }
  | { type: "conclusion"; id: string; field?: string }
  | { type: "collection"; id: string; revision?: number; itemId?: string; field?: string };

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

export type WorkflowSkillGenerator = {
  id: string;
  version: string;
  label: string;
  default: boolean;
  options_schema: Record<string, unknown>;
};

export type WorkflowSkillGeneratorCatalog = {
  generators: WorkflowSkillGenerator[];
  default_generator_id: string;
};

export type WorkflowSyncWarning = string | { code?: string; message: string };

export type WorkflowSyncPreviewAction = {
  mode: "create" | "reactivate" | "already_current";
  skill_version_id: string | null;
  version: string | null;
  version_number: number | null;
  display_name: string | null;
  next_version: string | null;
};

export type WorkflowSyncPreview = {
  workflow_id: string;
  workflow_revision: number;
  generator: WorkflowSkillGenerator;
  generator_options: Record<string, unknown>;
  generator_options_digest: string;
  preview_digest: string;
  bundle_digest: string;
  files: BundleFile[];
  diff: {
    summary: { added: number; changed: number; removed: number; unchanged: number; binary: number };
    files: BundleDiffFile[];
  };
  warnings: WorkflowSyncWarning[];
  action: WorkflowSyncPreviewAction;
};

export type WorkflowSyncPreviewPayload = {
  expected_workflow_revision: number;
  generator_id: string;
  generator_options: Record<string, unknown>;
};

export type WorkflowSyncPayload = {
  version: string;
  display_name?: string;
  change_summary: string;
  expected_workflow_revision: number;
  generator_id: string;
  generator_version: string;
  generator_options: Record<string, unknown>;
  preview_digest: string;
};

export type WorkflowSyncResult = {
  mode: "created" | "reactivated" | "already_current";
  skill_id: string;
  skill_version_id: string;
  workflow_revision: number;
  version?: string;
  version_number?: number;
  generator_id: string;
  generator_version: string;
  generator_options: Record<string, unknown>;
  generator_options_digest: string;
  preview_digest: string;
  bundle_digest: string;
  generator: WorkflowSkillGenerator;
};
