type WorkbenchMetricTone = "neutral" | "good" | "bad";

type WorkbenchMetricProps = {
  label: string;
  tone?: WorkbenchMetricTone;
  value: string;
};

export function Metric({ label, tone = "neutral", value }: WorkbenchMetricProps) {
  return (
    <div className={`linearMetric linearMetric-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
