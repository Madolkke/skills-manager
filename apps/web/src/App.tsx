import { useCallback, useEffect, useState } from "react";
import { Toast } from "./components/Toast";
import { TopBar } from "./components/TopBar";
import { api, ApiError } from "./lib/api";
import { readRoute, writeRoute, type RouteState, type SkillTab } from "./lib/navigation";
import { HubPage } from "./pages/HubPage";
import { NewSkillModal } from "./pages/NewSkillModal";
import { SkillPage } from "./pages/SkillPage";
import { WorkflowPage } from "./pages/WorkflowPage";
import type { SessionInfo, SkillDetail, SkillSummary, ToastState } from "./types";

export default function App() {
  const [route, setRoute] = useState<RouteState>(() => readRoute());
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [skill, setSkill] = useState<SkillDetail | null>(null);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastState>(null);
  const [newSkillOpen, setNewSkillOpen] = useState(false);

  const actor = session?.actor ?? "product-operator";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sessionInfo, list] = await Promise.all([api.getSession(), api.listSkills()]);
      setSession(sessionInfo);
      setSkills(list);
      if (route.section === "skills" && route.skillId) setSkill(await api.getSkill(route.skillId));
      else setSkill(null);
    } catch (error) {
      setToast({ tone: "danger", message: errorMessage(error) });
    } finally {
      setLoading(false);
    }
  }, [route.section, route.skillId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const sync = () => setRoute(readRoute());
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);

  const navigate = useCallback((next: Partial<RouteState>) => setRoute(writeRoute(next)), []);
  const openSkill = useCallback((skillId: string) => navigate({ section: "skills", skillId, tab: "overview", selectedCaseId: null, selectedRunId: null, selectedVersionId: null }), [navigate]);
  const setTab = useCallback((tab: SkillTab) => navigate({ section: "skills", tab, selectedCaseId: null, selectedRunId: null, selectedVersionId: null }), [navigate]);
  const goHome = useCallback(() => navigate({ section: "hub", skillId: null, tab: "overview", selectedCaseId: null, selectedVersionId: null, selectedRunId: null }), [navigate]);
  const goWorkflows = useCallback(() => navigate({ section: "workflows", skillId: null, tab: "overview", selectedCaseId: null, selectedRunId: null, selectedVersionId: null }), [navigate]);

  const sectionShell = route.section === "workflows" ? "workflow-shell" : route.skillId ? "skill-shell" : "hub-shell";
  const shellClass = `app-shell ${sectionShell}`;

  return (
    <div className={shellClass}>
      <div className="app-main">
        <TopBar actor={actor} currentSkill={route.section === "skills" && route.skillId ? skill : null} onHome={goHome} onCreate={() => setNewSkillOpen(true)} onWorkflows={goWorkflows} />
        <main className={route.section === "workflows" ? "workflow-shell-page" : "page-shell"}>
          {route.section === "skills" && route.skillId && skill ? (
            <SkillPage
              skill={skill}
              tab={route.tab}
              route={route}
              onTab={setTab}
              onRefresh={load}
              onNavigate={navigate}
              onToast={setToast}
            />
          ) : route.section === "workflows" ? (
            <WorkflowPage onBack={goHome} />
          ) : (
            <HubPage
              skills={skills}
              actor={actor}
              loading={loading}
              onOpenSkill={openSkill}
              onCreate={() => setNewSkillOpen(true)}
              onOpenWorkflows={goWorkflows}
            />
          )}
        </main>
      </div>
      {newSkillOpen ? (
        <NewSkillModal
          actor={actor}
          onClose={() => setNewSkillOpen(false)}
          onCreated={async (skillId) => {
            setNewSkillOpen(false);
            setToast({ tone: "success", message: "Skill 已创建。" });
            navigate({ skillId, tab: "overview", selectedCaseId: null, selectedRunId: null, selectedVersionId: null });
          }}
        />
      ) : null}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "操作失败，请稍后重试。";
}
