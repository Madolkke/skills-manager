<script setup lang="ts">
import { javascript } from "@codemirror/lang-javascript";
import { json } from "@codemirror/lang-json";
import { markdown } from "@codemirror/lang-markdown";
import { python } from "@codemirror/lang-python";
import { yaml } from "@codemirror/lang-yaml";
import { EditorState, type Extension } from "@codemirror/state";
import { EditorView, basicSetup } from "codemirror";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { ViewUpdate } from "@codemirror/view";

const props = defineProps<{ path: string; value: string }>();
const emit = defineEmits<{ change: [value: string] }>();

const host = ref<HTMLDivElement | null>(null);
let view: EditorView | null = null;
let applyingExternalValue = false;

onMounted(() => {
  if (!host.value) return;
  view = new EditorView({
    parent: host.value,
    state: EditorState.create({
      doc: props.value,
      extensions: [
        basicSetup,
        ...languageExtensions(props.path),
        EditorView.updateListener.of((update: ViewUpdate) => {
          if (update.docChanged && !applyingExternalValue) emit("change", update.state.doc.toString());
        }),
      ],
    }),
  });
});

onBeforeUnmount(() => {
  view?.destroy();
  view = null;
});

watch(
  () => props.value,
  (value) => {
    if (!view || view.state.doc.toString() === value) return;
    applyingExternalValue = true;
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } });
    applyingExternalValue = false;
  },
);

watch(
  () => props.path,
  () => {
    if (!view || !host.value) return;
    const value = view.state.doc.toString();
    view.destroy();
    view = new EditorView({
      parent: host.value,
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          ...languageExtensions(props.path),
          EditorView.updateListener.of((update: ViewUpdate) => {
            if (update.docChanged && !applyingExternalValue) emit("change", update.state.doc.toString());
          }),
        ],
      }),
    });
  },
);

function languageExtensions(path: string): Extension[] {
  const lowerPath = path.toLowerCase();
  if (lowerPath.endsWith(".md") || lowerPath.endsWith(".markdown")) return [markdown()];
  if (lowerPath.endsWith(".json")) return [json()];
  if (lowerPath.endsWith(".yaml") || lowerPath.endsWith(".yml")) return [yaml()];
  if (lowerPath.endsWith(".py")) return [python()];
  if (lowerPath.endsWith(".js") || lowerPath.endsWith(".jsx")) return [javascript({ jsx: true })];
  if (lowerPath.endsWith(".ts") || lowerPath.endsWith(".tsx")) return [javascript({ jsx: lowerPath.endsWith(".tsx"), typescript: true })];
  return [];
}
</script>

<template>
  <div ref="host" class="bundle-code-editor" :aria-label="`编辑 ${path}`" />
</template>
