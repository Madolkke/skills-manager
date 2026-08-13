import { appFeatures } from "./appFeatures";

export type AppSection = "hub" | "skills" | "workflows" | "admin" | "my-reviews" | "skill-builder";

export type SkillTab = "overview" | "workflow" | "versions" | "evalsets" | "evaluate" | "history" | "reviews" | "publish" | "settings";

export type RouteState = {
  section: AppSection;
  skillId: string | null;
  tab: SkillTab;
  selectedCaseId: string | null;
  selectedEvalSetId: string | null;
  selectedVersionId: string | null;
  selectedRunId: string | null;
  selectedReviewId?: string | null;
};

/**
 * Normalizes the Vite app base to a pathname prefix without a trailing slash.
 */
export function appBasePath(baseUrl = import.meta.env.BASE_URL): string {
  const clean = baseUrl.trim();
  if (!clean || clean === "/") return "";
  return `/${clean.replace(/^\/+|\/+$/g, "")}`;
}

/**
 * Adds the current app base prefix to an internal SPA pathname.
 */
export function withAppBase(pathname: string, baseUrl = import.meta.env.BASE_URL): string {
  const path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return `${appBasePath(baseUrl)}${path}`;
}

/**
 * Removes the current app base prefix before route parsing.
 */
export function stripAppBase(pathname: string, baseUrl = import.meta.env.BASE_URL): string {
  const path = pathname || "/";
  const base = appBasePath(baseUrl);
  if (!base) return path;
  if (path === base) return "/";
  if (path.startsWith(`${base}/`)) return path.slice(base.length) || "/";
  return path;
}

export function readRoute(evaluationsVisible = appFeatures.evaluationsVisible): RouteState {
  const url = new URL(window.location.href);
  const pathname = stripAppBase(url.pathname);
  const skillId = url.searchParams.get("skill");
  if (pathname === "/skills/admin") {
    return normalizeRouteForFeatures({
      section: "admin",
      skillId: null,
      tab: "overview",
      selectedCaseId: null,
      selectedEvalSetId: null,
      selectedVersionId: null,
      selectedRunId: null,
    }, evaluationsVisible);
  }
  if (pathname === "/skills/reviews") {
    return normalizeRouteForFeatures({
      section: "my-reviews",
      skillId: null,
      tab: "overview",
      selectedCaseId: null,
      selectedEvalSetId: null,
      selectedVersionId: null,
      selectedRunId: null,
    }, evaluationsVisible);
  }
  if (pathname === "/skills/builder") {
    return normalizeRouteForFeatures({
      section: "skill-builder",
      skillId: null,
      tab: "overview",
      selectedCaseId: null,
      selectedEvalSetId: null,
      selectedVersionId: null,
      selectedRunId: null,
    }, evaluationsVisible);
  }
  return normalizeRouteForFeatures({
    section: normalizeSection(url.searchParams.get("section"), skillId),
    skillId,
    tab: normalizeTab(url.searchParams.get("tab")),
    selectedCaseId: url.searchParams.get("case"),
    selectedEvalSetId: url.searchParams.get("evalSet"),
    selectedVersionId: url.searchParams.get("version"),
    selectedRunId: url.searchParams.get("run"),
    ...(url.searchParams.get("review") ? { selectedReviewId: url.searchParams.get("review") } : {}),
  }, evaluationsVisible);
}

export function writeRoute(next: Partial<RouteState>, evaluationsVisible = appFeatures.evaluationsVisible): RouteState {
  const current = readRoute(evaluationsVisible);
  const route = normalizeRouteForFeatures({ ...current, ...next }, evaluationsVisible);
  return updateBrowserRoute(route, "push");
}

export function replaceRoute(route: RouteState, evaluationsVisible = appFeatures.evaluationsVisible): RouteState {
  return updateBrowserRoute(normalizeRouteForFeatures(route, evaluationsVisible), "replace");
}

/** Builds an absolute, identity-preserving link without changing the active route. */
export function reviewShareUrl(skillId: string, reviewId: string): string {
  const url = new URL(window.location.href);
  url.pathname = withAppBase("/skills");
  url.search = "";
  url.searchParams.set("section", "skills");
  url.searchParams.set("skill", skillId);
  url.searchParams.set("tab", "reviews");
  url.searchParams.set("review", reviewId);
  return url.toString();
}

export function normalizeRouteForFeatures(route: RouteState, evaluationsVisible: boolean): RouteState {
  if (evaluationsVisible) return route;
  return {
    ...route,
    tab: isEvaluationTab(route.tab) ? "overview" : route.tab,
    selectedCaseId: null,
    selectedEvalSetId: null,
    selectedRunId: null,
  };
}

export function isEvaluationTab(tab: SkillTab): boolean {
  return tab === "evalsets" || tab === "evaluate" || tab === "history";
}

function updateBrowserRoute(route: RouteState, mode: "push" | "replace"): RouteState {
  const url = new URL(window.location.href);
  if (route.section === "admin") {
    url.pathname = withAppBase("/skills/admin");
    url.search = "";
    writeHistory(mode, route, url);
    return route;
  }
  if (route.section === "my-reviews") {
    url.pathname = withAppBase("/skills/reviews");
    url.search = "";
    writeHistory(mode, route, url);
    return route;
  }
  if (route.section === "skill-builder") {
    url.pathname = withAppBase("/skills/builder");
    url.search = "";
    writeHistory(mode, route, url);
    return route;
  }
  url.pathname = withAppBase("/skills");
  url.search = "";
  if (route.section !== "hub") url.searchParams.set("section", route.section);
  if (route.skillId) url.searchParams.set("skill", route.skillId);
  if (route.skillId && route.tab !== "overview") url.searchParams.set("tab", route.tab);
  if (route.selectedEvalSetId) url.searchParams.set("evalSet", route.selectedEvalSetId);
  if (route.selectedCaseId) url.searchParams.set("case", route.selectedCaseId);
  if (route.selectedVersionId) url.searchParams.set("version", route.selectedVersionId);
  if (route.selectedRunId) url.searchParams.set("run", route.selectedRunId);
  if (route.tab === "reviews" && route.selectedReviewId) url.searchParams.set("review", route.selectedReviewId);
  writeHistory(mode, route, url);
  return route;
}

function writeHistory(mode: "push" | "replace", route: RouteState, url: URL): void {
  if (mode === "replace") window.history.replaceState(route, "", url);
  else window.history.pushState(route, "", url);
}

function normalizeSection(value: string | null, skillId: string | null): AppSection {
  if (value === "workflows") return skillId ? "workflows" : "hub";
  if (value === "skills" || value === "my-reviews" || value === "skill-builder") return value;
  if (skillId) return "skills";
  return "hub";
}

function normalizeTab(value: string | null): SkillTab {
  if (value === "workflow" || value === "versions" || value === "evalsets" || value === "evaluate" || value === "history" || value === "reviews" || value === "publish" || value === "settings") return value;
  return "overview";
}
