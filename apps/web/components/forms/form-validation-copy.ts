export type RequiredControlKind = "checkbox" | "file" | "text";

export function requiredFieldMessage(label: string, kind: RequiredControlKind) {
  if (kind === "file") return `选择 ${label}`;
  if (kind === "checkbox") return `确认 ${label}`;
  return `填写 ${label}`;
}
