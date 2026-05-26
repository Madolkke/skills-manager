import { Upload } from "lucide-react";
import { useEffect, useState } from "react";
import { SkillTabs } from "../components/Tabs";
import type { RouteState, SkillTab } from "../lib/navigation";
import { EvalSetsPage } from "./EvalSetsPage";
import { EvaluatePage } from "./EvaluatePage";
import { HistoryPage } from "./HistoryPage";
import { OverviewPage } from "./OverviewPage";
import { UploadVersionModal } from "./UploadVersionModal";
import { VersionsPage } from "./VersionsPage";
import type { SkillDetail, ToastState } from "../types";

type SkillPageProps = {
  skill: SkillDetail;
  tab: SkillTab;
  route: RouteState;
  onTab: (tab: SkillTab) => void;
  onRefresh: () => Promise<void>;
  onNavigate: (next: Partial<RouteState>) => void;
  onToast: (toast: ToastState) => void;
};

export function SkillPage({ skill, tab, route, onTab, onRefresh, onNavigate, onToast }: SkillPageProps) {
  const [uploadOpen, setUploadOpen] = useState(false);
  const canUploadVersion = tab === "overview" || tab === "versions";
  const closeUpload = () => setUploadOpen(false);

  useEffect(() => {
    setUploadOpen(false);
  }, [skill.skill.id, tab]);

  async function finishUpload() {
    closeUpload();
    onToast({ tone: "success", message: "版本已上传。" });
    await onRefresh();
  }

  return (
    <div className="skill-page">
      <div className="skill-nav-row">
        <SkillTabs active={tab} onChange={onTab} />
        {canUploadVersion ? (
          <button className="primary-button" type="button" onClick={() => setUploadOpen(true)}>
            <Upload size={17} />
            上传版本
          </button>
        ) : null}
      </div>

      {tab === "overview" ? <OverviewPage skill={skill} onNavigate={onNavigate} /> : null}
      {tab === "versions" ? (
        <VersionsPage
          skill={skill}
          selectedVersionId={route.selectedVersionId}
          uploadOpen={uploadOpen}
          onNavigate={onNavigate}
          onUploadClose={closeUpload}
          onUploaded={finishUpload}
        />
      ) : null}
      {tab === "evalsets" ? <EvalSetsPage skill={skill} selectedCaseId={route.selectedCaseId} onNavigate={onNavigate} onRefresh={onRefresh} onToast={onToast} /> : null}
      {tab === "evaluate" ? <EvaluatePage skill={skill} onRefresh={onRefresh} onNavigate={onNavigate} onToast={onToast} /> : null}
      {tab === "history" ? <HistoryPage skill={skill} selectedRunId={route.selectedRunId} onNavigate={onNavigate} onToast={onToast} /> : null}

      {uploadOpen && tab === "overview" ? (
        <UploadVersionModal
          skill={skill}
          onClose={closeUpload}
          onUploaded={finishUpload}
        />
      ) : null}
    </div>
  );
}
