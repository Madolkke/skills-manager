<script setup lang="ts">
import clsx from "clsx";
import { ChevronDown, ChevronRight, FileText, Folder, FolderOpen } from "lucide-vue-next";
import { computed, defineComponent, h, ref, watch, type PropType, type VNode } from "vue";
import { buildBundleTree, preferredBundleFile, type BundleTreeNode } from "../lib/bundle";
import type { BundleFile } from "../types";
import CodeEditor from "./CodeEditor.vue";

const props = withDefaults(defineProps<{ files: BundleFile[]; drafts: Record<string, string>; rootLabel?: string }>(), { rootLabel: "bundle/" });
const emit = defineEmits<{ "draft-change": [path: string, content: string] }>();

const initial = computed(() => preferredBundleFile(props.files));
const tree = computed(() => buildBundleTree(props.files, props.rootLabel));
const activePath = ref<string | null>(initial.value?.path ?? null);
const expandedPaths = ref(new Set(collectFolderPaths(tree.value)));
const active = computed(() => props.files.find((file) => file.path === activePath.value) ?? initial.value);

watch([initial, tree], () => {
  activePath.value = initial.value?.path ?? null;
  expandedPaths.value = new Set(collectFolderPaths(tree.value));
});

function togglePath(path: string): void {
  const next = new Set(expandedPaths.value);
  if (next.has(path)) next.delete(path);
  else next.add(path);
  expandedPaths.value = next;
}

const TreeNode: ReturnType<typeof defineComponent> = defineComponent({
  props: {
    node: { type: Object as PropType<BundleTreeNode>, required: true },
    depth: { type: Number, required: true },
    activePath: { type: String as PropType<string | null>, default: null },
    expandedPaths: { type: Object as PropType<Set<string>>, required: true },
  },
  emits: ["toggle", "select"],
  setup(nodeProps, { emit: componentEmit }) {
    return (): VNode => renderTreeNode(nodeProps.node, nodeProps.depth, nodeProps.activePath, nodeProps.expandedPaths, componentEmit);
  },
});

function renderTreeNode(
  node: BundleTreeNode,
  depth: number,
  currentPath: string | null,
  expanded: Set<string>,
  componentEmit: (event: "toggle" | "select", path: string) => void,
): VNode {
  if (node.type === "file") {
    return h("button", {
      class: clsx("bundle-tree-node leaf", currentPath === node.path && "active"),
      style: { "--tree-depth": depth },
      type: "button",
      role: "treeitem",
      title: node.path,
      "aria-selected": currentPath === node.path,
      onClick: () => componentEmit("select", node.path),
    }, [h("span", { class: "tree-caret" }), h(FileText, { size: 16 }), h("span", node.name), h("small", node.file.binary ? "bin" : "txt")]);
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
      key: child.path,
      node: child,
      depth: depth + 1,
      activePath: currentPath,
      expandedPaths: expanded,
      onToggle: (path: string) => componentEmit("toggle", path),
      onSelect: (path: string) => componentEmit("select", path),
    }))) : null,
  ]);
}

function collectFolderPaths(node: BundleTreeNode): string[] {
  if (node.type === "file") return [];
  return [node.path, ...node.children.flatMap(collectFolderPaths)];
}
</script>

<template>
  <div v-if="files.length === 0" class="quiet-panel">当前版本没有可编辑的 bundle 文件。</div>
  <section v-else class="bundle-browser bundle-editor">
    <aside class="bundle-tree">
      <div class="bundle-tree-list" role="tree" aria-label="Skill bundle 编辑文件树">
        <TreeNode
          :node="tree"
          :depth="0"
          :active-path="active?.path ?? null"
          :expanded-paths="expandedPaths"
          @toggle="togglePath"
          @select="activePath = $event"
        />
      </div>
    </aside>
    <article class="bundle-content bundle-editor-content">
      <header>
        <strong>{{ active?.path ?? "文件内容" }}</strong>
        <span :class="clsx('editor-file-state', active?.binary && 'muted')">{{ active?.binary ? "二进制只读" : "文本可编辑" }}</span>
      </header>
      <div v-if="active?.binary" class="binary-editor-message">这是二进制文件，保存新版本时会原样保留。</div>
      <CodeEditor
        v-else-if="active"
        :path="active.path"
        :value="drafts[active.path] ?? active.content_text ?? ''"
        @change="emit('draft-change', active.path, $event)"
      />
    </article>
  </section>
</template>
