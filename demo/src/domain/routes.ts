import type { AppData, AppState } from "./types";
import { latestVersionForSkill } from "./scoring";

type RouteState = Partial<Omit<AppState, "data">>;

export function applyRouteToState(state: AppState, pathname: string): AppState {
  return normalizeRouteState({
    ...state,
    ...routeStateFromPath(state.data, pathname),
  });
}

export function pathForState(state: AppState): string {
  if (state.view === "hub") return "/";

  const data = state.data;
  const skill = data.skills.find((item) => item.id === state.selectedSkillRef) ?? data.skills[0];
  if (!skill) return "/";

  if (state.view === "eval") {
    return `/skills/${encodeRoutePart(skill.slug)}/eval-sets/${encodeRoutePart(state.evalSetVersionRef)}`;
  }

  if (state.view === "workbench") {
    return `/skills/${encodeRoutePart(skill.slug)}/workbench`;
  }

  if (state.view === "manage") {
    return `/skills/${encodeRoutePart(skill.slug)}/manage`;
  }

  const variant =
    data.variants.find((item) => item.id === state.selectedVariantRef && item.skillRef === skill.id) ??
    data.variants.find((item) => item.id === skill.defaultVariantRef);
  const version =
    data.variantVersions.find((item) => item.id === state.selectedVersionRef && item.variantRef === variant?.id) ??
    data.variantVersions.find((item) => item.id === variant?.currentVersionRef);

  if (state.view === "result") {
    return `/skills/${encodeRoutePart(skill.slug)}/variants/${encodeRoutePart(variant?.id ?? "default")}/versions/${encodeRoutePart(
      version?.id ?? "current",
    )}/results/${encodeRoutePart(state.evalSetVersionRef)}`;
  }

  return `/skills/${encodeRoutePart(skill.slug)}/variants/${encodeRoutePart(variant?.id ?? "default")}/versions/${encodeRoutePart(
    version?.id ?? "current",
  )}`;
}

function routeStateFromPath(data: AppData, pathname: string): RouteState {
  const parts = pathname
    .split("/")
    .filter(Boolean)
    .map((part) => decodeURIComponent(part));

  if (parts.length === 0) return { view: "hub" };
  if (parts[0] !== "skills") return {};

  const skill = data.skills.find((item) => item.slug === parts[1] || item.id === parts[1]);
  if (!skill) return {};

  const route: RouteState = {
    view: "skill",
    selectedSkillRef: skill.id,
    evalSetVersionRef: latestVersionForSkill(data, skill.id)?.id,
  };

  if (parts[2] === "eval-sets") {
    return {
      ...route,
      view: "eval",
      evalSetVersionRef: evalSetVersionRefFromPath(data, skill.id, parts[3]) ?? route.evalSetVersionRef,
    };
  }

  if (parts[2] === "workbench") return { ...route, view: "workbench" };
  if (parts[2] === "manage") return { ...route, view: "manage" };

  if (parts[2] === "variants") {
    const variant = variantFromPath(data, skill.id, parts[3]);
    const version = variant ? variantVersionFromPath(data, variant.id, parts[5]) : undefined;
    const next: RouteState = {
      ...route,
      selectedVariantRef: variant?.id,
      selectedVersionRef: version?.id ?? variant?.currentVersionRef,
    };

    if (parts[6] === "results") {
      return {
        ...next,
        view: "result",
        evalSetVersionRef: evalSetVersionRefFromPath(data, skill.id, parts[7]) ?? route.evalSetVersionRef,
      };
    }

    return next;
  }

  return route;
}

function normalizeRouteState(state: AppState): AppState {
  const skill = state.data.skills.find((item) => item.id === state.selectedSkillRef) ?? state.data.skills[0];
  if (!skill) return state;

  const variants = state.data.variants.filter((item) => item.skillRef === skill.id);
  const variant =
    variants.find((item) => item.id === state.selectedVariantRef) ??
    variants.find((item) => item.id === skill.defaultVariantRef) ??
    variants[0];
  const version =
    state.data.variantVersions.find((item) => item.id === state.selectedVersionRef && item.variantRef === variant?.id) ??
    state.data.variantVersions.find((item) => item.id === variant?.currentVersionRef);
  const evalSetVersion = evalSetVersionFromData(state.data, skill.id, state.evalSetVersionRef);

  return {
    ...state,
    selectedSkillRef: skill.id,
    selectedVariantRef: variant?.id ?? state.selectedVariantRef,
    selectedVersionRef: version?.id ?? state.selectedVersionRef,
    evalSetVersionRef: evalSetVersion?.id ?? state.evalSetVersionRef,
  };
}

function variantFromPath(data: AppData, skillRef: string, variantRef?: string) {
  if (!variantRef || variantRef === "default") {
    const skill = data.skills.find((item) => item.id === skillRef);
    return data.variants.find((item) => item.id === skill?.defaultVariantRef);
  }
  return data.variants.find((item) => item.id === variantRef && item.skillRef === skillRef);
}

function variantVersionFromPath(data: AppData, variantRef: string, versionRef?: string) {
  if (!versionRef || versionRef === "current") {
    const variant = data.variants.find((item) => item.id === variantRef);
    return data.variantVersions.find((item) => item.id === variant?.currentVersionRef);
  }
  return data.variantVersions.find((item) => item.id === versionRef && item.variantRef === variantRef);
}

function evalSetVersionRefFromPath(data: AppData, skillRef: string, value?: string) {
  if (!value || value === "latest") return latestVersionForSkill(data, skillRef)?.id;
  return evalSetVersionFromData(data, skillRef, value)?.id;
}

function evalSetVersionFromData(data: AppData, skillRef: string, value: string) {
  const corpus = data.evalCorpora.find((item) => item.skillRef === skillRef);
  const versions = data.evalSetVersions
    .filter((item) => item.corpusRef === corpus?.id)
    .sort((a, b) => a.version.localeCompare(b.version, undefined, { numeric: true }));
  return versions.find((item) => item.id === value || item.version === value) ?? versions.at(-1);
}

function encodeRoutePart(value: string): string {
  return encodeURIComponent(value);
}
