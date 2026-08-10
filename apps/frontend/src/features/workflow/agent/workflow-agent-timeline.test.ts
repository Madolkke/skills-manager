// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { WorkflowAgentDescriptor, WorkflowAgentEvent, WorkflowAgentRun } from "../../../types";
import WorkflowAgentTimeline from "./components/WorkflowAgentTimeline.vue";
import { projectWorkflowAgentEvents } from "./timelineEntries";

describe("Workflow Agent ordered timeline", () => {
  it("preserves thinking, tool, text, and later tool order", () => {
    const entries = projectWorkflowAgentEvents([
      event(1, "THINKING_BLOCK_START", { block_id: "thinking-1" }),
      event(2, "THINKING_BLOCK_DELTA", { block_id: "thinking-1", delta: "先读取上下文" }),
      event(3, "THINKING_BLOCK_END", { block_id: "thinking-1" }),
      event(4, "TOOL_CALL_START", { tool_call_id: "call-1", tool_call_name: "read_context" }),
      event(5, "TOOL_CALL_DELTA", { tool_call_id: "call-1", delta: "{}" }),
      event(6, "TOOL_RESULT_START", { tool_call_id: "call-1", tool_call_name: "read_context" }),
      event(7, "TOOL_RESULT_TEXT_DELTA", { tool_call_id: "call-1", delta: "context" }),
      event(8, "TOOL_RESULT_END", { tool_call_id: "call-1", state: "success" }),
      event(9, "THINKING_BLOCK_START", { block_id: "thinking-2" }),
      event(10, "THINKING_BLOCK_DELTA", { block_id: "thinking-2", delta: "形成结论" }),
      event(11, "THINKING_BLOCK_END", { block_id: "thinking-2" }),
      event(12, "TEXT_BLOCK_START", { block_id: "text-1" }),
      event(13, "TEXT_BLOCK_DELTA", { block_id: "text-1", delta: "## 结论" }),
      event(14, "TEXT_BLOCK_END", { block_id: "text-1" }),
      event(15, "TOOL_CALL_START", { tool_call_id: "call-2", tool_call_name: "create_output" }),
    ]);

    expect(entries.map((entry) => entry.kind)).toEqual(["thinking", "tool", "thinking", "text", "tool"]);
    expect(entries.map((entry) => entry.eventId)).toEqual([1, 4, 9, 12, 15]);
    expect(entries[1]).toMatchObject({ name: "read_context", arguments: "{}", result: "context", phase: "success" });
  });

  it("keeps parallel tools unique and ordered by their first call event", () => {
    const entries = projectWorkflowAgentEvents([
      event(1, "TOOL_CALL_START", { tool_call_id: "call-a", tool_call_name: "tool_a" }),
      event(2, "TOOL_CALL_DELTA", { tool_call_id: "call-a", delta: "{" }),
      event(3, "TOOL_CALL_START", { tool_call_id: "call-b", tool_call_name: "tool_b" }),
      event(4, "TOOL_CALL_DELTA", { tool_call_id: "call-b", delta: "{}" }),
      event(5, "TOOL_CALL_DELTA", { tool_call_id: "call-a", delta: "}" }),
      event(6, "TOOL_RESULT_START", { tool_call_id: "call-b", tool_call_name: "tool_b" }),
      event(7, "TOOL_RESULT_END", { tool_call_id: "call-b", state: "error" }),
      event(8, "TOOL_RESULT_START", { tool_call_id: "call-a", tool_call_name: "tool_a" }),
      event(9, "TOOL_RESULT_END", { tool_call_id: "call-a", state: "success" }),
    ]);

    expect(entries).toHaveLength(2);
    expect(entries[0]).toMatchObject({ name: "tool_a", arguments: "{}", phase: "success" });
    expect(entries[1]).toMatchObject({ name: "tool_b", phase: "failure", state: "error" });
  });

  it("handles missing starts, duplicate sequences, data chunks, and unknown events", () => {
    const entries = projectWorkflowAgentEvents([
      event(4, "DATA_BLOCK_DELTA", { block_id: "data-1", delta: { status: "ok" } }),
      event(2, "THINKING_BLOCK_DELTA", { block_id: "thinking-1", delta: "保留" }),
      event(2, "THINKING_BLOCK_DELTA", { block_id: "thinking-1", delta: "重复" }),
      event(3, "THINKING_BLOCK_END", { block_id: "thinking-1" }),
      event(5, "CUSTOM", { delta: "忽略" }),
      event(6, "DATA_BLOCK_END", { block_id: "data-1" }),
    ]);

    expect(entries).toHaveLength(2);
    expect(entries[0]).toMatchObject({ kind: "thinking", text: "保留", complete: true });
    expect(entries[1]).toMatchObject({ kind: "data", content: '{\n  "status": "ok"\n}', complete: true });
  });

  it("projects thousands of deltas into one logical entry", () => {
    const events = [event(1, "THINKING_BLOCK_START", { block_id: "thinking-large" })];
    for (let index = 0; index < 5_000; index += 1) {
      events.push(event(index + 2, "THINKING_BLOCK_DELTA", { block_id: "thinking-large", delta: "x" }));
    }
    events.push(event(5_002, "THINKING_BLOCK_END", { block_id: "thinking-large" }));

    const entries = projectWorkflowAgentEvents(events);

    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({ kind: "thinking", text: "x".repeat(5_000), complete: true });
  });

  it("renders chronological blocks, collapsed details, raw tool data, and sanitized markdown", () => {
    const run = agentRun({ response_text: "不应重复显示" });
    const wrapper = mount(WorkflowAgentTimeline, {
      props: {
        runs: [run],
        currentRun: run,
        agents: [agentDescriptor()],
        events: [
          event(1, "THINKING_BLOCK_DELTA", { block_id: "thinking-1", delta: "先思考" }),
          event(2, "TOOL_CALL_START", { tool_call_id: "call-1", tool_call_name: "read_context" }),
          event(3, "TOOL_CALL_DELTA", { tool_call_id: "call-1", delta: '{"step":"one"}' }),
          event(4, "TOOL_RESULT_TEXT_DELTA", { tool_call_id: "call-1", delta: "<script>raw</script>" }),
          event(5, "TOOL_RESULT_END", { tool_call_id: "call-1", state: "success" }),
          event(6, "TEXT_BLOCK_DELTA", { block_id: "text-1", delta: "## 最终回答\n\n`safe`<script>alert(1)</script>" }),
        ],
      },
    });

    const blocks = wrapper.findAll(".workflow-agent-event-feed > *");
    expect(blocks.map((block) => block.classes())).toEqual([
      ["workflow-agent-thinking-entry"],
      ["workflow-agent-tool-entry", "is-success"],
      expect.arrayContaining(["workflow-agent-answer", "workflow-agent-text-entry"]),
    ]);
    expect(wrapper.get(".workflow-agent-thinking-entry").attributes("open")).toBeUndefined();
    expect(wrapper.get(".workflow-agent-tool-entry").attributes("open")).toBeUndefined();
    expect(wrapper.get(".workflow-agent-tool-details").text()).toContain('{"step":"one"}');
    expect(wrapper.get(".workflow-agent-tool-details").text()).toContain("<script>raw</script>");
    expect(wrapper.find(".workflow-agent-tool-details script").exists()).toBe(false);
    expect(wrapper.get(".workflow-agent-text-entry h2").text()).toBe("最终回答");
    expect(wrapper.find(".workflow-agent-text-entry script").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("不应重复显示");
  });

  it("keeps response_text as the fallback when no content events exist", () => {
    const run = agentRun({ response_text: "## 历史回答" });
    const wrapper = mount(WorkflowAgentTimeline, {
      props: { runs: [run], currentRun: run, agents: [agentDescriptor()], events: [event(1, "MODEL_CALL_END")] },
    });

    expect(wrapper.get(".workflow-agent-answer h2").text()).toBe("历史回答");
    expect(wrapper.find(".workflow-agent-event-feed").exists()).toBe(false);
  });

  it("expands only the current run and keeps history as a status summary", async () => {
    const historical = agentRun({ id: "run-old", agent_id: "debug_case_generator", user_input: "生成历史用例", response_text: "## 历史回答\n\n更多内容", created_at: "2026-08-08T08:30:00Z" });
    const current = agentRun({ id: "run-current", status: "running", user_input: "检查当前 Workflow", response_text: "当前回答" });
    const wrapper = mount(WorkflowAgentTimeline, {
      props: { runs: [historical, current], currentRun: current, agents: [agentDescriptor(), { ...agentDescriptor(), id: "debug_case_generator", name: "测试用例生成" }], events: [] },
    });

    const turns = wrapper.findAll(".workflow-agent-turn");
    expect(turns[0]!.get(".workflow-agent-turn-head").attributes("aria-expanded")).toBe("false");
    expect(turns[0]!.get(".workflow-agent-user").classes()).toContain("is-summary");
    expect(turns[0]!.get(".workflow-agent-answer-summary").text()).toContain("历史回答");
    expect(turns[0]!.text()).toContain("测试用例生成");
    expect(turns[0]!.text()).toContain("已完成");
    expect(turns[1]!.get(".workflow-agent-turn-head").attributes()).toMatchObject({ "aria-current": "true", "aria-expanded": "true" });
    expect(turns[1]!.text()).toContain("运行中");
    expect(turns[1]!.find(".workflow-agent-answer-summary").exists()).toBe(false);

    await turns[0]!.get(".workflow-agent-turn-head").trigger("click");
    expect(wrapper.emitted("select")?.[0]).toEqual([historical]);
  });

  it.each([
    ["starting", "准备中"],
    ["running", "运行中"],
    ["completed", "已完成"],
    ["failed", "失败"],
    ["canceled", "已取消"],
    ["interrupted", "已中断"],
  ] as const)("renders the %s run status with stable semantics", (status, label) => {
    const run = agentRun({ status });
    const wrapper = mount(WorkflowAgentTimeline, {
      props: { runs: [run], currentRun: run, agents: [agentDescriptor()], events: [] },
    });

    expect(wrapper.get(".workflow-agent-turn").classes()).toContain(`is-${status}`);
    expect(wrapper.get(".workflow-agent-turn-head").text()).toContain(label);
  });

  it("stops following while reading history and can return to the latest event", async () => {
    const run = agentRun({ status: "running" });
    const wrapper = mount(WorkflowAgentTimeline, {
      props: { runs: [run], currentRun: run, agents: [agentDescriptor()], events: [event(1, "TEXT_BLOCK_DELTA", { block_id: "text-1", delta: "开始" })] },
    });
    const timeline = wrapper.get(".workflow-agent-timeline");
    Object.defineProperties(timeline.element, {
      clientHeight: { configurable: true, value: 300 },
      scrollHeight: { configurable: true, value: 1_000 },
      scrollTop: { configurable: true, writable: true, value: 100 },
    });
    const scrollTo = vi.fn();
    Object.defineProperty(timeline.element, "scrollTo", { configurable: true, value: scrollTo });

    await timeline.trigger("scroll");
    expect(timeline.classes()).toContain("is-scrolling");
    expect(wrapper.get(".workflow-agent-jump-latest").text()).toContain("回到最新");
    await wrapper.setProps({ events: [event(1, "TEXT_BLOCK_DELTA", { block_id: "text-1", delta: "开始" }), event(2, "TEXT_BLOCK_DELTA", { block_id: "text-1", delta: "继续" })] });
    expect(scrollTo).not.toHaveBeenCalled();

    await wrapper.get(".workflow-agent-jump-latest").trigger("click");
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 1_000, behavior: "smooth" });
    await wrapper.setProps({ events: [event(1, "TEXT_BLOCK_DELTA", { block_id: "text-1", delta: "开始" }), event(2, "TEXT_BLOCK_DELTA", { block_id: "text-1", delta: "继续" }), event(3, "TEXT_BLOCK_DELTA", { block_id: "text-1", delta: "完成" })] });
    await Promise.resolve();
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 1_000, behavior: "auto" });
  });
});

function event(eventId: number, type: string, values: Record<string, unknown> = {}): WorkflowAgentEvent {
  return { event_id: eventId, session_id: "session-1", run_id: "run-1", event: { type, reply_id: "reply-1", ...values } };
}

function agentRun(overrides: Partial<WorkflowAgentRun> = {}): WorkflowAgentRun {
  return {
    id: "run-1", session_id: "session-1", skill_id: "skill-1", agent_id: "workflow_assistant", status: "completed",
    user_input: "检查 Workflow", response_text: "", selection: { type: "metadata" }, base_revision: 1,
    draft_digest: "digest", cancel_requested: false, usage: {}, error: null, proposal: null,
    created_at: "2026-08-09T00:00:00Z", started_at: "2026-08-09T00:00:00Z", finished_at: "2026-08-09T00:00:01Z",
    ...overrides,
  };
}

function agentDescriptor(): WorkflowAgentDescriptor {
  return { id: "workflow_assistant", name: "Workflow 助手", description: "", prompt_version: "1", tools: [], proposal_kind: null };
}
