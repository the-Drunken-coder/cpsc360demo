import { AnchorButton, Callout, Classes, HTMLTable, Spinner, Tag } from "@blueprintjs/core";
import { useQuery } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import type { IncidentDetail, IngestBatch } from "../../api/types";
import { fmtTime } from "../../components/text";
import { Section } from "./parts";

export function BatchFacts({ batch }: { batch: IngestBatch }) {
  return (
    <dl className="kv">
      <div className="kv-row"><dt>Batch</dt><dd>#{batch.id} <Tag minimal>{batch.kind}</Tag></dd></div>
      <div className="kv-row"><dt>Source URL</dt><dd className="mono break">{batch.source_url}</dd></div>
      {Object.keys(batch.params).length > 0 && (
        <div className="kv-row"><dt>Parameters</dt><dd className="mono break">
          {Object.entries(batch.params).map(([k, v]) => `${k}=${v}`).join(" · ")}
        </dd></div>
      )}
      <div className="kv-row"><dt>File SHA-256</dt><dd className="mono break">{batch.file_sha256}</dd></div>
      <div className="kv-row"><dt>Started</dt><dd>{fmtTime(batch.started_at)}</dd></div>
      <div className="kv-row"><dt>Finished</dt><dd>{batch.finished_at ? fmtTime(batch.finished_at) : "running"}</dd></div>
      <div className="kv-row"><dt>Rows</dt><dd>
        {batch.row_count ?? "?"} read · {batch.inserted ?? "?"} inserted · {batch.updated ?? "?"} updated ·
        {" "}{batch.unchanged ?? "?"} unchanged{batch.kept_bulk !== null ? ` · ${batch.kept_bulk} kept from bulk` : ""}
      </dd></div>
    </dl>
  );
}

export function SourceRecord({ detail }: { detail: IncidentDetail }) {
  const reportNo = detail.reported.report_no;
  const versions = useQuery({ queryKey: qk.versions(reportNo), queryFn: () => api.versions(reportNo) });
  const { source } = detail;
  return (
    <>
      <Section title="Source record" tier="reported" actions={
        <AnchorButton small icon="share" href={source.public_search_url} target="_blank" rel="noreferrer"
          text="SaferProducts.gov Public Search" />
      }>
        <dl className="kv">
          <div className="kv-row"><dt>Report No.</dt><dd className="mono">{reportNo}</dd></div>
          <div className="kv-row"><dt>Current row SHA-256</dt><dd className="mono break">{source.current_sha256}</dd></div>
        </dl>
        <h4 className="sub-head">Ingest batch that supplied the current version</h4>
        <BatchFacts batch={source.batch} />
        <p className={Classes.TEXT_MUTED}>
          Public Search detail pages use an internal id that neither export contains. Search for the Report No. there.
        </p>
      </Section>

      <Section title={`Version history (${source.versions.length})`} tier="reported">
        {versions.isPending && <Spinner size={16} />}
        {versions.isError && <Callout intent="danger">{versions.error.message}</Callout>}
        {versions.data?.map((v) => (
          <details key={v.row_sha256} className="version" open={v.row_sha256 === source.current_sha256 && versions.data.length === 1}>
            <summary>
              <span className="mono">{v.row_sha256.slice(0, 16)}</span>
              {v.row_sha256 === source.current_sha256 && <Tag minimal intent="primary">current</Tag>}
              <span className={Classes.TEXT_MUTED}>first seen {fmtTime(v.first_seen_at)} · batch #{v.batch.id} ({v.batch.kind})</span>
            </summary>
            {v.raw ? (
              <HTMLTable compact striped className="raw-row">
                <tbody>
                  {Object.entries(v.raw).map(([k, val]) => (
                    <tr key={k}><th>{k}</th><td className="raw-value">{val}</td></tr>
                  ))}
                </tbody>
              </HTMLTable>
            ) : <p className={Classes.TEXT_MUTED}>Raw row not returned.</p>}
          </details>
        ))}
      </Section>

      <Section title="CPSC disclaimer" tier="reported">
        <div className="disclaimer">{source.disclaimer}</div>
      </Section>
    </>
  );
}
