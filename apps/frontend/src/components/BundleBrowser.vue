<script setup lang="ts">
import clsx from "clsx";
import { ChevronDown, ChevronRight, Copy, FileText, Folder, FolderOpen } from "lucide-vue-next";
import { computed, defineComponent, h, ref, watch, type PropType, type VNode } from "vue";
import { buildBundleTree, bundleFileText, preferredBundleFile, type BundleTreeNode } from "../lib/bundle";
import type { BundleFile } from "../types";

const props = withDefaults(defineProps<{ files: BundleFile[]; rootLabel?: string }>(), { rootLabel: "bundle/" });

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

async function copyActive(): Promise<void> {
  await navigator.clipboard.writeText(bundleFileText(active.value));
}

const TreeNode: ReturnType<typeof defineComponent> = defineComponent({
  props: {
    node: { type: Object as PropType<BundleTreeNode>, required: true },
    depth: { type: Number, required: true },
    activePath: { type: String as PropType<string | null>, default: null },
    expandedPaths: { type: Object as PropType<Set<string>>, required: true },
  },
  emits: ["toggle", "select"],
  setup(nodeProps, { emit }) {
    return (): VNode => renderTreeNode(nodeProps.node, nodeProps.depth, nodeProps.activePath, nodeProps.expandedPaths, emit);
  },
});

function renderTreeNode(
  node: BundleTreeNode,
  depth: number,
  currentPath: string | null,
  expanded: Set<string>,
  emit: (event: "toggle" | "select", path: string) => void,
): VNode {
  if (node.type === "file") {
    return h("button", {
      class: clsx("bundle-tree-node leaf", currentPath === node.path && "active"),
      style: treeDepthStyle(depth),
      type: "button",
      role: "treeitem",
      title: node.path,
      "aria-selected": currentPath === node.path,
      onClick: () => emit("select", node.path),
    }, [h("span", { class: "tree-caret" }), h(FileText, { size: 16 }), h("span", node.name), h("small", formatSize(node.file.size_bytes))]);
  }

  const isExpanded = expanded.has(node.path);
  const FolderIcon = isExpanded ? FolderOpen : Folder;
  return h("div", { class: "bundle-tree-branch" }, [
    h("button", {
      class: "bundle-tree-node branch",
      style: treeDepthStyle(depth),
      type: "button",
      role: "treeitem",
      "aria-expanded": isExpanded,
      onClick: () => emit("toggle", node.path),
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
      onToggle: (path: string) => emit("toggle", path),
      onSelect: (path: string) => emit("select", path),
    }))) : null,
  ]);
}

function formatSize(value?: number): string {
  if (!value) return "";
  if (value < 1024) return `${value} B`;
  return `${Math.round(value / 102.4) / 10} KB`;
}

function collectFolderPaths(node: BundleTreeNode): string[] {
  if (node.type === "file") return [];
  return [node.path, ...node.children.flatMap(collectFolderPaths)];
}

function treeDepthStyle(depth: number) {
  return { "--tree-depth": depth };
}
</script>

<template>
  <div v-if="files.length === 0" class="quiet-panel">当前版本没有可预览的 bundle 文件。</div>
  <section v-else class="bundle-browser">
    <aside class="bundle-tree">
      <div class="bundle-tree-list" role="tree" aria-label="Skill bundle 文件树">
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
    <article class="bundle-content">
      <header>
        <strong>{{ active?.path ?? "文件内容" }}</strong>
        <button class="icon-button" type="button" aria-label="复制内容" @click="copyActive">
          <Copy :size="17" />
        </button>
      </header>
      <div class="code-preview">
        <div v-for="(line, index) in bundleFileText(active).split(/\r?\n/)" :key="`${index}-${line}`" class="code-line">
          <span>{{ index + 1 }}</span>
          <code>{{ line || " " }}</code>
        </div>
      </div>
    </article>
  </section>
</template>
