import type { SkillVersion } from "../types";

export const SEMVER_PATTERN = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$/;
export type VersionBumpType = "major" | "minor" | "patch";

export function nextPatchVersion(versions: SkillVersion[]): string {
  const latest = [...versions].sort(compareSkillVersions).at(-1);
  return bumpVersion(latest?.version, "patch");
}

export function latestVersion(versions: SkillVersion[]): string {
  return [...versions].sort(compareSkillVersions).at(-1)?.version ?? "0.0.0";
}

export function bumpVersion(current: string | undefined, type: VersionBumpType): string {
  const parsed = parseVersion(current);
  if (!parsed) return "0.0.1";
  const [major, minor, patch] = parsed.core;
  if (type === "major") return `${major + 1}.0.0`;
  if (type === "minor") return `${major}.${minor + 1}.0`;
  return `${major}.${minor}.${patch + 1}`;
}

export function compareSkillVersions(left: SkillVersion, right: SkillVersion): number {
  const semantic = compareSemver(left.version, right.version);
  return semantic || left.version_number - right.version_number;
}

export function validSemver(value: string): boolean {
  return SEMVER_PATTERN.test(value.trim());
}

function compareSemver(left?: string, right?: string): number {
  const leftParts = parseVersion(left);
  const rightParts = parseVersion(right);
  if (!leftParts || !rightParts) return 0;
  for (let index = 0; index < 3; index += 1) {
    const delta = leftParts.core[index] - rightParts.core[index];
    if (delta) return delta;
  }
  return comparePrerelease(leftParts.prerelease, rightParts.prerelease);
}

function parseVersion(value?: string): { core: [number, number, number]; prerelease: string[] } | null {
  if (!value || !SEMVER_PATTERN.test(value)) return null;
  const [withoutBuild] = value.split("+", 1);
  const [core, prerelease = ""] = withoutBuild.split("-", 2);
  return {
    core: core.split(".").map(Number) as [number, number, number],
    prerelease: prerelease ? prerelease.split(".") : [],
  };
}

function comparePrerelease(left: string[], right: string[]): number {
  if (!left.length && !right.length) return 0;
  if (!left.length) return 1;
  if (!right.length) return -1;
  const length = Math.max(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    const leftPart = left[index];
    const rightPart = right[index];
    if (leftPart === undefined) return -1;
    if (rightPart === undefined) return 1;
    const leftNumeric = /^\d+$/.test(leftPart);
    const rightNumeric = /^\d+$/.test(rightPart);
    if (leftNumeric && rightNumeric) {
      const delta = Number(leftPart) - Number(rightPart);
      if (delta) return delta;
      continue;
    }
    if (leftNumeric !== rightNumeric) return leftNumeric ? -1 : 1;
    const delta = leftPart.localeCompare(rightPart);
    if (delta) return delta;
  }
  return 0;
}
