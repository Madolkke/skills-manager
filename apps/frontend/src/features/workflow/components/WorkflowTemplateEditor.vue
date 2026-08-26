<script setup lang="ts">
import { autocompletion, closeCompletion, completionKeymap, startCompletion } from "@codemirror/autocomplete";
import { Compartment, EditorState, type Extension } from "@codemirror/state";
import { EditorView, keymap, placeholder as editorPlaceholder, type ViewUpdate } from "@codemirror/view";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { WorkflowExpressionVariable } from "../workflowExpressionVariables";
import { acceptWorkflowExpressionCompletion, createWorkflowTemplateCompletionSource, shouldOpenWorkflowTemplateCompletion } from "../workflowExpressionCompletion";
import type { WorkflowTemplateDiagnostic } from "../workflowTemplate";

const props = withDefaults(defineProps<{ value: string; variables: WorkflowExpressionVariable[]; diagnostics?: WorkflowTemplateDiagnostic[]; readonly?: boolean; placeholder?: string; ariaLabel?: string }>(), { diagnostics: () => [], readonly: false, placeholder: "可使用 {{ expression }} 引用流程值", ariaLabel: "结论模板" });
const emit = defineEmits<{ change: [value: string] }>();
const host = ref<HTMLDivElement | null>(null);
const readonlyCompartment = new Compartment();
const completionSource = createWorkflowTemplateCompletionSource(() => props.variables);
let view: EditorView | null = null;
let external = false;
let completionTimer: number | null = null;
let changeTimer: number | null = null;
let pendingValue: string | null = null;

onMounted(() => {
  if (!host.value) return;
  view = new EditorView({ parent: host.value, state: EditorState.create({ doc: props.value, extensions: [autocompletion({ override: [completionSource], activateOnTyping: false, interactionDelay: 0, defaultKeymap: false }), keymap.of([{ key: "Mod-Space", run: startCompletion }, ...completionKeymap]), EditorView.lineWrapping, readonlyCompartment.of(readonlyExtensions(props.readonly)), editorPlaceholder(props.placeholder), EditorView.contentAttributes.of({ "aria-label": props.ariaLabel, "aria-autocomplete": "list" }), EditorView.domEventHandlers({ keydown(event, currentView) { if (event.key === "Tab" || event.key === "Enter") return acceptWorkflowExpressionCompletion(currentView); return false; }, blur() { flushPendingChange(); return false; } }), EditorView.updateListener.of((update: ViewUpdate) => { if (!update.docChanged || external) return; queueChange(update.state.doc.toString()); scheduleAutomaticCompletion(update); })] }) });
});
onBeforeUnmount(() => { clearAutomaticCompletionTimer(); flushPendingChange(); view?.destroy(); });
watch(() => props.value, (value) => { if (!view || view.state.doc.toString() === value) return; flushPendingChange(); external = true; view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } }); external = false; });
watch(() => props.readonly, (readonly) => { if (readonly) { clearAutomaticCompletionTimer(); if (view) closeCompletion(view); } view?.dispatch({ effects: readonlyCompartment.reconfigure(readonlyExtensions(readonly)) }); });
function scheduleAutomaticCompletion(update: ViewUpdate): void {
  clearAutomaticCompletionTimer();
  if (props.readonly || update.transactions.some((transaction) => transaction.isUserEvent("input.complete"))) return;
  completionTimer = window.setTimeout(() => {
    completionTimer = null;
    const currentView = view;
    if (!currentView || props.readonly || !currentView.hasFocus) return;
    const cursor = currentView.state.selection.main.head;
    if (shouldOpenWorkflowTemplateCompletion(props.variables, currentView.state.doc.toString(), cursor)) startCompletion(currentView);
    else closeCompletion(currentView);
  }, 0);
}
function clearAutomaticCompletionTimer(): void { if (completionTimer !== null) window.clearTimeout(completionTimer); completionTimer = null; }
function queueChange(value: string): void { pendingValue = value; if (changeTimer !== null) window.clearTimeout(changeTimer); changeTimer = window.setTimeout(flushPendingChange, 200); }
function flushPendingChange(): void { if (changeTimer !== null) window.clearTimeout(changeTimer); changeTimer = null; if (pendingValue === null) return; const value = pendingValue; pendingValue = null; emit("change", value); }
function readonlyExtensions(readonly: boolean): Extension { return [EditorState.readOnly.of(readonly), EditorView.editable.of(!readonly)]; }
</script>

<template>
  <div class="workflow-template-field"><div ref="host" :class="['workflow-template-editor', props.readonly && 'is-readonly', props.diagnostics.length && 'has-warning']" /><ul v-if="props.diagnostics.length" class="workflow-template-diagnostics"><li v-for="item in props.diagnostics" :key="`${item.code}:${item.start}`">{{ item.message }} <small>{{ item.start + 1 }}–{{ item.end }}</small></li></ul></div>
</template>
