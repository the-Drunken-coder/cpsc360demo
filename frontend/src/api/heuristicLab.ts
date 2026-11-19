export interface LabRules<Action extends LabTriageAction | null = LabTriageAction> {
  triage?: LabTriageRule<Action>[];
}

export interface LabReport {
  id: string;
  available_on: string;
  product: string;
  hazard: string;
  injury: boolean;
  narrative: string;
  facts?: Record<string, string | number | boolean>;
}

export interface LabScenario {
  version: string;
  first_start: string;
  last_start: string;
  as_of: string;
  baseline: LabRules;
  candidate: LabRules;
  reports: LabReport[];
}

export interface LabCase {
  id: string;
  title: string;
  decisions: LabDecision[];
}

export interface LabDecision {
  report: LabReport;
  triage?: LabTriageMatch[];
}

export interface LabEvaluation {
  rules: LabRules;
  cases: LabCase[];
  end_checks?: LabDecision[];
}

export interface LabRunInput {
  start: string;
  baseline: LabRules<LabCaseAction>;
  candidate: LabRules<LabCaseAction>;
}

export interface LabRunSummary {
  id: number;
  created_at: string;
  start: string;
  end: string;
}

export interface LabRun extends LabRunSummary {
  result: {
    scenario: string;
    evaluator: string;
    start: string;
    end: string;
    starting_reports: LabReport[];
    baseline: LabEvaluation;
    candidate: LabEvaluation;
  };
}

export const TRIAGE_TEXT_FIELDS = ["narrative", "product", "hazard", "manufacturer", "model", "jurisdiction", "body_area", "retailer"] as const;
export const TRIAGE_NUMBER_FIELDS = ["age", "tbsa", "burn_depth", "people_injured"] as const;
export const TRIAGE_FLAGS = ["injury", "hospitalized", "death", "contact_available", "sample_available", "missing_detail", "intended_use", "duplicate", "recalled", "public_attention", "reviewer_disagreement", "active_case", "unbranded", "on_watchlist"] as const;
export const TRIAGE_GROUPS = ["product", "hazard", "product_hazard", "manufacturer", "make_model", "manufacturer_hazard"] as const;
export const TRIAGE_ACTIONS = [
  "nfa", "watchlist", "idi", "compliance", "compliance_other", "standards_work", "ipt_discussion", "reject", "forward",
] as const;

export type LabCaseAction = { kind: typeof TRIAGE_ACTIONS[number] };
type LabLegacyAction = {
  kind: "tag" | "route" | "copy" | "escalate" | "priority" | "disposition" | "suppress" | "audit";
  value: string;
};
export type LabTriageAction = LabCaseAction | LabLegacyAction;

export type LabCondition =
  | { kind: "text"; field: typeof TRIAGE_TEXT_FIELDS[number]; operator: "contains_any" | "contains_all" | "equals_any" | "contains_none" | "unknown"; value: string }
  | { kind: "number"; field: typeof TRIAGE_NUMBER_FIELDS[number]; operator: "gte" | "gt" | "lte" | "lt" | "eq" | "unknown"; value: number }
  | { kind: "flag"; field: typeof TRIAGE_FLAGS[number]; state: "yes" | "no" | "unknown" }
  | { kind: "count"; group: typeof TRIAGE_GROUPS[number]; operator: "gte" | "lte"; window_days: number; threshold: number; filter: "all" | "injury" | "hospitalized"; measure: "reports" | "manufacturers" }
  | { kind: "score"; terms: string; operator: "gte" | "eq"; threshold: number }
  | { kind: "sample"; percent: number }
  | { kind: "quiet"; group: typeof TRIAGE_GROUPS[number]; days: number };

export interface LabTriageRule<Action extends LabTriageAction | null = LabTriageAction> {
  name: string;
  match: "all" | "any";
  trigger?: "arrival" | "end";
  conditions: LabCondition[];
  action: Action;
}

export interface LabTriageMatch {
  rule: string;
  action: LabTriageAction;
  evidence: string[];
  applied: boolean;
}
