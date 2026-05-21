import clsx from "clsx";
import { humanDate } from "../lib/format";
import type { VariantDetail } from "../types";

type VariantVersionTrackProps = {
  variant: VariantDetail;
};

export function VariantVersionTrack({ variant }: VariantVersionTrackProps) {
  const current = variant.versions.find((version) => version.id === variant.current_version_id) ?? variant.current_version ?? variant.versions.at(-1);

  return (
    <div className="inspector-version-history">
      <ol className="inspector-version-track" aria-label="变体版本历史">
        {variant.versions.map((version) => {
          const currentStep = version.id === variant.current_version_id;
          return (
            <li className={clsx("version-track-step", currentStep && "current")} aria-current={currentStep ? "step" : undefined} key={version.id}>
              <span>v{version.version_number}</span>
              <small>{currentStep ? "当前" : shortDate(version.created_at)}</small>
            </li>
          );
        })}
      </ol>
      {current ? (
        <div className="version-current-summary">
          <strong>当前 v{current.version_number}</strong>
          <span>{current.change_summary || "当前使用中的 bundle 版本。"}</span>
          <small>{humanDate(current.created_at)}</small>
        </div>
      ) : null}
    </div>
  );
}

function shortDate(value?: string | null): string {
  const label = humanDate(value ?? undefined);
  return label.includes(" ") ? label.split(" ")[0] ?? label : label;
}
