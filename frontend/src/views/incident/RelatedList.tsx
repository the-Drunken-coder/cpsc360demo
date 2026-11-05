import {
  Button, ButtonGroup, Callout, Checkbox, Classes, NonIdealState, Popover, Spinner, Switch, Tag, TextArea, Tooltip,
  type Intent,
} from "@blueprintjs/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, qk } from "../../api/client";
import type { Reason, ReasonKind, RelatedIncident, Verdict } from "../../api/types";
import { HazardTags } from "../../components/HazardTags";
import { Provenance } from "../../components/Provenance";
import { BulkActions } from "../../components/SelectionBadge";
import { Marked, ReportLink, fmtTime } from "../../components/text";
import { toastError } from "../../components/toaster";
import { useSession } from "../../session/SessionProvider";

const REASON_LABELS: Record<ReasonKind, string> = {
  associated_report: "Associated report",
  same_model: "Same model",
  text_similarity: "Text similarity",
  same_manufacturer: "Same manufacturer",
  same_brand: "Same brand",
  same_product_type: "Same product type",
  shared_hazard: "Shared hazard",
};

export function RelatedList({ reportNo }: { reportNo: string }) {
  const related = useQuery({ queryKey: qk.related(reportNo), queryFn: () => api.related(reportNo) });
  const [selected, setSelected] = useState<string[]>([]);
  const [hideRejected, setHideRejected] = useState(false);

  if (related.isPending) return <NonIdealState icon={<Spinner />} title="Scoring candidates" />;
  if (related.isError) return <NonIdealState icon="error" title="Related search failed" description={related.error.message} />;

  const items = related.data.filter((r) => !(hideRejected && r.review?.verdict === "rejected"));
  const confirmed = related.data.filter((r) => r.review?.verdict === "confirmed").map((r) => r.incident.report_no);
  const toggle = (no: string) => setSelected((cur) => (cur.includes(no) ? cur.filter((x) => x !== no) : [...cur, no]));
  const method = related.data[0]?.method;

  return (
    <div className="related">
      <div className="related-toolbar">
        <span><strong>{related.data.length}</strong> candidates</span>
        {method && <Provenance tier="inferred" method={method} />}
        <span className={Classes.TEXT_MUTED}>{confirmed.length} confirmed</span>
        <Switch className="inline-switch" checked={hideRejected} label="Hide rejected" onChange={(e) => setHideRejected(e.currentTarget.checked)} />
        <span className="spacer" />
        <Button small minimal text="Select confirmed" disabled={confirmed.length === 0} onClick={() => setSelected(confirmed)} />
        <span className="toolbar-selection">{selected.length > 0 ? `this report + ${selected.length}` : ""}</span>
        <BulkActions reportNos={selected.length > 0 ? [reportNo, ...selected] : []} onClear={() => setSelected([])} />
      </div>
      <Callout compact className="related-explainer" icon="info-sign">
        Score is the sum of the listed reason weights, clamped to 1. Same model +0.35, associated report +0.50,
        text similarity +0.40 × cosine, same manufacturer +0.10, same brand +0.05, same product type +0.05,
        shared hazard +0.05 each (max 0.10). Confirmed links always appear.
      </Callout>
      {items.length === 0 && <NonIdealState icon="graph" title="No related reports above the 0.15 threshold" />}
      <ol className="related-list">
        {items.map((r) => (
          <RelatedRow key={r.incident.report_no} anchor={reportNo} item={r}
            selected={selected.includes(r.incident.report_no)} onToggle={() => toggle(r.incident.report_no)} />
        ))}
      </ol>
    </div>
  );
}

function RelatedRow({ anchor, item, selected, onToggle }: {
  anchor: string; item: RelatedIncident; selected: boolean; onToggle: () => void;
}) {
  const { incident: inc, review } = item;
  const verdictClass = review ? `review-${review.verdict}` : "";
  return (
    <li className={`related-row ${verdictClass} ${selected ? "selected" : ""}`}>
      <Checkbox className="row-check" checked={selected} onChange={onToggle} aria-label={`Select ${inc.report_no}`} />
      <div className="score" title={`Score ${item.score.toFixed(3)}`}>
        <div className="score-value">{item.score.toFixed(2)}</div>
        <div className="score-bar"><div style={{ width: `${Math.min(1, item.score) * 100}%` }} /></div>
      </div>
      <div className="related-main">
        <div className="related-head">
          <ReportLink reportNo={inc.report_no} />
          <span className={Classes.TEXT_MUTED}>{inc.report_date}</span>
          <span className="cell-clip related-product">{inc.product_description}</span>
          <span className={Classes.TEXT_MUTED}>{inc.manufacturer_name}{inc.model ? ` · ${inc.model}` : ""}</span>
          <span className={inc.is_injury ? "severity-warning" : Classes.TEXT_MUTED}>{inc.severity}</span>
          <HazardTags hazards={inc.hazards} />
          {review?.verdict === "confirmed" && <Tag intent="success" icon="tick-circle">Confirmed</Tag>}
          {review?.verdict === "rejected" && <Tag minimal intent="danger" icon="disable">Rejected</Tag>}
        </div>
        <ul className="reasons">
          {item.reasons.map((reason, i) => <ReasonLine key={`${reason.kind}-${i}`} reason={reason} />)}
        </ul>
        <div className="related-snippet cell-clip"><Marked html={inc.snippet} /></div>
        {review && (
          <div className="review-meta">
            <Provenance tier="analyst" by={review.reviewer.display_name} />
            <span>{review.verdict} by {review.reviewer.display_name} · {fmtTime(review.reviewed_at)}</span>
            {review.note && <q>{review.note}</q>}
          </div>
        )}
      </div>
      <ReviewControls anchor={anchor} item={item} />
    </li>
  );
}

function ReasonLine({ reason }: { reason: Reason }) {
  return (
    <li className={`reason reason-${reason.kind}`}>
      <span className="reason-weight mono">+{reason.weight.toFixed(2)}</span>
      <Tag minimal className="reason-kind">{REASON_LABELS[reason.kind]}</Tag>
      <span className="reason-detail">{reason.detail}</span>
      {reason.terms && reason.terms.length > 0 && (
        <span className="term-list">{reason.terms.map((t) => <Tag key={t} minimal className="term">{t}</Tag>)}</span>
      )}
      {reason.hazards && <HazardTags hazards={reason.hazards} />}
    </li>
  );
}

function ReviewControls({ anchor, item }: { anchor: string; item: RelatedIncident }) {
  const { canWrite } = useSession();
  const queryClient = useQueryClient();
  const other = item.incident.report_no;
  const [note, setNote] = useState(item.review?.note ?? "");
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: qk.related(anchor) });
    void queryClient.invalidateQueries({ queryKey: qk.related(other) });
    void queryClient.invalidateQueries({ queryKey: qk.incident(anchor) });
    void queryClient.invalidateQueries({ queryKey: qk.incident(other) });
  };
  const review = useMutation({
    mutationFn: (args: { verdict: Verdict; note: string }) =>
      api.reviewRelation({ report_a: anchor, report_b: other, verdict: args.verdict, note: args.note }),
    onSuccess: invalidate,
    onError: toastError,
  });
  const undo = useMutation({ mutationFn: () => api.deleteRelation(anchor, other), onSuccess: invalidate, onError: toastError });
  const busy = review.isPending || undo.isPending;
  const verdict = item.review?.verdict;
  const disabledReason = canWrite ? undefined : "Read-only viewer";

  const button = (v: Verdict, icon: "tick" | "cross", intent: Intent) => (
    <Tooltip content={disabledReason ?? (v === "confirmed" ? "Confirm related" : "Reject as unrelated")}>
      <Button small icon={icon} intent={verdict === v ? intent : "none"} active={verdict === v}
        disabled={!canWrite || busy} aria-label={v === "confirmed" ? "Confirm" : "Reject"}
        onClick={() => review.mutate({ verdict: v, note })} />
    </Tooltip>
  );

  return (
    <div className="review-controls">
      <ButtonGroup>
        {button("confirmed", "tick", "success")}
        {button("rejected", "cross", "danger")}
        <Popover placement="left" disabled={!canWrite} content={
          <div className="note-popover">
            <TextArea fill autoFocus placeholder="Why (optional)" value={note} onChange={(e) => setNote(e.currentTarget.value)} />
            <ButtonGroup fill>
              <Button small intent="success" text="Confirm with note" onClick={() => review.mutate({ verdict: "confirmed", note })} />
              <Button small intent="danger" text="Reject with note" onClick={() => review.mutate({ verdict: "rejected", note })} />
            </ButtonGroup>
          </div>
        }>
          <Tooltip content={disabledReason ?? "Review with a note"}>
            <Button small icon="comment" disabled={!canWrite || busy} aria-label="Review with note" />
          </Tooltip>
        </Popover>
        {verdict && (
          <Tooltip content={disabledReason ?? "Remove review"}>
            <Button small icon="undo" disabled={!canWrite || busy} onClick={() => undo.mutate()} aria-label="Remove review" />
          </Tooltip>
        )}
      </ButtonGroup>
    </div>
  );
}
