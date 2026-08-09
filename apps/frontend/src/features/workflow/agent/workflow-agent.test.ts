// @vitest-environment jsdom

import { reactive } from "vue";
import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { WorkflowAgentRun } from "../../../types";
import { streamWorkflowAgentEvents } from "./api";
import { shouldSendWorkflowAgentMessage } from "./composerKeyboard";
import WorkflowAgentTimeline from "./components/WorkflowAgentTimeline.vue";
import { cloneWorkflowAgentCandidate } from "./useWorkflowAgent";

afterEach(() => vi.restoreAllMocks());

describe("Workflow Agent assistant", () => {
  it("sends on Enter and keeps modified Enter keys for line breaks", () => {
    const event = (overrides: Partial<KeyboardEvent> = {}) => ({
      altKey: false,
      ctrlKey: false,
      isComposing: false,
      key: "Enter",
      metaKey: false,
      shiftKey: false,
      ...overrides,
    }) as KeyboardEvent;

    expect(shouldSendWorkflowAgentMessage(event())).toBe(true);
    expect(shouldSendWorkflowAgentMessage(event({ ctrlKey: true }))).toBe(false);
    expect(shouldSendWorkflowAgentMessage(event({ shiftKey: true }))).toBe(false);
    expect(shouldSendWorkflowAgentMessage(event({ isComposing: true }))).toBe(false);
    expect(shouldSendWorkflowAgentMessage(event({ key: "a" }))).toBe(false);
  });

  it("renders native thinking, tool, and text events without flattening the event contract", () => {
    const run = workflowAgentRun();
    const wrapper = mount(WorkflowAgentTimeline, {
      props: {
        runs: [run],
        currentRun: run,
        agents: [{ id: "workflow_assistant", name: "Workflow 助手", description: "", prompt_version: "1", tools: [], proposal_kind: null }],
        events: [
          envelope(1, { type: "THINKING_BLOCK_DELTA", delta: "检查表达式" }),
          envelope(2, { type: "TOOL_CALL_START", tool_call_name: "read_workflow_validation" }),
          envelope(3, { type: "TOOL_RESULT_END", tool_call_name: "read_workflow_validation" }),
          envelope(4, { type: "TEXT_BLOCK_DELTA", delta: "发现一个错误。" }),
        ],
      },
    });

    expect(wrapper.text()).toContain("思考过程");
    expect(wrapper.text()).toContain("检查表达式");
    expect(wrapper.text()).toContain("read_workflow_validation");
    expect(wrapper.text()).toContain("发现一个错误。");
  });

  it("renders assistant responses as sanitized markdown", () => {
    const run = {
      ...workflowAgentRun(),
      status: "completed" as const,
      response_text: "## 结论\n\n- 邻居状态为 `Established`\n- [查看资料](https://example.com)\n\n<script>alert(1)</script>",
    };
    const wrapper = mount(WorkflowAgentTimeline, {
      props: {
        runs: [run],
        currentRun: run,
        agents: [{ id: "workflow_assistant", name: "Workflow 助手", description: "", prompt_version: "1", tools: [], proposal_kind: null }],
        events: [],
      },
    });

    expect(wrapper.find(".workflow-agent-answer h2").text()).toBe("结论");
    expect(wrapper.findAll(".workflow-agent-answer li")).toHaveLength(2);
    expect(wrapper.find(".workflow-agent-answer code").text()).toBe("Established");
    expect(wrapper.find(".workflow-agent-answer a").attributes()).toMatchObject({
      href: "https://example.com",
      rel: "noopener noreferrer",
      target: "_blank",
    });
    expect(wrapper.find(".workflow-agent-answer script").exists()).toBe(false);
  });

  it("parses replayable SSE envelopes and sends the Last-Event-ID cursor", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(': keep-alive\n\nid: 7\nevent: agentscope\ndata: {"event_id":7,"session_id":"session-1","run_id":"run-1","event":{"type":"TEXT_BLOCK_DELTA","delta":"ok"}}\n\n'));
        controller.close();
      },
    });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(stream, { status: 200 }));
    const received: number[] = [];

    await streamWorkflowAgentEvents("run-1", 6, new AbortController().signal, (event) => received.push(event.event_id));

    expect(received).toEqual([7]);
    expect(fetchMock.mock.calls[0]?.[1]?.headers).toMatchObject({ "Last-Event-ID": "6" });
  });

  it("restores proposal candidates from reactive run history", () => {
    const candidate = reactive({
      step_id: "step-1",
      name: "case",
      description: "",
      expected_target_id: "conclusion-1",
      workflow_inputs: { "input-1": "peer.example" },
      collection_fixtures: { "call-1": { raw_output: ["Established"], outputs: { "output-1": "Established" } } },
    });

    const cloned = cloneWorkflowAgentCandidate(candidate);

    expect(cloned).toEqual(candidate);
    expect(cloned).not.toBe(candidate);
  });

});

function envelope(eventId: number, event: Record<string, unknown>) {
  return { event_id: eventId, session_id: "session-1", run_id: "run-1", event };
}

function workflowAgentRun(): WorkflowAgentRun {
  return {
    id: "run-1", session_id: "session-1", skill_id: "skill-1", agent_id: "workflow_assistant", status: "running",
    user_input: "检查当前 Workflow", response_text: "", selection: { type: "metadata" }, base_revision: 1,
    draft_digest: "digest", cancel_requested: false, usage: {}, error: null, proposal: null,
    created_at: "2026-08-09T00:00:00Z", started_at: "2026-08-09T00:00:00Z", finished_at: null,
  };
}
