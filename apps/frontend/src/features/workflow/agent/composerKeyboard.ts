type ComposerKeyboardEvent = Pick<KeyboardEvent, "altKey" | "ctrlKey" | "isComposing" | "key" | "metaKey" | "shiftKey">;

export function shouldSendWorkflowAgentMessage(event: ComposerKeyboardEvent): boolean {
  return event.key === "Enter"
    && !event.altKey
    && !event.ctrlKey
    && !event.metaKey
    && !event.shiftKey
    && !event.isComposing;
}
