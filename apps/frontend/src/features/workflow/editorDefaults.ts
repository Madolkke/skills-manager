import type { CollectionDefinition, CollectionType, ConfigCollectionSpec, DeviceRole, LogCollectionSpec, WorkflowConclusion, WorkflowMetadata, WorkflowParameter, WorkflowStep, WorkflowTransition } from "../../types";
import { createWorkflowId } from "./domain/utils";
import { newWorkflowSchema } from "./workflowJsonSchema";

export function newParameter(): WorkflowParameter {
  return { id: createWorkflowId("input"), key: "", required: true, schema: newWorkflowSchema("string") };
}

export function newRole(index: number): DeviceRole {
  return { id: createWorkflowId("role"), key: `device${index}`, name: `设备角色 ${index}`, description: "", required: true };
}

export function newStep(index: number): WorkflowStep {
  return {
    id: createWorkflowId("step"), name: `排查步骤 ${index}`, description: "", isStart: false,
    collectionCalls: [], topology: [], stepType: "expression",
  };
}

export function newConclusion(index: number): WorkflowConclusion {
  return { id: createWorkflowId("conclusion"), name: `排查结论 ${index}`, rootCause: "", repairRecommendation: "", nodeType: "conclusion" };
}

export function newTransition(target: { id: string }): WorkflowTransition {
  return { id: createWorkflowId("transition"), target, conditionText: "", conditionExpression: "" };
}

export function newCollection(
  index: number,
  metadata?: Pick<WorkflowMetadata, "industry" | "device" | "versions">,
  collectionType: CollectionType = "cli",
): CollectionDefinition {
  const label = collectionType === "cli" ? "CLI" : collectionType === "log" ? "日志" : "配置";
  return {
    id: createWorkflowId("collection"), revision: 1, key: `collection_${index}`,
    metadata: {
      name: `${label}采集 ${index}`,
      description: "",
      industry: metadata?.industry ?? "",
      device: metadata?.device ?? "",
      versions: [...(metadata?.versions ?? [])],
      tags: [],
    },
    spec: collectionType === "cli"
      ? { collectionType: "cli", commandTemplate: "", outputSamples: [], commandParameterSyntax: "angle-v1" }
      : collectionType === "log" ? newLogCollectionSpec() : newConfigCollectionSpec(),
    inputs: [], outputs: [],
  };
}

export function newLogCollectionSpec(): LogCollectionSpec {
  return { collectionType: "log", sqlDialect: "duckdb", queries: [], outputSamples: [] };
}

export function newConfigCollectionSpec(): ConfigCollectionSpec {
  return { collectionType: "config", config: { commands: [] } };
}
