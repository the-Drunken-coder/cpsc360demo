import { Breadcrumbs, Button, Classes, NonIdealState, Spinner, Tab, Tabs, Tag } from "@blueprintjs/core";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { api, qk } from "../../api/client";
import { HazardTags } from "../../components/HazardTags";
import { useInvestigate } from "../../components/InvestigateProvider";
import { useSelection } from "../../session/SelectionProvider";
import { useSession } from "../../session/SessionProvider";
import { AnalystContext, CompanyComments, HazardEvidence, Narrative, Section } from "./parts";
import { RelatedList } from "./RelatedList";
import { ReportedFields } from "./ReportedFields";
import { SourceRecord } from "./SourceRecord";

type TabId = "report" | "related" | "source";

function canGoBack(): boolean {
  return ((window.history.state as { idx?: number } | null)?.idx ?? 0) > 0;
}

export function IncidentView() {
  const { reportNo = "", tab } = useParams();
  const navigate = useNavigate();
  const activeTab: TabId = tab === "related" || tab === "source" ? tab : "report";
  const detail = useQuery({ queryKey: qk.incident(reportNo), queryFn: () => api.incident(reportNo) });
  const investigate = useInvestigate();
  const selection = useSelection();
  const { canWrite } = useSession();

  if (detail.isPending) return <NonIdealState icon={<Spinner />} title={`Loading ${reportNo}`} />;
  if (detail.isError) return <NonIdealState icon="error" title={`Report ${reportNo}`} description={detail.error.message} />;
  const d = detail.data;
  const r = d.reported;
  const hazardKeys = d.inferred.hazards.map((h) => h.hazard);

  return (
    <div className="incident-view">
      <header className="incident-head">
        <Breadcrumbs items={[
          { text: "Explorer", icon: "search-template", onClick: () => (canGoBack() ? navigate(-1) : navigate("/")) },
          { text: r.report_no },
        ]} />
        <div className="incident-title-row">
          <h2 className="incident-title">{r.product_description}</h2>
          <span className="spacer" />
          <Button small icon={selection.isSelected(r.report_no) ? "tick" : "add-to-artifact"}
            text={selection.isSelected(r.report_no) ? "Selected" : "Select"} onClick={() => selection.toggle(r.report_no)} />
          <Button small icon="folder-new" text="Add to investigation" disabled={!canWrite}
            onClick={() => investigate.open([r.report_no])} />
        </div>
        <div className="incident-meta">
          <span className="mono">{r.report_no}</span>
          <span>Reported {r.report_date}</span>
          <span>Published {r.publication_date}</span>
          <Tag minimal intent={r.severity.toLowerCase().includes("death") ? "danger" : r.severity.toLowerCase().includes("injury") ? "warning" : "none"}>
            {r.severity}
          </Tag>
          <span>{r.manufacturer_name}</span>
          {r.model && <span className="mono">{r.model}</span>}
          <HazardTags hazards={hazardKeys} />
        </div>
      </header>
      <Tabs id="incident-tabs" selectedTabId={activeTab} renderActiveTabPanelOnly className="incident-tabs"
        onChange={(id) => navigate(`/incidents/${reportNo}${id === "report" ? "" : `/${String(id)}`}`, { replace: true })}>
        <Tab id="report" title="Report" panel={
          <div className="incident-grid">
            <div className="incident-main">
              <Narrative text={r.incident_description} hazards={d.inferred.hazards} />
              <CompanyComments comments={d.company_comments} raw={r.company_comments} />
              <ReportedFields reported={r} />
            </div>
            <div className="incident-side">
              <HazardEvidence hazards={d.inferred.hazards} />
              <Section title="Canonical keys" tier="inferred" method={d.inferred.method}>
                <dl className="kv">
                  <div className="kv-row"><dt>Manufacturer</dt><dd>{d.inferred.manufacturer_display_name} <span className="mono muted">{d.inferred.manufacturer_key}</span></dd></div>
                  <div className="kv-row"><dt>Brand key</dt><dd className="mono">{d.inferred.brand_key ?? "—"}</dd></div>
                  <div className="kv-row"><dt>Model key</dt><dd className="mono">{d.inferred.model_key ?? "—"}</dd></div>
                </dl>
                <p className={Classes.TEXT_MUTED}>Normalizations used for grouping. The reported spelling is kept in the fields.</p>
              </Section>
              <AnalystContext detail={d} />
            </div>
          </div>
        } />
        <Tab id="related" title="Related" panel={<RelatedList reportNo={reportNo} />} />
        <Tab id="source" title="Source record" panel={<div className="source-panel"><SourceRecord detail={d} /></div>} />
      </Tabs>
    </div>
  );
}
