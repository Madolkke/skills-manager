<script setup lang="ts">
import clsx from "clsx";
import { ChevronDown, ChevronRight, FilePlus2, FileText, Folder, FolderOpen, Trash2 } from "lucide-vue-next";
import { computed, defineComponent, h, ref, watch, type PropType, type VNode } from "vue";
import { buildBundleTree, preferredBundleFile, type BundleTreeNode } from "../lib/bundle";
import { SKILL_ENTRY_PATH, type SkillBundleDraftFile, type SkillBundleValidationResult } from "../lib/skillBundleDraft";
import CodeEditor from "./CodeEditor.vue";

const props = withDefaults(defineProps<{ files: SkillBundleDraftFile[]; validation: SkillBundleValidationResult; rootLabel?: string }>(), { rootLabel: "bundle/" });
const emit = defineEmits<{
  add: [];
  remove: [id: string];
  "path-change": [id: string, path: string];
  "content-change": [id: string, content: string];
}>();

const initial = computed(() => preferredBundleFile(props.files));
const tree = computed(() => buildBundleTree(props.files, props.rootLabel));
const activeId = ref(initial.value?.id ?? null);
const expandedPaths = ref(new Set(collectFolderPaths(tree.value)));
const active = computed(() => props.files.find((file) => file.id === activeId.value) ?? initial.value);
const activeError = computed(() => (active.value ? props.validation.errors[active.value.id] : ""));
const canDeleteActive = computed(() => Boolean(active.value && active.value.path.trim() !== SKILL_ENTRY_PATH));

watch(
  () => props.files.length,
  (nextLength, previousLength) => {
    if (nextLength <= previousLength) return;
    activeId.value = props.files.at(-1)?.id ?? activeId.value;
  },
);

watch([initial, tree], () => {
  if (activeId.value && props.files.some((file) => file.id === activeId.value)) {
    expandedPaths.value = new Set(collectFolderPaths(tree.value));
    return;
  }
  activeId.value = initial.value?.id ?? null;
  expandedPaths.value = new Set(collectFolderPaths(tree.value));
});

function togglePath(path: string): void {
  const next = new Set(expandedPaths.value);
  if (next.has(path)) next.delete(path);
  else next.add(path);
  expandedPaths.value = next;
}

function selectFile(file: SkillBundleDraftFile): void {
  activeId.value = file.id;
}

function removeActive(): void {
  if (active.value && canDeleteActive.value) emit("remove", active.value.id);
}

const TreeNode: ReturnType<typeof defineComponent> = defineComponent({
  props: {
    node: { type: Object as PropType<BundleTreeNode>, required: true },
    depth: { type: Number, required: true },
    activeId: { type: String as PropType<string | null>, default: null },
    expandedPaths: { type: Object as PropType<Set<string>>, required: true },
    errors: { type: Object as PropType<Record<string, string>>, required: true },
  },
  emits: ["toggle", "select"],
  setup(nodeProps, { emit: componentEmit }) {
    return (): VNode => renderTreeNode(nodeProps.node, nodeProps.depth, nodeProps.activeId, nodeProps.expandedPaths, nodeProps.errors, componentEmit);
  },
});

function renderTreeNode(
  node: BundleTreeNode,
  depth: number,
  currentId: string | null,
  expanded: Set<string>,
  errors: Record<string, string>,
  componentEmit: (event: "toggle" | "select", value: string | SkillBundleDraftFile) => void,
): VNode {
  if (node.type === "file") {
    const id = node.file.id ?? node.path;
    return h("button", {
      class: clsx("bundle-tree-node leaf", currentId === id && "active", errors[id] && "invalid"),
      style: { "--tree-depth": depth },
      type: "button",
      role: "treeitem",
      title: errors[id] || node.path,
      "aria-selected": currentId === id,
      onClick: () => componentEmit("select", node.file as SkillBundleDraftFile),
    }, [h("span", { class: "tree-caret" }), h(FileText, { size: 16 }), h("span", node.name || "未命名文件"), h("small", node.file.binary ? "bin" : "txt")]);
  }

  const isExpanded = expanded.has(node.path);
  const FolderIcon = isExpanded ? FolderOpen : Folder;
  return h("div", { class: "bundle-tree-branch" }, [
    h("button", {
      class: "bundle-tree-node branch",
      style: { "--tree-depth": depth },
      type: "button",
      role: "treeitem",
      "aria-expanded": isExpanded,
      onClick: () => componentEmit("toggle", node.path),
    }, [
      h("span", { class: "tree-caret" }, [isExpanded ? h(ChevronDown, { size: 15 }) : h(ChevronRight, { size: 15 })]),
      h(FolderIcon, { size: 17 }),
      h("span", `${node.name}/`),
    ]),
    isExpanded ? h("div", { role: "group" }, node.children.map((child) => h(TreeNode, {
      key: child.type === "file" ? `${child.path}:${child.file.id ?? ""}` : child.path,
      node: child,
      depth: depth + 1,
      activeId: currentId,
      expandedPaths: expanded,
      errors,
      onToggle: (path: string) => componentEmit("toggle", path),
      onSelect: (file: SkillBundleDraftFile) => componentEmit("select", file),
    }))) : null,
  ]);
}

function collectFolderPaths(node: BundleTreeNode): string[] {
  if (node.type === "file") return [];
  return [node.path, ...node.children.flatMap(collectFolderPaths)];
}
</script>

<template>
  <div v-if="files.length === 0" class="quiet-panel">
    当前版本没有 bundle 文件。
    <button class="secondary-button" type="button" @click="emit('add')">
      <FilePlus2 :size="16" />
      添加文件
    </button>
  </div>
  <section v-else class="bundle-browser bundle-editor">
    <aside class="bundle-tree">
      <div class="bundle-editor-toolbar">
        <button class="secondary-button" type="button" @click="emit('add')">
          <FilePlus2 :size="16" />
          添加文件
        </button>
      </div>
      <div class="bundle-tree-list" role="tree" aria-label="Skill bundle 编辑文件树">
        <TreeNode
          :node="tree"
          :depth="0"
          :active-id="active?.id ?? null"
          :expanded-paths="expandedPaths"
          :errors="validation.errors"
          @toggle="togglePath"
          @select="selectFile"
        />
      </div>
    </aside>
    <article class="bundle-content bundle-editor-content">
      <header>
        <strong>{{ active?.path ?? "文件内容" }}</strong>
        <span :class="clsx('editor-file-state', active?.binary && 'muted')">{{ active?.binary ? "二进制只读" : "文本可编辑" }}</span>
      </header>
      <div v-if="active" class="bundle-editor-file-meta">
        <label class="field-label compact">
          <span>文件路径</span>
          <input :value="active.path" :disabled="active.path === SKILL_ENTRY_PATH" placeholder="例如 prompts/instructions.md" @input="emit('path-change', active.id, ($event.target as HTMLInputElement).value)" />
        </label>
        <button class="secondary-button" type="button" :disabled="!canDeleteActive" :title="active.path === SKILL_ENTRY_PATH ? 'SKILL.md 是 Skill 入口文件，不能删除。' : ''" @click="removeActive">
          <Trash2 :size="16" />
          删除文件
        </button>
        <p v-if="activeError" class="field-hint danger">{{ activeError }}</p>
      </div>
      <div v-if="active?.binary" class="binary-editor-message">这是二进制文件，保存新版本时会原样保留；你可以重命名路径或删除它。</div>
      <CodeEditor
        v-else-if="active"
        :path="active.path"
        :value="active.content_text ?? ''"
        @change="emit('content-change', active.id, $event)"
      />
    </article>
  </section>
</template>
