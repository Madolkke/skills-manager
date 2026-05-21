export type SkillTab = "overview" | "variants" | "evalsets" | "evaluate" | "history";

export type RouteState = {
  skillId: string | null;
  tab: SkillTab;
  selectedCaseId: string | null;
  selectedVariantId: string | null;
  selectedRunId: string | null;
};

export function readRoute(): RouteState {
  const url = new URL(window.location.href);
  return {
    skillId: url.searchParams.get("skill"),
    tab: normalizeTab(url.searchParams.get("tab")),
    selectedCaseId: url.searchParams.get("case"),
    selectedVariantId: url.searchParams.get("variant"),
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
  if (route.selectedVariantId) url.searchParams.set("variant", route.selectedVariantId);
  if (route.selectedRunId) url.searchParams.set("run", route.selectedRunId);
  window.history.pushState(route, "", url);
  return route;
}

function normalizeTab(value: string | null): SkillTab {
  if (value === "variants" || value === "evalsets" || value === "evaluate" || value === "history") return value;
  return "overview";
}
