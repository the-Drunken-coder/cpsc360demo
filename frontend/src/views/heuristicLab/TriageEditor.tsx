import { Button } from "@blueprintjs/core";
import {
  TRIAGE_ACTIONS, TRIAGE_FLAGS, TRIAGE_GROUPS, TRIAGE_NUMBER_FIELDS, TRIAGE_TEXT_FIELDS,
  type LabCondition, type LabTriageRule,
} from "../../api/heuristicLab";

const CONDITION_TYPES = ["text", "number", "flag", "count", "score", "sample", "quiet"] as const;
const CONDITION_LABELS = { text: "Text match", number: "Numeric threshold", flag: "Report fact",
  count: "Rolling pattern", score: "Keyword score", sample: "Audit sample", quiet: "Time without new reports" };
const OPERATORS: Record<string, string> = {
  gte: "At least", gt: "Greater than", lte: "At most", lt: "Less than", eq: "Exactly", unknown: "Unknown",
  make_model: "Make and model", tbsa: "Burn area (% TBSA)",
};

function readable(value: string) {
  return OPERATORS[value] ?? value.replaceAll("_", " ");
}

function Picker<T extends string>({ label, options, value, onChange, format = readable }: {
  label: string;
  options: readonly T[];
  value: T;
  onChange: (value: T) => void;
  format?: (value: T) => string;
}) {
  return <label>{label}<select className="bp5-input" aria-label={label} value={value} onChange={(event) => {
    const next = options.find((option) => option === event.currentTarget.value);
    if (next !== undefined) onChange(next);
  }}>
    {options.map((option) => <option key={option} value={option}>{format(option)}</option>)}
  </select></label>;
}

function TextValue({ label, value, onChange, limit = 80 }: {
  label: string; value: string; onChange: (value: string) => void; limit?: number;
}) {
  return <label>{label}<input className="bp5-input" required pattern=".*\S.*" maxLength={limit}
    value={value} onChange={(event) => onChange(event.currentTarget.value)} /></label>;
}

function NumericValue({ label, value, onChange, min, max, step = 1 }: {
  label: string; value: number; onChange: (value: number) => void; min: number; max: number; step?: number | "any";
}) {
  return <label>{label}<input className="bp5-input" type="number" required min={min} max={max} step={step}
    value={Number.isNaN(value) ? "" : value} onChange={(event) => onChange(event.currentTarget.valueAsNumber)} /></label>;
}

const DEFAULTS: Record<LabCondition["kind"], LabCondition> = {
  text: { kind: "text", field: "narrative", operator: "contains_any", value: "" },
  number: { kind: "number", field: "age", operator: "lte", value: 5 },
  flag: { kind: "flag", field: "injury", state: "yes" },
  count: { kind: "count", group: "make_model", operator: "gte", window_days: 365, threshold: 2, filter: "all", measure: "reports" },
  score: { kind: "score", terms: "", operator: "gte", threshold: 3 },
  sample: { kind: "sample", percent: 10 },
  quiet: { kind: "quiet", group: "product", days: 90 },
};

function ConditionFields({ condition, change }: { condition: LabCondition; change: (condition: LabCondition) => void }) {
  switch (condition.kind) {
    case "text": return <>
      <Picker label="Field" options={TRIAGE_TEXT_FIELDS} value={condition.field} onChange={(field) => change({ ...condition, field })} />
      <Picker label="Match" options={["contains_any", "contains_all", "equals_any", "contains_none", "unknown"] as const}
        value={condition.operator} onChange={(operator) => change({ ...condition, operator })} />
      {condition.operator !== "unknown" && <TextValue label="Phrases, separated by commas" limit={400}
        value={condition.value} onChange={(value) => change({ ...condition, value })} />}
    </>;
    case "number": return <>
      <Picker label="Field" options={TRIAGE_NUMBER_FIELDS} value={condition.field} onChange={(field) => change({ ...condition, field })} />
      <Picker label="Match" options={["gte", "gt", "lte", "lt", "eq", "unknown"] as const} value={condition.operator} onChange={(operator) => change({ ...condition, operator })} />
      {condition.operator !== "unknown" && <NumericValue label="Value" min={0} max={120} step="any" value={condition.value}
        onChange={(value) => change({ ...condition, value })} />}
    </>;
    case "flag": return <>
      <Picker label="Fact" options={TRIAGE_FLAGS} value={condition.field} onChange={(field) => change({ ...condition, field })} />
      <Picker label="Fact is" options={["yes", "no", "unknown"] as const} value={condition.state} onChange={(state) => change({ ...condition, state })} />
    </>;
    case "count": return <>
      <Picker label="Group by" options={TRIAGE_GROUPS} value={condition.group} onChange={(group) => change({ ...condition, group })} />
      <Picker label="Count" options={["reports", "manufacturers"] as const} value={condition.measure} onChange={(measure) => change({ ...condition, measure })} />
      <Picker label="Include" options={["all", "injury", "hospitalized"] as const} value={condition.filter} onChange={(filter) => change({ ...condition, filter })} />
      <NumericValue label="Window (days)" min={1} max={366} value={condition.window_days} onChange={(window_days) => change({ ...condition, window_days })} />
      <Picker label="Match" options={["gte", "lte"] as const} value={condition.operator} onChange={(operator) => change({ ...condition, operator })} />
      <NumericValue label="Threshold" min={0} max={100} value={condition.threshold} onChange={(threshold) => change({ ...condition, threshold })} />
    </>;
    case "score": return <>
      <TextValue label="Keywords, separated by commas" limit={400} value={condition.terms} onChange={(terms) => change({ ...condition, terms })} />
      <Picker label="Match" options={["gte", "eq"] as const} value={condition.operator} onChange={(operator) => change({ ...condition, operator })} />
      <NumericValue label="Distinct keywords matched" min={0} max={40} value={condition.threshold} onChange={(threshold) => change({ ...condition, threshold })} />
    </>;
    case "quiet": return <>
      <Picker label="Group by" options={TRIAGE_GROUPS} value={condition.group} onChange={(group) => change({ ...condition, group })} />
      <NumericValue label="Minimum days without new reports" min={1} max={366} value={condition.days}
        onChange={(days) => change({ ...condition, days })} />
    </>;
    case "sample": return <NumericValue label="Sample percentage" min={1} max={100} value={condition.percent}
      onChange={(percent) => change({ ...condition, percent })} />;
  }
}

export function TriageEditor({ rules, onChange }: { rules: LabTriageRule[]; onChange: (rules: LabTriageRule[]) => void }) {
  function update(index: number, rule: LabTriageRule) {
    onChange(rules.map((item, position) => position === index ? rule : item));
  }

  return <div className="lab-triage-editor">
    <p className="lab-subtle">Rules can add several recommendations. Suppression overrides targeted actions. The first remaining disposition wins.</p>
    {rules.map((rule, index) => <div className="lab-triage-rule" key={index}>
      <TextValue label="Rule name" value={rule.name} onChange={(name) => update(index, { ...rule, name })} />
      <Picker label="Evaluate" options={rule.conditions.some((condition) => condition.kind === "quiet") ? ["end"] : ["arrival", "end"]} value={rule.trigger ?? "arrival"}
        format={(value) => value === "arrival" ? "On report arrival" : "At the end of the replay"}
        onChange={(trigger) => update(index, { ...rule, trigger })} />
      <Picker label="Conditions required" options={["all", "any"] as const} value={rule.match} onChange={(match) => update(index, { ...rule, match })} />
      {rule.conditions.map((condition, position) => <div className="lab-condition" key={position}>
        <Picker label="Condition type" options={CONDITION_TYPES} value={condition.kind} format={(kind) => CONDITION_LABELS[kind]}
          onChange={(kind) => update(index, { ...rule, trigger: kind === "quiet" ? "end" : rule.trigger,
            conditions: rule.conditions.map((item, offset) => offset === position ? DEFAULTS[kind] : item) })} />
        <ConditionFields condition={condition} change={(next) => update(index, {
          ...rule, conditions: rule.conditions.map((item, offset) => offset === position ? next : item),
        })} />
        <Button small text="Remove condition" disabled={rule.conditions.length === 1}
          onClick={() => update(index, { ...rule, conditions: rule.conditions.filter((_, offset) => offset !== position) })} />
      </div>)}
      <div><Button small text="Add condition" disabled={rule.conditions.length >= 12}
        onClick={() => update(index, { ...rule, conditions: [...rule.conditions, DEFAULTS.text] })} /></div>
      <Picker label="Action" options={TRIAGE_ACTIONS} value={rule.action.kind}
        onChange={(kind) => update(index, { ...rule, action: { ...rule.action, kind } })} />
      <TextValue label={rule.action.kind === "suppress" ? "Action to suppress (e.g. escalate or tag:burn)" : "Action value"}
        value={rule.action.value} onChange={(value) => update(index, { ...rule, action: { ...rule.action, value } })} />
      <div className="lab-rule-controls">
        <Button small text="Move up" disabled={index === 0} onClick={() => {
          onChange([...rules.slice(0, index - 1), rule, ...rules.slice(index - 1, index), ...rules.slice(index + 1)]);
        }} />
        <Button small minimal text="Remove rule" onClick={() => onChange(rules.filter((_, position) => position !== index))} />
      </div>
    </div>)}
    <div><Button small icon="add" text="Add triage rule" disabled={rules.length >= 20} onClick={() =>
      onChange([...rules, { name: "", match: "all", conditions: [DEFAULTS.text], action: { kind: "route", value: "" } }])} /></div>
  </div>;
}
