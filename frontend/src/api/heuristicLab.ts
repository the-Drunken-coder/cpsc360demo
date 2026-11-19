export interface LabRules {
  phrase: string;
  severity: "any" | "injury";
  window_days: number;
  minimum_count: number;
  use_signals?: boolean;
  triage?: LabTriageRule[];
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

export interface LabMetrics {
  caught: number;
  missed: number;
  extra: number;
  alerts: number;
  median_delay_days: number | null;
}

export interface LabCase {
  id: string;
  title: string;
  expected_alert: boolean;
  decisions: LabDecision[];
  first_alert_delay: number | null;
}

export interface LabDecision {
  report: LabReport;
  reasons: string[];
  triage?: LabTriageMatch[];
}

export interface LabEvaluation {
  rules: LabRules;
  metrics: LabMetrics;
  cases: LabCase[];
  end_checks?: LabDecision[];
}

export interface LabRunInput {
  start: string;
  baseline: LabRules;
  candidate: LabRules;
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

export interface LabAdvice {
  model: string;
  proposal: { rules: LabRules; reasoning: string; case_ids: string[] };
  current: LabMetrics;
  proposed: LabMetrics;
}

export const TRIAGE_TEXT_FIELDS = ["narrative", "product", "hazard", "manufacturer", "model", "jurisdiction", "body_area", "retailer"] as const;
export const TRIAGE_NUMBER_FIELDS = ["age", "tbsa", "burn_depth", "people_injured"] as const;
export const TRIAGE_FLAGS = ["injury", "hospitalized", "death", "contact_available", "sample_available", "missing_detail", "intended_use", "duplicate", "recalled", "public_attention", "reviewer_disagreement", "active_case", "unbranded", "on_watchlist"] as const;
export const TRIAGE_GROUPS = ["product", "hazard", "manufacturer", "make_model", "manufacturer_hazard"] as const;
export const TRIAGE_ACTIONS = ["tag", "route", "copy", "escalate", "priority", "disposition", "suppress", "audit"] as const;

export type LabCondition =
  | { kind: "text"; field: typeof TRIAGE_TEXT_FIELDS[number]; operator: "contains_any" | "contains_all" | "equals_any" | "contains_none" | "unknown"; value: string }
  | { kind: "number"; field: typeof TRIAGE_NUMBER_FIELDS[number]; operator: "gte" | "gt" | "lte" | "lt" | "eq" | "unknown"; value: number }
  | { kind: "flag"; field: typeof TRIAGE_FLAGS[number]; state: "yes" | "no" | "unknown" }
  | { kind: "count"; group: typeof TRIAGE_GROUPS[number]; operator: "gte" | "lte"; window_days: number; threshold: number; filter: "all" | "injury" | "hospitalized"; measure: "reports" | "manufacturers" }
  | { kind: "score"; terms: string; operator: "gte" | "eq"; threshold: number }
  | { kind: "sample"; percent: number }
  | { kind: "quiet"; group: typeof TRIAGE_GROUPS[number]; days: number };

export interface LabTriageRule {
  name: string;
  match: "all" | "any";
  trigger?: "arrival" | "end";
  conditions: LabCondition[];
  action: { kind: typeof TRIAGE_ACTIONS[number]; value: string };
}

export interface LabTriageMatch {
  rule: string;
  action: LabTriageRule["action"];
  evidence: string[];
  applied: boolean;
}
