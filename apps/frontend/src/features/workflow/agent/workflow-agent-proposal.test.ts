// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import type { CollectionDefinition, WorkflowBundle, WorkflowDebugCasePayload, WorkflowStep } from "../../../types";
import WorkflowAgentProposalEditor from "./components/WorkflowAgentProposalEditor.vue";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("Workflow Agent proposal workspace", () => {
  it("shows proposal status, selected count, target names, and one active editor", () => {
    const bundle = proposalBundle();
    const wrapper = mountEditor(bundle, {
      candidates: proposalCandidates(),
      selected: [true, false],
      proposalStatus: "proposed",
    });

    expect(wrapper.text()).toContain("调试例候选 · 检查邻居状态");
    expect(wrapper.text()).toContain("待确认");
    expect(wrapper.text()).toContain("1 / 2");
    expect(wrapper.text()).toContain("继续诊断");
    expect(wrapper.text()).toContain("结束排查");
    expect(wrapper.findAll(".workflow-debug-case-editor")).toHaveLength(1);
    expect(wrapper.get('.workflow-agent-candidate-list button[aria-current="true"] .workflow-agent-candidate-index').text()).toBe("01");
  });

  it("switches candidates without rendering duplicate editors or changing selection", async () => {
    const bundle = proposalBundle();
    const wrapper = mountEditor(bundle, {
      candidates: proposalCandidates(),
      selected: [true, false],
      proposalStatus: "proposed",
    });

    await wrapper.findAll(".workflow-agent-candidate-list button")[1]!.trigger("click");

    expect(wrapper.findAll(".workflow-debug-case-editor")).toHaveLength(1);
    expect(wrapper.get(".workflow-agent-candidate-editor > header h3").text()).toBe("链路中断时结束排查");
    expect(wrapper.get(".workflow-agent-candidate-disabled").text()).toContain("不会创建为调试例");
    expect(wrapper.findAll<HTMLInputElement>('.workflow-agent-candidate-list input[type="checkbox"]')[0]!.element.checked).toBe(true);
    expect(wrapper.findAll<HTMLInputElement>('.workflow-agent-candidate-list input[type="checkbox"]')[1]!.element.checked).toBe(false);
  });

  it("exposes candidate selection and semantic applied, stale, and dirty states", async () => {
    const bundle = proposalBundle();
    const wrapper = mountEditor(bundle, {
      candidates: proposalCandidates(),
      selected: [true, true],
      proposalStatus: "applied",
      dirty: true,
    });

    expect(wrapper.get(".workflow-agent-proposal-description .is-success").text()).toBe("已创建");
    expect(wrapper.text()).toContain("保存当前 Workflow 后才能创建调试例");
    await wrapper.setProps({ proposalStatus: "stale", dirty: false });
    expect(wrapper.get(".workflow-agent-proposal-description .is-warning").text()).toBe("已过期");
    expect(wrapper.text()).toContain("提案基于旧版 Workflow");

    await wrapper.findAll<HTMLInputElement>('.workflow-agent-candidate-list input[type="checkbox"]')[0]!.setValue(false);
    expect(wrapper.emitted("select")?.at(-1)).toEqual([0, false]);
    expect(wrapper.get('[aria-label="选择候选：邻居正常时继续诊断"]')).toBeTruthy();
    expect(wrapper.get('[aria-label="关闭"]')).toBeTruthy();
  });
});

function mountEditor(bundle: WorkflowBundle, overrides: Partial<InstanceType<typeof WorkflowAgentProposalEditor>["$props"]>) {
  const step = bundle.workflow.nodes.find((node): node is WorkflowStep => node.id === "step-1")!;
  return mount(WorkflowAgentProposalEditor, {
    props: {
      open: true,
      bundle,
      step,
      candidates: proposalCandidates(),
      selected: [true, true],
      proposalStatus: "proposed",
      canApply: true,
      ...overrides,
    },
    global: { stubs: { Teleport: true, Transition: false } },
  });
}

function proposalCandidates(): WorkflowDebugCasePayload[] {
  return [
    {
      step_id: "step-1",
      name: "邻居正常时继续诊断",
      description: "邻居状态正常，继续检查路由。",
      expected_target_id: "step-next",
      workflow_inputs: { "input-peer": "192.0.2.1" },
      collection_fixtures: { "call-neighbor": { raw_output: ["Peer state: Established"], outputs: { "output-state": "Established" } } },
    },
    {
      step_id: "step-1",
      name: "链路中断时结束排查",
      description: "设备没有返回邻居状态。",
      expected_target_id: "conclusion-down",
      workflow_inputs: {},
      collection_fixtures: {},
    },
  ];
}

function proposalBundle(): WorkflowBundle {
  const definition: CollectionDefinition = {
    id: "collection-neighbor",
    revision: 1,
    key: "neighbor",
    metadata: { name: "邻居状态", description: "", industry: "", device: "", versions: [], tags: [] },
    spec: { collectionType: "cli", commandTemplate: "display bgp peer", outputSamples: [] },
    inputs: [],
    outputs: [{ id: "output-state", key: "state", required: true, schema: { type: "string", title: "邻居状态", description: "" } }],
  };
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow-1",
      revision: 3,
      metadata: { name: "BGP 排障", code: "BGP", description: "", symptom: "", industry: "", device: "", versions: [] },
      inputs: [{ id: "input-peer", key: "peer_ip", required: true, schema: { type: "string", title: "Peer IP", description: "对端地址" } }],
      deviceRoles: [],
      nodes: [
        {
          id: "step-1",
          name: "检查邻居状态",
          description: "",
          isStart: true,
          stepType: "expression",
          collectionCalls: [{ id: "call-neighbor", key: "neighbor", name: "邻居状态", definition: { id: definition.id, revision: 1 }, sampleCount: 1, inputBindings: {} }],
          topology: [
            { id: "transition-next", target: { id: "step-next" }, conditionText: "", conditionExpression: "true" },
            { id: "transition-down", target: { id: "conclusion-down" }, conditionText: "", conditionExpression: "false" },
          ],
        },
        { id: "step-next", name: "继续诊断", description: "", isStart: false, stepType: "expression", collectionCalls: [], topology: [] },
        { id: "conclusion-down", name: "结束排查", rootCause: "", repairRecommendation: "", nodeType: "conclusion" },
      ],
    },
    collectionSnapshots: [definition],
  };
}
