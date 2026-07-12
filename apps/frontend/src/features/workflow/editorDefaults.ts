import type { CollectionDefinition, DeviceRole, WorkflowConclusion, WorkflowMetadata, WorkflowParameter, WorkflowStep, WorkflowTransition } from "../../types";
import { createWorkflowId } from "./domain/utils";

export function newParameter(): WorkflowParameter {
  return { id: createWorkflowId("input"), key: "", name: "", description: "", dataType: "string", required: true };
}

export function newRole(index: number): DeviceRole {
  return { id: createWorkflowId("role"), key: `device${index}`, name: `设备角色 ${index}`, description: "", required: true };
}

export function newStep(index: number): WorkflowStep {
  return {
    id: createWorkflowId("step"), name: `排查步骤 ${index}`, description: "", isStart: false,
    inputs: [], collectionCalls: [], topology: [], stepType: "expression",
  };
}

export function newConclusion(index: number): WorkflowConclusion {
  return { id: createWorkflowId("conclusion"), name: `排查结论 ${index}`, rootCause: "", repairRecommendation: "", nodeType: "conclusion" };
}

export function newTransition(target: { id: string }): WorkflowTransition {
  return { id: createWorkflowId("transition"), target, conditionText: "", conditionExpression: "" };
}

export function newCollection(index: number, metadata?: Pick<WorkflowMetadata, "industry" | "device" | "versions">): CollectionDefinition {
  return {
    id: createWorkflowId("collection"), revision: 1, key: `collection_${index}`,
    metadata: {
      name: `CLI 采集 ${index}`,
      description: "",
      industry: metadata?.industry ?? "",
      device: metadata?.device ?? "",
      versions: [...(metadata?.versions ?? [])],
      tags: [],
    },
    spec: { collectionType: "cli", commandTemplate: "", outputSamples: [] }, inputs: [], outputs: [],
  };
}
