import { Button } from "@blueprintjs/core";
import { type PointerEvent, useEffect, useId, useRef, useState } from "react";
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
  narrative: "Report narrative", injury: "Injury reported", death: "Death reported", product_hazard: "Product and hazard",
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

export type RuleDraft = LabTriageRule<LabTriageAction | null> & { draftId: number };
type RuleText = LabTriageRule<LabTriageAction | null>;
const RULE_NAME_LIMIT = 80;
let nextDraftId = 0;

export function createRuleDraft(rule: RuleText): RuleDraft {
  return { ...rule, draftId: nextDraftId++ };
}

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
    case "count": {
      const group = readable(condition.group).toLowerCase();
      if (Number.isNaN(condition.threshold) || Number.isNaN(condition.window_days)) return `Rolling count by ${group}`;
      const filter = condition.filter === "all" ? "" : condition.filter === "injury" ? " with injury" : " with hospitalization";
      return `${operator} ${condition.threshold} ${condition.measure}${filter} in ${condition.window_days} days by ${group}`;
    }
    case "score": return Number.isNaN(condition.threshold) ? "Keyword score"
      : `${operator} ${condition.threshold} keywords${condition.terms.trim() ? ` from “${condition.terms.trim()}”` : ""}`;
    case "sample": return Number.isNaN(condition.percent) ? "Audit sample" : `${condition.percent}% audit sample`;
    case "quiet": return Number.isNaN(condition.days) ? "Quiet period"
      : `${condition.days} days without new reports by ${readable(condition.group).toLowerCase()}`;
  }
}

function conditionSummary(rule: RuleText) {
  return rule.conditions.map(conditionText).join(rule.match === "all" ? " and " : " or ");
}

function automaticRuleName(rule: RuleText) {
  const condition = conditionSummary(rule);
  const action = rule.action ? recommendationText(rule.action) : "New rule";
  const timing = rule.trigger === "end" ? " at replay end" : "";
  const name = Array.from(`${action}${timing} · ${condition}`);
  return name.length <= RULE_NAME_LIMIT ? name.join("") : `${name.slice(0, RULE_NAME_LIMIT - 1).join("").trimEnd()}…`;
}

export function ruleLabel(rule: RuleText) {
  const manualName = rule.auto_named ? "" : rule.name.trim();
  return { name: manualName || automaticRuleName(rule), auto_named: !manualName };
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

function TextValue({ label, value, onChange, limit = 80, list = false, help, placeholder, required = true }: {
  label: string; value: string; onChange: (value: string) => void; limit?: number; list?: boolean; help?: string;
  placeholder?: string; required?: boolean;
}) {
  const id = useId();
  return <div className="lab-text-field">
    <div className="lab-field-label"><label htmlFor={id}>{label}</label>{help && <LabHelp label={label} text={help} />}</div>
    <input id={id} className="bp5-input" required={required} placeholder={placeholder}
      pattern={required ? (list ? ".*[^\\s,].*" : ".*\\S.*") : undefined} maxLength={limit}
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

interface RuleDrag {
  pointerId: number;
  from: number;
  startY: number;
  y: number;
  active: boolean;
  frame: number | null;
}

export function TriageEditor({ rules, onChange, disabled }: {
  rules: RuleDraft[];
  onChange: (rules: RuleDraft[]) => void;
  disabled: boolean;
}) {
  const group = useId();
  const list = useRef<HTMLOListElement>(null);
  const add = useRef<HTMLButtonElement>(null);
  const drag = useRef<RuleDrag | null>(null);
  const [placement, setPlacement] = useState<{ from: number; to: number } | null>(null);
  const [announcement, setAnnouncement] = useState("");

  useEffect(() => () => {
    const frame = drag.current?.frame;
    if (frame != null) cancelAnimationFrame(frame);
  }, []);

  function update(index: number, rule: RuleDraft) {
    onChange(rules.map((item, position) => position === index ? rule : item));
  }

  function appendRule() {
    flushSync(() => onChange([...rules, createRuleDraft({ name: "", match: "all", conditions: [DEFAULTS.flag], action: null })]));
    const detail = list.current?.lastElementChild?.querySelector("details");
    if (detail) {
      detail.open = true;
      detail.querySelector("input")?.focus();
    }
  }

  function moveRule(from: number, to: number) {
    const rule = rules[from];
    if (disabled || !rule || from === to || to < 0 || to >= rules.length) return;
    const next = rules.filter((_, index) => index !== from);
    next.splice(to, 0, rule);
    flushSync(() => onChange(next));
    list.current?.children[to]?.querySelector<HTMLButtonElement>(".lab-rule-handle")?.focus({ preventScroll: true });
    setAnnouncement(`Moved ${ruleLabel(rule).name} to position ${to + 1} of ${rules.length}.`);
  }

  function dropIndex({ from, y }: RuleDrag) {
    const summaries = Array.from(list.current?.querySelectorAll("summary") ?? []);
    const next = summaries.findIndex((summary) => {
      const rect = summary.getBoundingClientRect();
      return y < rect.top + rect.height / 2;
    });
    const insertion = next < 0 ? summaries.length : next;
    return insertion > from ? insertion - 1 : insertion;
  }

  function startDrag(event: PointerEvent<HTMLButtonElement>, from: number) {
    if (disabled || rules.length < 2 || drag.current || !event.isPrimary || event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { pointerId: event.pointerId, from, startY: event.clientY, y: event.clientY, active: false, frame: null };
  }

  function trackDrag(active: RuleDrag) {
    active.frame = null;
    const scroller = list.current?.closest<HTMLElement>(".page.heuristic-lab");
    if (scroller) {
      const rect = scroller.getBoundingClientRect();
      const step = active.y < rect.top + 36 ? -12 : active.y > rect.bottom - 36 ? 12 : 0;
      const before = scroller.scrollTop;
      scroller.scrollTop += step;
      if (scroller.scrollTop !== before) active.frame = requestAnimationFrame(() => trackDrag(active));
    }
    const to = dropIndex(active);
    setPlacement((current) => current?.from === active.from && current.to === to ? current : { from: active.from, to });
  }

  function updateDrag(event: PointerEvent<HTMLButtonElement>) {
    const active = drag.current;
    if (!active || active.pointerId !== event.pointerId) return;
    active.y = event.clientY;
    if (!active.active && Math.abs(active.y - active.startY) < 4) return;
    active.active = true;
    if (active.frame === null) trackDrag(active);
  }

  function finishDrag(event: PointerEvent<HTMLButtonElement>, drop: boolean) {
    const active = drag.current;
    if (!active || active.pointerId !== event.pointerId) return;
    drag.current = null;
    if (active.frame !== null) cancelAnimationFrame(active.frame);
    setPlacement(null);
    if (drop && active.active) moveRule(active.from, dropIndex({ ...active, y: event.clientY }));
  }

  function removeRule(index: number) {
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
    {rules.length > 0 && <p className="lab-rule-order" id={`${group}-order`}>
      Rules run top to bottom. First match wins.{!disabled && rules.length > 1 && " Drag a handle or use its arrow keys to reorder."}
    </p>}
    <div className="lab-reorder-status" role="status">{announcement}</div>
    <ol ref={list} className="lab-rule-list">
      {rules.map((rule, index) => <li className="lab-rule-row" key={rule.draftId}
        data-dragging={placement?.from === index || undefined}
        data-drop-before={placement?.to === index && index < placement.from || undefined}
        data-drop-after={placement?.to === index && index > placement.from || undefined}>
        {!disabled && rules.length > 1 && <Button type="button" minimal icon="drag-handle-vertical" className="lab-rule-handle"
          aria-label={`Reorder rule ${index + 1}: ${ruleLabel(rule).name}`} aria-describedby={`${group}-order`}
          onPointerDown={(event) => startDrag(event, index)} onPointerMove={updateDrag}
          onPointerUp={(event) => finishDrag(event, true)} onPointerCancel={(event) => finishDrag(event, false)}
          onLostPointerCapture={(event) => finishDrag(event, false)}
          onKeyDown={(event) => {
            if (event.key === "Escape" && drag.current) {
              event.currentTarget.releasePointerCapture(drag.current.pointerId);
              return;
            }
            if (event.key === "ArrowUp" || event.key === "ArrowDown") {
              event.preventDefault();
              if (!drag.current) moveRule(index, index + (event.key === "ArrowUp" ? -1 : 1));
            }
          }} />}
        <details className="lab-editor-detail" name={group}>
          <summary>
            <strong>{ruleLabel(rule).name}</strong>
            <span>{conditionSummary(rule)} → {rule.action ? recommendationText(rule.action) : "Choose a case action"}</span>
            <span className="lab-disclosure-action" aria-hidden="true" />
          </summary>
          <fieldset className="lab-editor-fields lab-triage-fields" disabled={disabled}>
            <TextValue label="Rule name (optional)" value={rule.auto_named ? "" : rule.name}
              limit={RULE_NAME_LIMIT} placeholder={automaticRuleName(rule)} required={false}
              help="Leave blank to use a name based on the rule’s conditions and action."
              onChange={(name) => update(index, { ...rule, name, auto_named: false })} />
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
              <Button type="button" small minimal icon="arrow-up" text="Move rule up" disabled={index === 0} onClick={() => moveRule(index, index - 1)} />
              <Button type="button" small minimal icon="arrow-down" text="Move rule down" disabled={index === rules.length - 1} onClick={() => moveRule(index, index + 1)} />
              <Button type="button" small minimal intent="danger" text="Remove rule" onClick={() => removeRule(index)} />
            </div>
          </fieldset>
        </details>
      </li>)}
    </ol>
  </section>;
}
