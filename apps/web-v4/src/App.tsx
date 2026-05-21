import { useCallback, useEffect, useMemo, useState } from "react";
import { BrandRail } from "./components/BrandRail";
import { Toast } from "./components/Toast";
import { TopBar } from "./components/TopBar";
import { api, ApiError } from "./lib/api";
import { allKnownTags } from "./lib/format";
import { readRoute, writeRoute, type RouteState, type SkillTab } from "./lib/navigation";
import { HubPage } from "./pages/HubPage";
import { NewSkillModal } from "./pages/NewSkillModal";
import { SkillPage } from "./pages/SkillPage";
import type { SessionInfo, SkillDetail, SkillSummary, ToastState } from "./types";

export default function App() {
  const [route, setRoute] = useState<RouteState>(() => readRoute());
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [skill, setSkill] = useState<SkillDetail | null>(null);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastState>(null);
  const [newSkillOpen, setNewSkillOpen] = useState(false);
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [searchFocusSignal, setSearchFocusSignal] = useState(0);

  const knownTags = useMemo(() => allKnownTags(skills), [skills]);
  const actor = session?.actor ?? "product-operator";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sessionInfo, list] = await Promise.all([api.getSession(), api.listSkills()]);
      setSession(sessionInfo);
      setSkills(list);
      if (route.skillId) setSkill(await api.getSkill(route.skillId));
      else setSkill(null);
    } catch (error) {
      setToast({ tone: "danger", message: errorMessage(error) });
    } finally {
      setLoading(false);
    }
  }, [route.skillId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const sync = () => setRoute(readRoute());
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);

  const navigate = useCallback((next: Partial<RouteState>) => setRoute(writeRoute(next)), []);
  const openSkill = useCallback((skillId: string) => navigate({ skillId, tab: "overview", selectedCaseId: null, selectedRunId: null }), [navigate]);
  const setTab = useCallback((tab: SkillTab) => navigate({ tab, selectedCaseId: null, selectedRunId: null }), [navigate]);
  const goHome = useCallback(() => navigate({ skillId: null, tab: "overview", selectedCaseId: null, selectedVariantId: null, selectedRunId: null }), [navigate]);
  const focusHubSearch = useCallback(() => {
    goHome();
    setSearchFocusSignal((value) => value + 1);
  }, [goHome]);

  const shellClass = ["app-shell", railCollapsed ? "rail-is-collapsed" : "", route.skillId ? "skill-shell" : "hub-shell"].filter(Boolean).join(" ");

  return (
    <div className={shellClass}>
      <BrandRail
        collapsed={railCollapsed}
        homeActive={!route.skillId}
        onToggle={() => setRailCollapsed((value) => !value)}
        onHome={goHome}
        onCreate={() => setNewSkillOpen(true)}
        onSearch={focusHubSearch}
      />
      <div className="app-main">
        {route.skillId ? <TopBar actor={actor} currentSkill={skill} onHome={goHome} /> : null}
        <main className="page-shell">
          {route.skillId && skill ? (
            <SkillPage
              skill={skill}
              tab={route.tab}
              route={route}
              knownTags={knownTags}
              onTab={setTab}
              onRefresh={load}
              onNavigate={navigate}
              onToast={setToast}
            />
          ) : (
            <HubPage
              skills={skills}
              actor={actor}
              loading={loading}
              searchFocusSignal={searchFocusSignal}
              onOpenSkill={openSkill}
              onCreate={() => setNewSkillOpen(true)}
            />
          )}
        </main>
      </div>
      {newSkillOpen ? (
        <NewSkillModal
          actor={actor}
          knownTags={knownTags}
          onClose={() => setNewSkillOpen(false)}
          onCreated={async (skillId) => {
            setNewSkillOpen(false);
            setToast({ tone: "success", message: "Skill 已创建。" });
            navigate({ skillId, tab: "overview", selectedCaseId: null, selectedRunId: null, selectedVariantId: null });
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
