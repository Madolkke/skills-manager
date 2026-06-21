export type AppSection = "hub" | "skills" | "workflows";

export type SkillTab = "overview" | "versions" | "evalsets" | "evaluate" | "history";

export type RouteState = {
  section: AppSection;
  skillId: string | null;
  tab: SkillTab;
  selectedCaseId: string | null;
  selectedEvalSetId: string | null;
  selectedVersionId: string | null;
  selectedRunId: string | null;
};

export function readRoute(): RouteState {
  const url = new URL(window.location.href);
  const skillId = url.searchParams.get("skill");
  return {
    section: normalizeSection(url.searchParams.get("section"), skillId),
    skillId,
    tab: normalizeTab(url.searchParams.get("tab")),
    selectedCaseId: url.searchParams.get("case"),
    selectedEvalSetId: url.searchParams.get("evalSet"),
    selectedVersionId: url.searchParams.get("version"),
    selectedRunId: url.searchParams.get("run"),
  };
}

export function writeRoute(next: Partial<RouteState>): RouteState {
  const current = readRoute();
  const route = { ...current, ...next };
  const url = new URL(window.location.href);
  url.pathname = "/skills";
  url.search = "";
  if (route.section !== "hub") url.searchParams.set("section", route.section);
  if (route.skillId) url.searchParams.set("skill", route.skillId);
  if (route.skillId && route.tab !== "overview") url.searchParams.set("tab", route.tab);
  if (route.selectedEvalSetId) url.searchParams.set("evalSet", route.selectedEvalSetId);
  if (route.selectedCaseId) url.searchParams.set("case", route.selectedCaseId);
  if (route.selectedVersionId) url.searchParams.set("version", route.selectedVersionId);
  if (route.selectedRunId) url.searchParams.set("run", route.selectedRunId);
  window.history.pushState(route, "", url);
  return route;
}

function normalizeSection(value: string | null, skillId: string | null): AppSection {
  if (value === "skills" || value === "workflows") return value;
  if (skillId) return "skills";
  return "hub";
}

function normalizeTab(value: string | null): SkillTab {
  if (value === "versions" || value === "evalsets" || value === "evaluate" || value === "history") return value;
  return "overview";
}
