import { Button, ButtonGroup, Classes, NonIdealState, Spinner, Tooltip } from "@blueprintjs/core";
import { useQuery } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import { useInvestigate } from "../../components/InvestigateProvider";
import { useSession } from "../../session/SessionProvider";
import { AnalystContext, HazardEvidence, Narrative, Section } from "../incident/parts";

export function PreviewPanel({ reportNo, onClose, onOpen, onRelated }: {
  reportNo: string; onClose: () => void; onOpen: () => void; onRelated: () => void;
}) {
  const detail = useQuery({ queryKey: qk.incident(reportNo), queryFn: () => api.incident(reportNo) });
  const investigate = useInvestigate();
  const { canWrite } = useSession();
  const d = detail.data;
  return (
    <aside className="preview-panel">
      <header className="preview-head">
        <span className="mono preview-title">{reportNo}</span>
        <span className="spacer" />
        <ButtonGroup minimal>
          <Tooltip content="Open full report (Enter)"><Button small icon="document-open" onClick={onOpen} aria-label="Open" /></Tooltip>
          <Tooltip content="Related reports (r)"><Button small icon="graph" onClick={onRelated} aria-label="Related" /></Tooltip>
          <Tooltip content={canWrite ? "Add to investigation" : "Read-only viewer"}>
            <Button small icon="folder-new" disabled={!canWrite} onClick={() => investigate.open([reportNo])} aria-label="Add to investigation" />
          </Tooltip>
          <Tooltip content="Close (Esc)"><Button small icon="cross" onClick={onClose} aria-label="Close" /></Tooltip>
        </ButtonGroup>
      </header>
      <div className="preview-body">
        {detail.isPending && <NonIdealState icon={<Spinner size={20} />} />}
        {detail.isError && <NonIdealState icon="error" description={detail.error.message} />}
        {d && (
          <>
            <Section title={d.reported.product_description} tier="reported">
              <dl className="kv compact">
                <dt>Reported</dt><dd>{d.reported.report_date}</dd>
                <dt>Published</dt><dd>{d.reported.publication_date}</dd>
                <dt>Severity</dt><dd>{d.reported.severity}</dd>
                <dt>Product type</dt><dd>{d.reported.product_type ?? d.reported.product_code}</dd>
                <dt>Manufacturer</dt><dd>{d.reported.manufacturer_name}</dd>
                <dt>Brand / model</dt><dd>{[d.reported.brand, d.reported.model].filter(Boolean).join(" · ") || "—"}</dd>
                <dt>Location</dt><dd>{[d.reported.city, d.reported.state].filter(Boolean).join(", ") || "—"}</dd>
                <dt>Victim</dt><dd>{[d.reported.victim_age !== null ? `age ${d.reported.victim_age}` : null, d.reported.victim_sex].filter(Boolean).join(", ") || "—"}</dd>
                <dt>Mfr. response</dt><dd>{d.company_comments.length > 0 ? `${d.company_comments.length} published` : "none"}</dd>
              </dl>
            </Section>
            <Narrative text={d.reported.incident_description} hazards={d.inferred.hazards} />
            <HazardEvidence hazards={d.inferred.hazards} />
            <AnalystContext detail={d} />
            <p className={`${Classes.TEXT_MUTED} preview-foot`}>Enter opens every reported field, responses, and the source record.</p>
          </>
        )}
      </div>
    </aside>
  );
}
