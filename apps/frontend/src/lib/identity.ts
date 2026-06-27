const ACTOR_STORAGE_KEY = "skillhub.identity.actor_id";
const DEFAULT_ACTOR = "product-operator";

export function getActorId(): string {
  if (typeof window === "undefined") return DEFAULT_ACTOR;
  const actor = window.localStorage.getItem(ACTOR_STORAGE_KEY)?.trim();
  return actor || DEFAULT_ACTOR;
}

export function setTemporaryActorId(actorId: string): string {
  const clean = actorId.trim() || DEFAULT_ACTOR;
  window.localStorage.setItem(ACTOR_STORAGE_KEY, clean);
  return clean;
}

export function clearTemporaryActorId(): string {
  window.localStorage.removeItem(ACTOR_STORAGE_KEY);
  return DEFAULT_ACTOR;
}

export const identityStorageKey = ACTOR_STORAGE_KEY;
export const defaultActorId = DEFAULT_ACTOR;
