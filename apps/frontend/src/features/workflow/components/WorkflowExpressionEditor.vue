<script setup lang="ts">
import { autocompletion, closeCompletion, completionKeymap, startCompletion } from "@codemirror/autocomplete";
import { Compartment, EditorState, type Extension } from "@codemirror/state";
import { EditorView, keymap, placeholder as editorPlaceholder, type ViewUpdate } from "@codemirror/view";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  acceptWorkflowExpressionCompletion,
  createWorkflowExpressionCompletionSource,
  normalizeWorkflowExpressionInput,
  shouldOpenWorkflowExpressionCompletion,
} from "../workflowExpressionCompletion";
import type { WorkflowExpressionVariable } from "../workflowExpressionVariables";

const props = withDefaults(defineProps<{
  value: string;
  variables: WorkflowExpressionVariable[];
  readonly?: boolean;
  placeholder?: string;
  ariaLabel?: string;
}>(), {
  readonly: false,
  placeholder: "可选的机器可读表达式",
  ariaLabel: "条件表达式",
});
const emit = defineEmits<{ change: [value: string] }>();
const host = ref<HTMLDivElement | null>(null);
const readonlyCompartment = new Compartment();
const completionSource = createWorkflowExpressionCompletionSource(() => props.variables);
let view: EditorView | null = null;
let applyingExternalValue = false;
let completionTimer: number | null = null;
const focusableSelector = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[contenteditable='true']",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

onMounted(() => {
  if (!host.value) return;
  view = new EditorView({
    parent: host.value,
    state: EditorState.create({
      doc: props.value,
      extensions: [
        autocompletion({ override: [completionSource], activateOnTyping: false, interactionDelay: 0, defaultKeymap: false }),
        keymap.of([{ key: "Mod-Space", run: startCompletion }, ...completionKeymap]),
        readonlyCompartment.of(readonlyExtensions(props.readonly)),
        editorPlaceholder(props.placeholder),
        EditorView.contentAttributes.of({
          "aria-label": props.ariaLabel,
          "aria-autocomplete": "list",
          autocapitalize: "off",
          autocomplete: "off",
          spellcheck: "false",
        }),
        EditorView.inputHandler.of((currentView, from, to, text) => {
          const normalized = normalizeWorkflowExpressionInput(text);
          if (normalized === text) return false;
          currentView.dispatch({
            changes: { from, to, insert: normalized },
            selection: { anchor: from + normalized.length },
            userEvent: "input",
          });
          return true;
        }),
        EditorView.domEventHandlers({
          keydown(event, currentView) {
            if (event.key === "Tab") {
              if (acceptWorkflowExpressionCompletion(currentView)) return true;
              return moveEditorFocus(currentView, event.shiftKey);
            }
            if (event.key === "Enter") {
              if (acceptWorkflowExpressionCompletion(currentView)) return true;
              return true;
            }
            return false;
          },
          paste(event, currentView) {
            const text = event.clipboardData?.getData("text/plain");
            if (text === undefined) return false;
            const normalized = normalizeWorkflowExpressionInput(text);
            if (normalized === text) return false;
            const selection = currentView.state.selection.main;
            currentView.dispatch({
              changes: { from: selection.from, to: selection.to, insert: normalized },
              selection: { anchor: selection.from + normalized.length },
              scrollIntoView: true,
              userEvent: "input.paste",
            });
            return true;
          },
        }),
        EditorView.updateListener.of((update: ViewUpdate) => {
          if (!update.docChanged || applyingExternalValue) return;
          emit("change", update.state.doc.toString());
          scheduleAutomaticCompletion(update);
        }),
      ],
    }),
  });
});

onBeforeUnmount(() => {
  clearAutomaticCompletionTimer();
  view?.destroy();
  view = null;
});

watch(() => props.value, (value) => {
  if (!view || view.state.doc.toString() === value) return;
  applyingExternalValue = true;
  const anchor = Math.min(view.state.selection.main.head, value.length);
  view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value }, selection: { anchor } });
  applyingExternalValue = false;
});

watch(() => props.readonly, (readonly) => {
  if (!view) return;
  if (readonly) {
    clearAutomaticCompletionTimer();
    closeCompletion(view);
  }
  view.dispatch({ effects: readonlyCompartment.reconfigure(readonlyExtensions(readonly)) });
});

function scheduleAutomaticCompletion(update: ViewUpdate): void {
  clearAutomaticCompletionTimer();
  if (props.readonly || update.transactions.some((transaction) => transaction.isUserEvent("input.complete"))) return;
  completionTimer = window.setTimeout(() => {
    completionTimer = null;
    const currentView = view;
    if (!currentView || props.readonly || !currentView.hasFocus) return;
    const cursor = currentView.state.selection.main.head;
    const valueBeforeCursor = currentView.state.doc.sliceString(0, cursor);
    if (shouldOpenWorkflowExpressionCompletion(props.variables, valueBeforeCursor)) startCompletion(currentView);
    else closeCompletion(currentView);
  }, 0);
}

function clearAutomaticCompletionTimer(): void {
  if (completionTimer === null) return;
  window.clearTimeout(completionTimer);
  completionTimer = null;
}

function moveEditorFocus(currentView: EditorView, backwards: boolean): boolean {
  const elements = Array.from(currentView.dom.ownerDocument.querySelectorAll<HTMLElement>(focusableSelector))
    .filter(isVisibleFocusableElement);
  const currentIndex = elements.indexOf(currentView.contentDOM);
  const target = elements[currentIndex + (backwards ? -1 : 1)];
  if (currentIndex < 0 || !target) return false;
  target.focus();
  return currentView.dom.ownerDocument.activeElement === target;
}

function isVisibleFocusableElement(element: HTMLElement): boolean {
  for (let current: HTMLElement | null = element; current; current = current.parentElement) {
    const style = window.getComputedStyle(current);
    if (current.hidden || current.inert || current.getAttribute("aria-hidden") === "true" || style.display === "none" || style.visibility === "hidden") return false;
  }
  return true;
}

function readonlyExtensions(readonly: boolean): Extension {
  return [EditorState.readOnly.of(readonly), EditorView.editable.of(!readonly)];
}
</script>

<template>
  <div ref="host" :class="['workflow-expression-editor', props.readonly && 'is-readonly']" />
</template>
