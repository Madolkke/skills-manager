export function shortId(value: string | null | undefined): string {
  if (!value) return "-";
  if (value.length <= 16) return value;
  return `${value.slice(0, 10)}...${value.slice(-4)}`;
}

export function formatDate(value: string | undefined): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function percent(value: number | null): string {
  if (value === null) return "N/A";
  return `${value}%`;
}
