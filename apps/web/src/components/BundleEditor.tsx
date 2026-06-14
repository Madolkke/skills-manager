import clsx from "clsx";
import { ChevronDown, ChevronRight, FileText, Folder, FolderOpen } from "lucide-react";
import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";
import { buildBundleTree, preferredBundleFile, type BundleTreeNode } from "../lib/bundle";
import type { BundleFile } from "../types";
import { CodeEditor } from "./CodeEditor";

type BundleEditorProps = {
  files: BundleFile[];
  drafts: Record<string, string>;
  rootLabel?: string;
  onDraftChange: (path: string, content: string) => void;
};

export function BundleEditor({ files, drafts, rootLabel = "bundle/", onDraftChange }: BundleEditorProps) {
  const initial = useMemo(() => preferredBundleFile(files), [files]);
  const tree = useMemo(() => buildBundleTree(files, rootLabel), [files, rootLabel]);
  const [activePath, setActivePath] = useState<string | null>(initial?.path ?? null);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(() => new Set(collectFolderPaths(tree)));
  const active = files.find((file) => file.path === activePath) ?? initial;

  useEffect(() => {
    setActivePath(initial?.path ?? null);
    setExpandedPaths(new Set(collectFolderPaths(tree)));
  }, [initial?.path, tree]);

  if (files.length === 0) {
    return <div className="quiet-panel">当前版本没有可编辑的 bundle 文件。</div>;
  }

  return (
    <section className="bundle-browser bundle-editor">
      <aside className="bundle-tree">
        <div className="bundle-tree-list" role="tree" aria-label="Skill bundle 编辑文件树">
          <TreeNode
            node={tree}
            depth={0}
            activePath={active?.path ?? null}
            expandedPaths={expandedPaths}
            onToggle={(path) => togglePath(path, setExpandedPaths)}
            onSelect={setActivePath}
          />
        </div>
      </aside>
      <article className="bundle-content bundle-editor-content">
        <header>
          <strong>{active?.path ?? "文件内容"}</strong>
          <span className={clsx("editor-file-state", active?.binary && "muted")}>{active?.binary ? "二进制只读" : "文本可编辑"}</span>
        </header>
        {active ? <FileEditor file={active} value={drafts[active.path] ?? active.content_text ?? ""} onChange={onDraftChange} /> : null}
      </article>
    </section>
  );
}

function FileEditor({ file, value, onChange }: { file: BundleFile; value: string; onChange: (path: string, content: string) => void }) {
  if (file.binary) {
    return <div className="binary-editor-message">这是二进制文件，保存新版本时会原样保留。</div>;
  }

  return <CodeEditor path={file.path} value={value} onChange={(content) => onChange(file.path, content)} />;
}

function TreeNode({
  node,
  depth,
  activePath,
  expandedPaths,
  onToggle,
  onSelect,
}: {
  node: BundleTreeNode;
  depth: number;
  activePath: string | null;
  expandedPaths: Set<string>;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
}) {
  if (node.type === "file") {
    return (
      <button
        className={clsx("bundle-tree-node leaf", activePath === node.path && "active")}
        style={treeDepthStyle(depth)}
        type="button"
        role="treeitem"
        title={node.path}
        aria-selected={activePath === node.path}
        onClick={() => onSelect(node.path)}
      >
        <span className="tree-caret" />
        <FileText size={16} />
        <span>{node.name}</span>
        <small>{node.file.binary ? "bin" : "txt"}</small>
      </button>
    );
  }

  const expanded = expandedPaths.has(node.path);
  const FolderIcon = expanded ? FolderOpen : Folder;
  return (
    <div className="bundle-tree-branch">
      <button className="bundle-tree-node branch" style={treeDepthStyle(depth)} type="button" role="treeitem" aria-expanded={expanded} onClick={() => onToggle(node.path)}>
        <span className="tree-caret">{expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}</span>
        <FolderIcon size={17} />
        <span>{node.name}/</span>
      </button>
      {expanded ? (
        <div role="group">
          {node.children.map((child) => (
            <TreeNode node={child} depth={depth + 1} activePath={activePath} expandedPaths={expandedPaths} onToggle={onToggle} onSelect={onSelect} key={child.path} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function collectFolderPaths(node: BundleTreeNode): string[] {
  if (node.type === "file") return [];
  return [node.path, ...node.children.flatMap(collectFolderPaths)];
}

function togglePath(path: string, setExpandedPaths: (next: (current: Set<string>) => Set<string>) => void): void {
  setExpandedPaths((current) => {
    const next = new Set(current);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    return next;
  });
}

function treeDepthStyle(depth: number) {
  return { "--tree-depth": depth } as CSSProperties;
}
