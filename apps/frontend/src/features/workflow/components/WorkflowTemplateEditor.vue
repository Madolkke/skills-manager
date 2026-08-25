<script setup lang="ts">
import { acceptCompletion, autocompletion, completionKeymap, completionStatus, startCompletion, type CompletionContext } from "@codemirror/autocomplete";
import { Compartment, EditorState, type Extension } from "@codemirror/state";
import { EditorView, keymap, placeholder as editorPlaceholder, type ViewUpdate } from "@codemirror/view";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { WorkflowExpressionFunction } from "../../../types";
import type { WorkflowExpressionVariable } from "../workflowExpressionVariables";
import { loadWorkflowExpressionFunctions } from "../workflowExpressionFunctions";
import { workflowExpressionCompletionOption, workflowExpressionCompletionQuery } from "../workflowExpressionCompletion";
import { activeWorkflowTemplateExpression } from "../workflowTemplate";
import type { WorkflowTemplateDiagnostic } from "../workflowTemplate";

const props = withDefaults(defineProps<{ value: string; variables: WorkflowExpressionVariable[]; functions?: Record<string, WorkflowExpressionFunction>; diagnostics?: WorkflowTemplateDiagnostic[]; readonly?: boolean; placeholder?: string; ariaLabel?: string }>(), { diagnostics: () => [], functions: () => ({}), readonly: false, placeholder: "可使用 {{ expression }} 引用流程值", ariaLabel: "结论模板" });
const emit = defineEmits<{ change: [value: string] }>();
const host = ref<HTMLDivElement | null>(null);
const expressionFunctions = ref<Record<string, WorkflowExpressionFunction>>({});
const readonlyCompartment = new Compartment();
let view: EditorView | null = null;
let external = false;

onMounted(() => {
  if (!host.value) return;
  const source = (context: CompletionContext) => {
    const active = activeWorkflowTemplateExpression(context.state.doc.toString(), context.pos);
    if (!active || (!context.explicit && !active.expression.trim())) return null;
    const query = workflowExpressionCompletionQuery(props.variables, active.expression, { ...expressionFunctions.value, ...props.functions });
    if (!query || (!context.explicit && !query.fragment) || !query.matches.length) return null;
    return { from: active.start + query.from, options: query.matches.map(workflowExpressionCompletionOption), filter: false };
  };
  view = new EditorView({ parent: host.value, state: EditorState.create({ doc: props.value, extensions: [autocompletion({ override: [source], activateOnTyping: true, interactionDelay: 0, defaultKeymap: false }), keymap.of([{ key: "Mod-Space", run: startCompletion }, ...completionKeymap]), readonlyCompartment.of(readonlyExtensions(props.readonly)), editorPlaceholder(props.placeholder), EditorView.contentAttributes.of({ "aria-label": props.ariaLabel, "aria-autocomplete": "list" }), EditorView.domEventHandlers({ keydown(event, currentView) { if ((event.key === "Tab" || event.key === "Enter") && completionStatus(currentView.state) === "active") return acceptCompletion(currentView); return false; } }), EditorView.updateListener.of((update: ViewUpdate) => { if (update.docChanged && !external) emit("change", update.state.doc.toString()); })] }) });
  void loadWorkflowExpressionFunctions().then((functions) => { expressionFunctions.value = functions; });
});
onBeforeUnmount(() => view?.destroy());
watch(() => props.value, (value) => { if (!view || view.state.doc.toString() === value) return; external = true; view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } }); external = false; });
watch(() => props.readonly, (readonly) => view?.dispatch({ effects: readonlyCompartment.reconfigure(readonlyExtensions(readonly)) }));
function readonlyExtensions(readonly: boolean): Extension { return [EditorState.readOnly.of(readonly), EditorView.editable.of(!readonly)]; }
</script>

<template>
  <div class="workflow-template-field"><div ref="host" :class="['workflow-template-editor', props.readonly && 'is-readonly', props.diagnostics.length && 'has-warning']" /><ul v-if="props.diagnostics.length" class="workflow-template-diagnostics"><li v-for="item in props.diagnostics" :key="`${item.code}:${item.start}`">{{ item.message }} <small>{{ item.start + 1 }}–{{ item.end }}</small></li></ul></div>
</template>
