import type { AuditEvent } from "@/lib/types";

export function auditPayloadSummary(event: AuditEvent) {
  const payload = event.payload;
  const subject = typeof payload.subject_id === "string" ? payload.subject_id : null;
  const role = typeof payload.role === "string" ? payload.role : null;
  if (subject && role) return `${subject} -> ${role}`;
  if (event.action === "skill.archived") return "Skill hidden from catalog";
  if (event.action === "variant.promoted") return String(payload.to_version_id ?? event.resource_id);
  if (event.action === "eval_run.accepted_verification_set") return String(payload.eval_run_id ?? event.resource_id);
  return event.resource_id;
}

export function formatAuditDate(value?: string) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
