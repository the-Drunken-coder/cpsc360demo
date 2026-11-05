import { Tag } from "@blueprintjs/core";
import type { HazardKey } from "../api/types";
import { HAZARD_LABELS } from "../domain/hazards";

export function HazardTags({ hazards }: { hazards: HazardKey[] }) {
  if (hazards.length === 0) return null;
  return (
    <span className="hazard-tags" title={hazards.map((h) => HAZARD_LABELS[h]).join(", ")}>
      {hazards.map((h) => (
        <Tag key={h} minimal intent="warning" className="hazard-tag">{HAZARD_LABELS[h]}</Tag>
      ))}
    </span>
  );
}
