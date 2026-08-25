import type { WorkflowJsonSchema } from "./workflow";

export type ExpressionFunction = {
  id: string;
  name: string;
  description: string;
  parameterSchema: WorkflowJsonSchema;
  returnSchema: WorkflowJsonSchema;
  body: string;
  language: string;
  isBuiltin: boolean;
  enabled: boolean;
  createdAt?: string;
  updatedAt?: string;
  createdBy?: string;
  updatedBy?: string;
};

export type ExpressionFunctionPayload = Omit<ExpressionFunction, "id" | "createdAt" | "updatedAt" | "createdBy" | "updatedBy"> & { id?: string };
