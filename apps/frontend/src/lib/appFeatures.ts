export type AppFeatures = Readonly<{
  evaluationsVisible: boolean;
}>;

/**
 * Keeps existing deployments enabled unless the flag is explicitly false.
 */
export function enabledUnlessFalse(value: string | undefined): boolean {
  return value?.trim().toLowerCase() !== "false";
}

export const appFeatures: AppFeatures = Object.freeze({
  evaluationsVisible: enabledUnlessFalse(import.meta.env.VITE_SKILLHUB_EVALUATIONS_VISIBLE),
});
