import { Badge } from "@/components/chrome";
import type { PromotionReadiness } from "@/lib/types";

export function PromotionReadinessCard({ readiness }: { readiness: PromotionReadiness }) {
  const tone = readinessTone(readiness.status);
  const items = [
    ...readiness.passing_items.map((item) => ({ tone: "good" as const, label: item })),
    ...readiness.risk_items.map((item) => ({ tone: "bad" as const, label: item })),
    ...readiness.blocking_items.map((item) => ({ tone: "bad" as const, label: item })),
  ];

  return (
    <section className={`promotionReadiness promotionReadiness-${readiness.status}`}>
      <div className="promotionReadinessHead">
        <span>Promotion readiness</span>
        <Badge tone={tone}>{readiness.label}</Badge>
      </div>
      <strong>{readiness.reason}</strong>
      <div className="promotionReadinessChecks">
        {items.length > 0 ? (
          items.map((item) => (
            <span className={`promotionCheck promotionCheck-${item.tone}`} key={item.label}>
              {item.label}
            </span>
          ))
        ) : (
          <span className="promotionCheck">暂无额外检查项</span>
        )}
      </div>
    </section>
  );
}

function readinessTone(status: PromotionReadiness["status"]) {
  if (status === "ready") return "good";
  if (status === "risky" || status === "blocked") return "bad";
  return "neutral";
}
