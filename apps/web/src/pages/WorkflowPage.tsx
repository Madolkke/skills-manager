import { useMemo } from "react";

type WorkflowPageProps = {
  onBack: () => void;
};

export function WorkflowPage({ onBack }: WorkflowPageProps) {
  const workflowUrl = useMemo(() => workflowAppUrl(), []);

  return (
    <section className="workflow-page">
      <header className="workflow-page-hero">
        <div>
          <p className="workflow-eyebrow">独立工作流编排区</p>
          <h1>工作流编排</h1>
          <p>这里预留外置工作流页面的展位。后续将通过嵌入方式接入，发布结果再回传到 SkillHub。 </p>
        </div>
        <div className="workflow-page-actions">
          <button className="secondary-button" type="button" onClick={onBack}>
            返回首页
          </button>
        </div>
      </header>

      <div className="workflow-frame-shell">
        <div className="workflow-frame-placeholder">
          <strong>外置工作流页面展位</strong>
          <p>后续这里会嵌入独立的工作流应用，例如 `iframe`、新窗口或可配置的远程地址。</p>
          <dl>
            <div>
              <dt>建议地址</dt>
              <dd>{workflowUrl}</dd>
            </div>
            <div>
              <dt>发布通道</dt>
              <dd>`postMessage` + `workflow.publishSkill`</dd>
            </div>
            <div>
              <dt>发布目标</dt>
              <dd>新 Skill 或已有 Skill 的新版本</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}

function workflowAppUrl(): string {
  const value = import.meta.env.VITE_WORKFLOW_APP_URL;
  if (typeof value === "string" && value.trim()) return value.trim();
  return "http://127.0.0.1:xxxx";
}
