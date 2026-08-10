import type { WorkflowAgentEvent } from "../../../types";

type TimelineEntryBase = { key: string; eventId: number };
export type WorkflowAgentThinkingEntry = TimelineEntryBase & { kind: "thinking"; text: string; complete: boolean };
export type WorkflowAgentTextEntry = TimelineEntryBase & { kind: "text"; text: string; complete: boolean };
export type WorkflowAgentDataEntry = TimelineEntryBase & { kind: "data"; content: string; complete: boolean };
export type WorkflowAgentToolEntry = TimelineEntryBase & {
  kind: "tool";
  name: string;
  arguments: string;
  result: string;
  phase: "calling" | "running" | "success" | "failure";
  state: string;
};
export type WorkflowAgentTimelineEntry = WorkflowAgentThinkingEntry | WorkflowAgentTextEntry | WorkflowAgentDataEntry | WorkflowAgentToolEntry;

type ContentKind = "thinking" | "text" | "data";

export function projectWorkflowAgentEvents(events: WorkflowAgentEvent[]): WorkflowAgentTimelineEntry[] {
  const entries: WorkflowAgentTimelineEntry[] = [];
  const byKey = new Map<string, WorkflowAgentTimelineEntry>();
  const activeBlocks = new Map<string, string>();
  const seen = new Set<number>();
  const ordered = [...events].sort((left, right) => left.event_id - right.event_id);

  for (const envelope of ordered) {
    if (seen.has(envelope.event_id)) continue;
    seen.add(envelope.event_id);
    const type = stringValue(envelope.event.type);
    if (type.startsWith("THINKING_BLOCK_")) {
      updateContentEntry("thinking", envelope, type, entries, byKey, activeBlocks);
    } else if (type.startsWith("TEXT_BLOCK_")) {
      updateContentEntry("text", envelope, type, entries, byKey, activeBlocks);
    } else if (type.startsWith("DATA_BLOCK_")) {
      updateContentEntry("data", envelope, type, entries, byKey, activeBlocks);
    } else if (type.startsWith("TOOL_CALL_") || type.startsWith("TOOL_RESULT_")) {
      updateToolEntry(envelope, type, entries, byKey);
    }
  }
  return entries;
}

function updateContentEntry(
  kind: ContentKind,
  envelope: WorkflowAgentEvent,
  type: string,
  entries: WorkflowAgentTimelineEntry[],
  byKey: Map<string, WorkflowAgentTimelineEntry>,
  activeBlocks: Map<string, string>,
): void {
  const event = envelope.event;
  const replyId = stringValue(event.reply_id) || "reply";
  const activeKey = `${kind}:${replyId}`;
  const blockId = stringValue(event.block_id);
  let key = blockId ? `${activeKey}:${blockId}` : activeBlocks.get(activeKey);
  if (!key) key = `${activeKey}:implicit-${envelope.event_id}`;
  if (type.endsWith("_START") || !activeBlocks.has(activeKey)) activeBlocks.set(activeKey, key);

  let entry = byKey.get(key);
  if (!entry) {
    entry = kind === "thinking"
      ? { kind, key, eventId: envelope.event_id, text: "", complete: false }
      : kind === "text"
        ? { kind, key, eventId: envelope.event_id, text: "", complete: false }
        : { kind, key, eventId: envelope.event_id, content: "", complete: false };
    byKey.set(key, entry);
    entries.push(entry);
  }
  if (type.endsWith("_DELTA")) {
    if (entry.kind === "thinking" || entry.kind === "text") entry.text += textDelta(event.delta);
    else if (entry.kind === "data") entry.content = appendChunk(entry.content, event.delta);
  }
  if (type.endsWith("_END")) {
    if (entry.kind === "thinking" || entry.kind === "text" || entry.kind === "data") entry.complete = true;
    activeBlocks.delete(activeKey);
  }
}

function updateToolEntry(
  envelope: WorkflowAgentEvent,
  type: string,
  entries: WorkflowAgentTimelineEntry[],
  byKey: Map<string, WorkflowAgentTimelineEntry>,
): void {
  const event = envelope.event;
  const replyId = stringValue(event.reply_id) || "reply";
  const callId = stringValue(event.tool_call_id) || `implicit-${envelope.event_id}`;
  const key = `tool:${replyId}:${callId}`;
  let entry = byKey.get(key) as WorkflowAgentToolEntry | undefined;
  if (!entry) {
    entry = {
      kind: "tool",
      key,
      eventId: envelope.event_id,
      name: stringValue(event.tool_call_name) || "领域工具",
      arguments: "",
      result: "",
      phase: type.startsWith("TOOL_RESULT_") ? "running" : "calling",
      state: "",
    };
    byKey.set(key, entry);
    entries.push(entry);
  }
  entry.name = stringValue(event.tool_call_name) || entry.name;
  if (type === "TOOL_CALL_DELTA") entry.arguments += textDelta(event.delta);
  if (type === "TOOL_RESULT_START" || type === "TOOL_RESULT_TEXT_DELTA" || type === "TOOL_RESULT_DATA_DELTA") entry.phase = "running";
  if (type === "TOOL_RESULT_TEXT_DELTA") entry.result += textDelta(event.delta);
  if (type === "TOOL_RESULT_DATA_DELTA") entry.result = appendChunk(entry.result, event.delta);
  if (type === "TOOL_RESULT_END") {
    entry.state = stringValue(event.state);
    entry.phase = entry.state.toLowerCase() === "success" ? "success" : "failure";
  }
}

function appendChunk(current: string, value: unknown): string {
  const chunk = typeof value === "string" ? value : value === undefined ? "" : JSON.stringify(value, null, 2);
  if (!chunk) return current;
  return current && typeof value !== "string" ? `${current}\n${chunk}` : current + chunk;
}

function textDelta(value: unknown): string {
  return value === undefined || value === null ? "" : typeof value === "string" ? value : String(value);
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}
