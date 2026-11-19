import { Button } from "@blueprintjs/core";
import { useId, useRef } from "react";
import { flushSync } from "react-dom";
import {
  TRIAGE_ACTIONS, TRIAGE_FLAGS, TRIAGE_GROUPS, TRIAGE_NUMBER_FIELDS, TRIAGE_TEXT_FIELDS,
  type LabCaseAction, type LabCondition, type LabTriageAction, type LabTriageRule,
} from "../../api/heuristicLab";
import { LabHelp } from "./LabHelp";

const CONDITION_TYPES = ["text", "number", "flag", "count", "score", "sample", "quiet"] as const;
const CONDITION_LABELS = { text: "Text match", number: "Numeric threshold", flag: "Report fact",
  count: "Rolling pattern", score: "Keyword score", sample: "Audit sample", quiet: "Time without new reports" };
const OPERATORS: Record<string, string> = {
  gte: "At least", gt: "Greater than", lte: "At most", lt: "Less than", eq: "Exactly", unknown: "Unknown",
  contains_any: "Contains any", contains_all: "Contains all", equals_any: "Equals any", contains_none: "Contains none",
  narrative: "Report narrative", injury: "Injury reported", product_hazard: "Product and hazard",
  make_model: "Make and model", tbsa: "Burn area (% TBSA)",
  all: "All", any: "Any", yes: "Yes", no: "No",
};

const CASE_ACTIONS = {
  nfa: { label: "No further action (NFA)", detail: "Close the case." },
  watchlist: {
    label: "Watchlist",
    detail: "Mark the case for monitoring. Staff reported that it was rarely used and some couldn’t access it.",
  },
  idi: {
    label: "In-depth investigation (IDI)",
    detail: "Send field staff to collect details, photos, or the product itself.",
  },
  compliance: { label: "Compliance", detail: "Refer the case to the compliance office." },
  compliance_other: { label: "Compliance Other", detail: "Refer the case to the compliance office using the Other option recorded in the IPT notes." },
  standards_work: { label: "Standards work", detail: "Flag the case for a voluntary or mandatory standards project." },
  ipt_discussion: { label: "IPT discussion", detail: "Bring the case to the IPT meeting." },
  reject: { label: "Reject", detail: "Move the case to a different IPT." },
  forward: { label: "Forward", detail: "Move the case to a narrower sub-team." },
} satisfies Record<LabCaseAction["kind"], { label: string; detail: string }>;

const LEGACY_ACTIONS = {
  tag: "Add tag", route: "Send to queue", copy: "Also send to queue", escalate: "Escalate to",
  priority: "Set priority", disposition: "Recommend disposition", suppress: "Suppress action", audit: "Mark for audit",
} satisfies Record<Exclude<LabTriageAction["kind"], LabCaseAction["kind"]>, string>;

type RuleDraft = LabTriageRule<LabTriageAction | null>;

function readable(value: string) {
  return OPERATORS[value] ?? value.replaceAll("_", " ");
}

export function recommendationText(action: LabTriageAction) {
  return "value" in action ? `${LEGACY_ACTIONS[action.kind]} · ${action.value}` : CASE_ACTIONS[action.kind].label;
}

function CaseActionPicker({ action, onChange }: { action: RuleDraft["action"]; onChange: (action: LabCaseAction) => void }) {
  const id = useId();
  const detailId = `${id}-detail`;
  const selected = action && !("value" in action) ? action.kind : "";
  return <div className="lab-fields">
    <div className="lab-text-field">
      <label htmlFor={id}>Recommend</label>
      <select id={id} className="bp5-input" value={selected} required
        aria-describedby={action ? detailId : undefined} onChange={(event) => {
          const kind = TRIAGE_ACTIONS.find((option) => option === event.currentTarget.value);
          if (kind) onChange({ kind });
        }}>
        <option value="" disabled>Choose a case action</option>
        {TRIAGE_ACTIONS.map((kind) => <option key={kind} value={kind}>{CASE_ACTIONS[kind].label}</option>)}
      </select>
    </div>
    {selected ? <p id={detailId} className="lab-field-note">{CASE_ACTIONS[selected].detail}</p>
      : action && <p id={detailId} className="lab-field-note">
        Previous action was {recommendationText(action)}. Choose a case action to reuse this rule.
      </p>}
  </div>;
}

function conditionText(condition: LabCondition) {
  const operator = "operator" in condition ? readable(condition.operator).toLowerCase() : "";
  switch (condition.kind) {
    case "text": return condition.operator === "unknown" ? `${readable(condition.field)} is unknown`
      : `${readable(condition.field)} ${operator}${condition.value.trim() ? ` “${condition.value.trim()}”` : ""}`;
    case "number": return condition.operator === "unknown" ? `${readable(condition.field)} is unknown`
      : `${readable(condition.field)} is ${operator}${Number.isNaN(condition.value) ? "" : ` ${condition.value}`}`;
    case "flag": return `${readable(condition.field)} is ${condition.state}`;
    case "count": return `Rolling count by ${readable(condition.group).toLowerCase()}`;
    case "score": return "Keyword score";
    case "sample": return Number.isNaN(condition.percent) ? "Audit sample" : `${condition.percent}% audit sample`;
    case "quiet": return Number.isNaN(condition.days) ? "Quiet period" : `${condition.days} days without new reports`;
  }
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

function TextValue({ label, value, onChange, limit = 80, list = false, help }: {
  label: string; value: string; onChange: (value: string) => void; limit?: number; list?: boolean; help?: string;
}) {
  const id = useId();
  return <div className="lab-text-field">
    <div className="lab-field-label"><label htmlFor={id}>{label}</label>{help && <LabHelp label={label} text={help} />}</div>
    <input id={id} className="bp5-input" required pattern={list ? ".*[^\\s,].*" : ".*\\S.*"} maxLength={limit}
      value={value} onChange={(event) => onChange(event.currentTarget.value)} />
  </div>;
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
      {condition.operator !== "unknown" && <TextValue
        label={condition.field === "narrative" && condition.operator === "contains_any" ? "Report narrative contains" : "Text to match"}
        limit={400} list value={condition.value} onChange={(value) => change({ ...condition, value })}
        help="Separate text entries with commas. Matching ignores capitalization. A contains check also finds text inside longer words or a phrase like “no fire.”" />}
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
      <TextValue label="Keywords" limit={400} list value={condition.terms} onChange={(terms) => change({ ...condition, terms })}
        help="Separate keywords or phrases with commas. Each distinct term counts once when it matches a whole word or phrase in the narrative." />
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

export function TriageEditor({ rules, onChange, disabled }: {
  rules: RuleDraft[];
  onChange: (rules: RuleDraft[]) => void;
  disabled: boolean;
}) {
  const group = useId();
  const list = useRef<HTMLDivElement>(null);
  const add = useRef<HTMLButtonElement>(null);

  function update(index: number, rule: RuleDraft) {
    onChange(rules.map((item, position) => position === index ? rule : item));
  }

  function appendRule() {
    flushSync(() => onChange([...rules, { name: "", match: "all", conditions: [DEFAULTS.flag], action: null }]));
    const detail = list.current?.querySelector<HTMLDetailsElement>("details:last-child");
    if (detail) {
      detail.open = true;
      detail.querySelector("input")?.focus();
    }
  }

  function moveRuleUp(index: number, rule: RuleDraft) {
    flushSync(() => onChange([...rules.slice(0, index - 1), rule, ...rules.slice(index - 1, index), ...rules.slice(index + 1)]));
    const detail = list.current?.querySelectorAll("details")[index - 1];
    if (detail) {
      detail.open = true;
      detail.querySelector("summary")?.focus();
    }
  }

  function removeRule(index: number) {
    list.current?.querySelectorAll("details")[index]?.removeAttribute("open");
    flushSync(() => onChange(rules.filter((_, position) => position !== index)));
    add.current?.focus();
  }

  return <section className="lab-editor-section">
    <div className="lab-editor-heading">
      <h3>Triage rules <LabHelp label="Triage rules"
        text="Combine report facts, text, or patterns to recommend an action. Results show the matching evidence and recommendation. The replay takes no external action." /></h3>
      <Button type="button" small minimal intent="primary" icon="add" text="Add a rule" ref={add}
        disabled={disabled || rules.length >= 20} onClick={appendRule} />
    </div>
    {rules.length === 0 && <p className="lab-empty-rules">No triage rules in this set.</p>}
    <div ref={list}>
      {rules.map((rule, index) => <details className="lab-editor-detail" name={group} key={index}>
        <summary>
          <strong>{rule.name.trim() || "Unnamed rule"}</strong>
          <span>{rule.conditions.map(conditionText).join(rule.match === "all" ? " and " : " or ")} → {rule.action ? recommendationText(rule.action) : "Choose a case action"}</span>
          <span className="lab-disclosure-action" aria-hidden="true" />
        </summary>
        <fieldset className="lab-editor-fields lab-triage-fields" disabled={disabled}>
          <TextValue label="Rule name" value={rule.name} onChange={(name) => update(index, { ...rule, name })} />
          <div className="lab-rule-step">
            <div className="lab-field-label">
              <h4>When</h4>
              <LabHelp label="When to evaluate" text="Arrival rules evaluate each new report as it becomes available. End-of-replay rules use all reports available by the end date and can check for periods with no new reports." />
            </div>
            <div className="lab-fields">
              <Picker label="Evaluate" options={rule.conditions.some((condition) => condition.kind === "quiet") ? ["end"] : ["arrival", "end"]} value={rule.trigger ?? "arrival"}
                format={(value) => value === "arrival" ? "On report arrival" : "At the end of the replay"}
                onChange={(trigger) => update(index, { ...rule, trigger })} />
              <Picker label="Require" options={["all", "any"] as const} value={rule.match}
                format={(value) => value === "all" ? "All conditions to match" : "Any condition to match"}
                onChange={(match) => update(index, { ...rule, match })} />
            </div>
            {rule.conditions.map((condition, position) => <div className="lab-condition" key={position}>
              <div className="lab-fields">
                <Picker label="Condition type" options={CONDITION_TYPES} value={condition.kind} format={(kind) => CONDITION_LABELS[kind]}
                  onChange={(kind) => update(index, { ...rule, trigger: kind === "quiet" ? "end" : rule.trigger,
                    conditions: rule.conditions.map((item, offset) => offset === position ? DEFAULTS[kind] : item) })} />
                <ConditionFields condition={condition} change={(next) => update(index, {
                  ...rule, conditions: rule.conditions.map((item, offset) => offset === position ? next : item),
                })} />
              </div>
              {rule.conditions.length > 1 && <Button type="button" small minimal text="Remove condition"
                onClick={() => update(index, { ...rule, conditions: rule.conditions.filter((_, offset) => offset !== position) })} />}
            </div>)}
            <div><Button type="button" small icon="add" text="Add condition" disabled={rule.conditions.length >= 12}
              onClick={() => update(index, { ...rule, conditions: [...rule.conditions, DEFAULTS.flag] })} /></div>
          </div>
          <div className="lab-rule-step">
            <div className="lab-field-label">
              <h4>Then</h4>
              <LabHelp label="Action order" text="When several rules match a report at the same time, the first matching rule supplies the recommended action. The other matches still appear in the evidence." />
            </div>
            <CaseActionPicker action={rule.action} onChange={(action) => update(index, { ...rule, action })} />
          </div>
          <div className="lab-rule-controls">
            <Button type="button" small minimal icon="arrow-up" text="Move rule up" disabled={index === 0} onClick={() => moveRuleUp(index, rule)} />
            <Button type="button" small minimal intent="danger" text="Remove rule" onClick={() => removeRule(index)} />
          </div>
        </fieldset>
      </details>)}
    </div>
  </section>;
}
