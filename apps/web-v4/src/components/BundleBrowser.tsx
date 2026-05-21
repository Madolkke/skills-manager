import clsx from "clsx";
import { ChevronDown, ChevronRight, Copy, FileText, Folder, FolderOpen } from "lucide-react";
import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";
import { buildBundleTree, bundleFileText, preferredBundleFile, type BundleTreeNode } from "../lib/bundle";
import type { BundleFile } from "../types";

type BundleBrowserProps = {
  files: BundleFile[];
  rootLabel?: string;
};

export function BundleBrowser({ files, rootLabel = "bundle/" }: BundleBrowserProps) {
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
    return <div className="quiet-panel">当前版本没有可预览的 bundle 文件。</div>;
  }

  return (
    <section className="bundle-browser">
      <aside className="bundle-tree">
        <div className="bundle-tree-list" role="tree" aria-label="Skill bundle 文件树">
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
      <article className="bundle-content">
        <header>
          <strong>{active?.path ?? "文件内容"}</strong>
          <button className="icon-button" type="button" onClick={() => navigator.clipboard.writeText(bundleFileText(active))} aria-label="复制内容">
            <Copy size={17} />
          </button>
        </header>
        <CodePreview text={bundleFileText(active)} />
      </article>
    </section>
  );
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
        <small>{formatSize(node.file.size_bytes)}</small>
      </button>
    );
  }

  const expanded = expandedPaths.has(node.path);
  const FolderIcon = expanded ? FolderOpen : Folder;
  return (
    <div className="bundle-tree-branch">
      <button
        className="bundle-tree-node branch"
        style={treeDepthStyle(depth)}
        type="button"
        role="treeitem"
        aria-expanded={expanded}
        onClick={() => onToggle(node.path)}
      >
        <span className="tree-caret">{expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}</span>
        <FolderIcon size={17} />
        <span>{node.name}/</span>
      </button>
      {expanded ? (
        <div role="group">
          {node.children.map((child) => (
            <TreeNode
              node={child}
              depth={depth + 1}
              activePath={activePath}
              expandedPaths={expandedPaths}
              onToggle={onToggle}
              onSelect={onSelect}
              key={child.path}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function CodePreview({ text }: { text: string }) {
  const lines = text.split(/\r?\n/);
  return (
    <div className="code-preview">
      {lines.map((line, index) => (
        <div className="code-line" key={`${index}-${line}`}>
          <span>{index + 1}</span>
          <code>{line || " "}</code>
        </div>
      ))}
    </div>
  );
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
