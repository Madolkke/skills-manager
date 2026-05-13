import type { CommandMenuItem } from "@/components/command-menu/command-menu-types";

export function CommandMenuPreview({ command }: { command: CommandMenuItem | undefined }) {
  if (!command) {
    return (
      <aside className="commandMenuPreview" aria-label="命令预览">
        <span>Preview</span>
        <strong>没有可执行命令</strong>
        <p>换一个关键词，例如“测评”“历史”或“导入”。</p>
      </aside>
    );
  }

  const previewTitle = command.preview?.title ?? command.title;
  const previewBody = command.disabled ? command.disabledReason || command.detail : command.preview?.body ?? command.detail;
  const facts = command.preview?.facts ?? [];

  return (
    <aside className="commandMenuPreview" aria-label="命令预览">
      <span>Preview</span>
      <strong>{previewTitle}</strong>
      <p>{previewBody}</p>
      {facts.length > 0 ? (
        <dl>
          {facts.map((fact) => (
            <div key={`${fact.label}-${fact.value}`}>
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {command.shortcut ? <kbd>{command.shortcut}</kbd> : null}
    </aside>
  );
}
