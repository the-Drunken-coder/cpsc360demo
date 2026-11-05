import { Button, Callout, Classes, HTMLTable, NonIdealState, Spinner, Tag, Tooltip } from "@blueprintjs/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, qk } from "../../api/client";
import { fmtCount, fmtTime, shortHash } from "../../components/text";
import { toast, toastError } from "../../components/toaster";
import { useSession } from "../../session/SessionProvider";

export function SourceView() {
  const { isLead } = useSession();
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: qk.sourceStatus(), queryFn: api.sourceStatus });
  const sync = useMutation({
    mutationFn: api.sync,
    onSuccess: (batches) => {
      void queryClient.invalidateQueries();
      const inserted = batches.reduce((n, b) => n + (b.inserted ?? 0), 0);
      toast({ intent: "success", icon: "refresh", message: `Sync finished: ${batches.length} batch(es), ${inserted} new reports.` });
    },
    onError: toastError,
  });

  if (status.isPending) return <NonIdealState icon={<Spinner />} title="Loading source status" />;
  if (status.isError) return <NonIdealState icon="error" description={status.error.message} />;
  const s = status.data;
  return (
    <div className="page source-view">
      <header className="page-head">
        <h2>Source: SaferProducts.gov</h2>
        <span className="spacer" />
        <Tooltip content={isLead ? "Fetch newly published reports through Public Search" : "Only a lead may trigger a sync"}>
          <Button icon="refresh" text="Run incremental sync" disabled={!isLead} loading={sync.isPending} onClick={() => sync.mutate()} />
        </Tooltip>
      </header>
      <div className="stat-row">
        <div className="stat"><span className="stat-label">Reports held</span><span className="stat-value">{fmtCount(s.incident_count)}</span></div>
        <div className="stat"><span className="stat-label">Newest report date</span><span className="stat-value">{s.newest_report_date}</span></div>
        <div className="stat"><span className="stat-label">Newest publication date</span><span className="stat-value">{s.newest_publication_date}</span></div>
      </div>
      <Callout compact icon="info-sign" className="source-note">
        Bulk snapshots come from SPDB.zip. Incremental rows come from the Public Search CSV export, which renders records
        less faithfully, so they never overwrite a bulk record. Every received row is kept verbatim with its hash.
        Reports carry a report (submission) date and a publication date. There is no incident date.
      </Callout>
      <HTMLTable compact striped className="full-width dense-table">
        <thead>
          <tr><th>Batch</th><th>Kind</th><th>Started</th><th>Finished</th><th>File SHA-256</th>
            <th className="num">Rows</th><th className="num">Inserted</th><th className="num">Updated</th>
            <th className="num">Unchanged</th><th className="num">Kept bulk</th><th>Parameters</th></tr>
        </thead>
        <tbody>
          {s.batches.map((b) => (
            <tr key={b.id}>
              <td className="mono">#{b.id}</td>
              <td><Tag minimal>{b.kind}</Tag></td>
              <td className="nowrap">{fmtTime(b.started_at)}</td>
              <td className="nowrap">{b.finished_at ? fmtTime(b.finished_at) : <span className={Classes.TEXT_MUTED}>running</span>}</td>
              <td className="mono" title={b.file_sha256}>{shortHash(b.file_sha256)}</td>
              <td className="num">{b.row_count ?? "—"}</td>
              <td className="num">{b.inserted ?? "—"}</td>
              <td className="num">{b.updated ?? "—"}</td>
              <td className="num">{b.unchanged ?? "—"}</td>
              <td className="num">{b.kept_bulk ?? "—"}</td>
              <td className="mono small-text">{Object.entries(b.params).map(([k, v]) => `${k}=${v}`).join(" ")}</td>
            </tr>
          ))}
        </tbody>
      </HTMLTable>
    </div>
  );
}
