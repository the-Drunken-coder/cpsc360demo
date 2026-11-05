import { Tag, Tooltip, type IconName, type Intent } from "@blueprintjs/core";

export type ProvenanceTier = "reported" | "inferred" | "analyst";

const TIERS: Record<ProvenanceTier, { label: string; icon: IconName; intent: Intent; meaning: string }> = {
  reported: {
    label: "Reported",
    icon: "document",
    intent: "none",
    meaning: "As published on SaferProducts.gov. Never edited.",
  },
  inferred: {
    label: "Inferred",
    icon: "predictive-analysis",
    intent: "warning",
    meaning: "Produced by an automated method. May be wrong.",
  },
  analyst: {
    label: "Analyst",
    icon: "person",
    intent: "success",
    meaning: "Created by a prototype user. Attributed and audited.",
  },
};

export function Provenance({ tier, method, by }: { tier: ProvenanceTier; method?: string; by?: string }) {
  const t = TIERS[tier];
  const extra = method ? ` Method: ${method}.` : by ? ` By ${by}.` : "";
  return (
    <Tooltip content={`${t.meaning}${extra}`} placement="top" hoverOpenDelay={300}>
      <Tag minimal icon={t.icon} intent={t.intent} className={`provenance provenance-${tier}`}>
        {t.label}{method ? ` · ${method}` : ""}
      </Tag>
    </Tooltip>
  );
}
