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

export function readRoute(): RouteState {
  const url = new URL(window.location.href);
  const pathname = stripAppBase(url.pathname);
  const skillId = url.searchParams.get("skill");
  if (pathname === "/skills/admin") {
    return {
      section: "admin",
      skillId: null,
      tab: "overview",
      selectedCaseId: null,
      selectedEvalSetId: null,
      selectedVersionId: null,
      selectedRunId: null,
    };
  }
  if (pathname === "/skills/reviews") {
    return {
      section: "my-reviews",
      skillId: null,
      tab: "overview",
      selectedCaseId: null,
      selectedEvalSetId: null,
      selectedVersionId: null,
      selectedRunId: null,
    };
  }
  if (pathname === "/skills/builder") {
    return {
      section: "skill-builder",
      skillId: null,
      tab: "overview",
      selectedCaseId: null,
      selectedEvalSetId: null,
      selectedVersionId: null,
      selectedRunId: null,
    };
  }
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
  if (route.section === "admin") {
    url.pathname = withAppBase("/skills/admin");
    url.search = "";
    window.history.pushState(route, "", url);
    return route;
  }
  if (route.section === "my-reviews") {
    url.pathname = withAppBase("/skills/reviews");
    url.search = "";
    window.history.pushState(route, "", url);
    return route;
  }
  if (route.section === "skill-builder") {
    url.pathname = withAppBase("/skills/builder");
    url.search = "";
    window.history.pushState(route, "", url);
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
  window.history.pushState(route, "", url);
  return route;
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
