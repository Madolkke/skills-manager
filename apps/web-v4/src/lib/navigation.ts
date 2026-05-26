export type SkillTab = "overview" | "versions" | "evalsets" | "evaluate" | "history";

export type RouteState = {
  skillId: string | null;
  tab: SkillTab;
  selectedCaseId: string | null;
  selectedVersionId: string | null;
  selectedRunId: string | null;
};

export function readRoute(): RouteState {
  const url = new URL(window.location.href);
  return {
    skillId: url.searchParams.get("skill"),
    tab: normalizeTab(url.searchParams.get("tab")),
    selectedCaseId: url.searchParams.get("case"),
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
  if (route.skillId) url.searchParams.set("skill", route.skillId);
  if (route.skillId && route.tab !== "overview") url.searchParams.set("tab", route.tab);
  if (route.selectedCaseId) url.searchParams.set("case", route.selectedCaseId);
  if (route.selectedVersionId) url.searchParams.set("version", route.selectedVersionId);
  if (route.selectedRunId) url.searchParams.set("run", route.selectedRunId);
  window.history.pushState(route, "", url);
  return route;
}

function normalizeTab(value: string | null): SkillTab {
  if (value === "versions" || value === "evalsets" || value === "evaluate" || value === "history") return value;
  return "overview";
}
