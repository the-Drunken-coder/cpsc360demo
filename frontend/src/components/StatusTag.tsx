import { Tag, type Intent } from "@blueprintjs/core";
import type { InvestigationStatus } from "../api/types";

export const STATUS_META: Record<InvestigationStatus, { label: string; intent: Intent }> = {
  open: { label: "Open", intent: "primary" },
  in_review: { label: "In review", intent: "warning" },
  escalated: { label: "Escalated", intent: "danger" },
  closed: { label: "Closed", intent: "none" },
};

export function StatusTag({ status }: { status: InvestigationStatus }) {
  const meta = STATUS_META[status];
  return <Tag intent={meta.intent} minimal={status === "closed"}>{meta.label}</Tag>;
}
